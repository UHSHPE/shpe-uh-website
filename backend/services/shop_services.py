"""Manage shop orders, inventory, and chapter-dues rules."""

import secrets
from datetime import datetime
from collections import defaultdict
from fastapi import HTTPException, status
from sqlmodel import Session, select

import config
from models.notification import Notification
from models.shop.order import Order, OrderCreate, OrderItem, OrderItemOut, OrderOut, OrderStatus
from models.shop.product import Product, ProductType
from models.shop.shop_settings import ShopSettings
from models.user.user import User
from models.user.user_enums import SHOP_ADMIN_ROLES, Role
from services.committee_services import CHAIR_EMAILS
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


# The chapter-dues product: one per member, ever. Found BY NAME — must match
# seed.py and the frontend's DUES_PRODUCT_NAME (signup redirect, banner,
# product page). OrderItem snapshots this name, so past purchases stay
# detectable even if the product is later edited or deleted.
DUES_PRODUCT_NAME = "T-Shirt Dues"


# Dues are per membership year and reset every May 30.
DUES_RESET_MONTH = 5
DUES_RESET_DAY = 30


def current_dues_period_start() -> datetime:
    """Start of the current dues period — the most recent May 30 (this year's
    if today is on/after it, otherwise last year's). Dues paid before this no
    longer count, so the member owes dues again for the new membership year."""
    now = utcnow()
    reset_this_year = datetime(now.year, DUES_RESET_MONTH, DUES_RESET_DAY)
    if now >= reset_this_year:
        return reset_this_year
    return datetime(now.year - 1, DUES_RESET_MONTH, DUES_RESET_DAY)


def has_dues_line(lines: list[tuple[Product, str | None, int]]) -> bool:
    """Whether a validated cart carries the chapter-dues product."""
    return any(product.name == DUES_PRODUCT_NAME for product, _, _ in lines)


def order_has_dues(session: Session, order: Order) -> bool:
    """Whether a persisted order carries the chapter-dues product."""
    return session.exec(
        select(OrderItem.id).where(
            OrderItem.order_id == order.id,
            OrderItem.product_name == DUES_PRODUCT_NAME,
        )
    ).first() is not None


def enforce_dues_rules(
    lines: list[tuple[Product, str | None, int]],
    user: User | None,
) -> None:
    """Dues are one per member per membership year (reset every May 30):
    quantity capped at 1, buyers must be signed in (the purchase has to attach
    to an account to count), and a repeat purchase within the current period is
    rejected."""
    dues_qty = sum(qty for product, _, qty in lines if product.name == DUES_PRODUCT_NAME)
    if dues_qty == 0:
        return
    if dues_qty > 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="T-Shirt Dues are a one-time purchase — remove the extra from your cart.",
        )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sign in to purchase your T-Shirt Dues so they count toward your membership.",
        )
    if user.has_paid_dues:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You've already paid your T-Shirt Dues — thank you!",
        )


def validate_order_items(
    session: Session, payload: OrderCreate
) -> tuple[list[tuple[Product, str | None, int]], int]:
    """Validate items against the catalog and compute the total server-side.
    Persists nothing — the route charges the card between this and
    create_order, so no order row ever exists for a failed charge."""
    item_cap = get_shop_settings(session).order_item_cap
    lines: list[tuple[Product, str | None, int]] = []
    qty_by_product: dict[int, int] = defaultdict(int)

    for item in payload.items:
        qty_by_product[item.product_id] += item.quantity
        if qty_by_product[item.product_id] > item_cap:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Orders are limited to {item_cap} of each item.",
            )

        product = session.get(Product, item.product_id)
        # Retired (soft-deleted) products are as unorderable as hidden ones —
        # same generic detail either way, never say which.
        if product is None or product.retired_at is not None or not product.is_active:
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

    if user_id is not None and has_dues_line(lines):
        buyer = session.get(User, user_id)
        if buyer is not None:
            buyer.has_paid_dues = True
            session.add(buyer)
    session.commit()

    return order


def order_to_out(session: Session, order: Order) -> OrderOut:
    items = session.exec(select(OrderItem).where(OrderItem.order_id == order.id)).all()
    out = OrderOut.model_validate(order)
    out.items = [OrderItemOut.model_validate(item) for item in items]
    return out


def apply_status_transition(session: Session, order: Order, new_status: OrderStatus) -> None:
    """Advance the order state machine; illegal jumps → 400. Entering `ready`
    emails the buyer that their order can be picked up. An order carrying dues
    can never be cancelled."""
    if new_status not in ALLOWED_TRANSITIONS[order.status]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot move an order from {order.status.value} to {new_status.value}.",
        )
    if new_status == OrderStatus.cancelled and order_has_dues(session, order):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Dues orders can't be cancelled — chapter dues are final once paid.",
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


def _slack_invite_lines() -> list[str]:
    """The Slack invite block, or nothing when no invite link is configured."""
    invite = config.slack_url()
    if not invite:
        return []
    return [
        "",
        "You're a dues-paying member now — here's your invite to our Slack:",
        "",
        invite,
        "",
        f"Having trouble getting in? Email {CHAIR_EMAILS[Role.web_dev_chair]} "
        "and we'll get you sorted.",
    ]


def _slack_invitee(session: Session, order: Order) -> User | None:
    """The buyer to send a Slack invite to, if this order earns them one.

    Args:
        session: Database session used to load the buyer.
        order: The order just paid for.
    Returns:
        The signed-in buyer when the order carries dues and they aren't in
        Slack yet, otherwise None.
    """
    if order.user_id is None or not order_has_dues(session, order):
        return None
    buyer = session.get(User, order.user_id)
    return buyer if buyer is not None and not buyer.in_slack else None


def send_buyer_receipt(session: Session, order: Order, receipt_url: str | None = None) -> None:
    """Email the buyer their receipt right after checkout. Goes to the contact
    email given at checkout (the profile prefills personal_email for signed-in
    members). Includes Square's hosted receipt link when the charge was real;
    dev-mode/simulated orders still get the itemized confirmation. A dues order
    also carries the Slack invite, and `in_slack` only flips once that send
    succeeds — a dead relay must not record a member as invited."""
    invitee = _slack_invitee(session, order)
    body_lines = [
        f"Hi {order.buyer_name},",
        "",
        f"Thanks for your order! Here's your receipt for {order.order_code}:",
        "",
        *_order_summary_lines(session, order),
        "",
        "We'll email you again when it's ready for pickup at a chapter event.",
    ]
    if receipt_url:
        body_lines += ["", f"Square receipt: {receipt_url}"]
    invite_lines = _slack_invite_lines() if invitee else []
    body_lines += invite_lines
    body_lines += ["", "— SHPE UH Shop"]
    sent = send_email(
        order.buyer_email,
        f"Your SHPE UH order {order.order_code}",
        "\n".join(body_lines),
    )
    if sent and invite_lines:
        invitee.in_slack = True
        session.add(invitee)
        session.commit()


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
