import secrets

from fastapi import HTTPException, status
from sqlmodel import Session, select

from models.notification import Notification
from models.shop.order import Order, OrderCreate, OrderItem, OrderItemOut, OrderOut, OrderStatus
from models.shop.product import Product, ProductType
from models.shop.shop_settings import ShopSettings
from models.user.user import User
from models.user.user_enums import SHOP_ADMIN_ROLES
from services.email_services import send_email
from services.time_services import utcnow

# No lookalike characters (0/O, 1/I) — codes get read out loud at pickup.
ORDER_CODE_ALPHABET = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"

ALLOWED_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.paid: {OrderStatus.ready, OrderStatus.cancelled},
    OrderStatus.ready: {OrderStatus.picked_up, OrderStatus.cancelled},
    OrderStatus.picked_up: set(),
    OrderStatus.cancelled: set(),
}


def get_shop_settings(session: Session) -> ShopSettings:
    """The singleton settings row, created with defaults on first access."""
    settings = session.exec(select(ShopSettings)).first()
    if settings is None:
        settings = ShopSettings()
        session.add(settings)
        session.commit()
        session.refresh(settings)
    return settings


def generate_order_code(session: Session) -> str:
    while True:
        code = "SHPE-" + "".join(secrets.choice(ORDER_CODE_ALPHABET) for _ in range(4))
        exists = session.exec(select(Order).where(Order.order_code == code)).first()
        if not exists:
            return code


def validate_order_items(
    session: Session, payload: OrderCreate
) -> tuple[list[tuple[Product, str | None, int]], int]:
    """Validate items against the catalog and compute the total server-side.
    Persists nothing — the route charges the card between this and
    create_order, so no order row ever exists for a failed charge."""
    item_cap = get_shop_settings(session).order_item_cap

    lines: list[tuple[Product, str | None, int]] = []
    for item in payload.items:
        if item.quantity > item_cap:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Orders are limited to {item_cap} of each item.",
            )

        product = session.get(Product, item.product_id)
        if product is None or not product.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="One of the products is unavailable.",
            )

        size = item.size
        if product.product_type == ProductType.apparel:
            if not size or not product.sizes or size not in product.sizes:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Please pick a valid size for {product.name}.",
                )
        else:
            size = None  # item products have no size

        lines.append((product, size, item.quantity))

    total_cents = sum(product.price_cents * qty for product, _, qty in lines)
    return lines, total_cents


def create_order(
    session: Session,
    payload: OrderCreate,
    user_id: int | None,
    square_payment_id: str | None = None,
    validated: tuple[list[tuple[Product, str | None, int]], int] | None = None,
) -> Order:
    """Persist the order + line items after the payment step. Pass `validated`
    (the pair from validate_order_items) so the stored total is exactly the
    amount charged; it is only recomputed here when omitted."""
    lines, total_cents = (
        validated if validated is not None else validate_order_items(session, payload)
    )

    order = Order(
        order_code=generate_order_code(session),
        buyer_name=payload.buyer_name,
        buyer_email=payload.buyer_email,
        buyer_phone=payload.buyer_phone,
        user_id=user_id,
        total_cents=total_cents,
        square_payment_id=square_payment_id,
    )
    session.add(order)
    session.commit()
    session.refresh(order)

    for product, size, qty in lines:
        session.add(
            OrderItem(
                order_id=order.id,
                product_id=product.id,
                product_name=product.name,
                quantity=qty,
                unit_price_cents=product.price_cents,
                size=size,
            )
        )
    session.commit()

    return order


def order_to_out(session: Session, order: Order) -> OrderOut:
    items = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    out = OrderOut.model_validate(order)
    out.items = [OrderItemOut.model_validate(item) for item in items]
    return out


def apply_status_transition(session: Session, order: Order, new_status: OrderStatus) -> None:
    """Advance the order state machine; illegal jumps → 400. Entering `ready`
    emails the buyer that their order can be picked up."""
    if new_status not in ALLOWED_TRANSITIONS[order.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move an order from {order.status.value} to {new_status.value}.",
        )

    order.status = new_status
    if new_status == OrderStatus.ready:
        order.ready_at = utcnow()
        notify_buyer_order_ready(session, order)
    elif new_status == OrderStatus.picked_up:
        order.picked_up_at = utcnow()


def _order_summary_lines(session: Session, order: Order) -> list[str]:
    items = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    lines = []
    for item in items:
        size = f" ({item.size})" if item.size else ""
        lines.append(f"  {item.quantity}x {item.product_name}{size}")
    lines.append(f"  Total: ${order.total_cents / 100:.2f}")
    return lines


def notify_managers_new_order(session: Session, order: Order) -> None:
    """In-app Notification row + email for every shop admin on each new order."""
    managers = session.exec(
        select(User).where(User.role.in_(SHOP_ADMIN_ROLES))  # type: ignore[attr-defined]
    ).all()
    body = f"New shop order {order.order_code} from {order.buyer_name} (${order.total_cents / 100:.2f})"

    for manager in managers:
        session.add(Notification(user_id=manager.id, body=body))

        email_body = "\n".join(
            [
                f"Hi {manager.first_name},",
                "",
                f"{order.buyer_name} just placed order {order.order_code}:",
                *_order_summary_lines(session, order),
                "",
                f"Buyer contact: {order.buyer_email}"
                + (f" · {order.buyer_phone}" if order.buyer_phone else ""),
                "",
                "— SHPE UH Shop",
            ]
        )
        send_email(manager.personal_email, f"New shop order {order.order_code}", email_body)

    session.commit()


def notify_buyer_order_ready(session: Session, order: Order) -> None:
    body = "\n".join(
        [
            f"Hi {order.buyer_name},",
            "",
            f"Your SHPE UH order {order.order_code} is ready for pickup!",
            *_order_summary_lines(session, order),
            "",
            "Bring your order code to the next chapter event to pick it up.",
            "",
            "— SHPE UH",
        ]
    )
    send_email(order.buyer_email, f"Your order {order.order_code} is ready for pickup", body)
