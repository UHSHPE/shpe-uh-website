import secrets
from typing import Annotated

import config

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile, status
from fastapi.responses import FileResponse
from sqlmodel import select

from models.shop.order import Order, OrderCreate, OrderOut, OrderStatus, OrderUpdate
from models.shop.product import Product, ProductCreate, ProductOut, ProductUpdate
from models.shop.shop_settings import ShopSettingsOut, ShopSettingsUpdate
from models.user.user import User
from services import shop_services, square_services
from services.dependencies import (
    SessionDependencies,
    get_current_user,
    get_optional_user,
    require_shop_admin,
)
from services.rate_limit import limiter, ORDER_LIMIT
from services.time_services import utcnow
from validators.email import normalize_email

router = APIRouter(prefix="/shop", tags=["Shop"])

# Product images live on disk, one file per product keyed by product id.
# Re-exported as a module attribute (rather than referenced as
# config.PRODUCT_IMAGE_DIR) so tests can keep monkeypatching it to a tmp_path.
PRODUCT_IMAGE_DIR = config.PRODUCT_IMAGE_DIR
# 2 MB, matching the resume cap. Product images are served to every shop
# visitor, so an oversized one is the single biggest bandwidth item on the
# site — a 4.5 MB photo cost ~1.35 GB of origin traffic per 300 viewers.
MAX_IMAGE_BYTES = 2 * 1024 * 1024

# content-type -> (extension, magic bytes)
IMAGE_TYPES = {
    "image/png": (".png", b"\x89PNG\r\n\x1a\n"),
    "image/jpeg": (".jpg", b"\xff\xd8\xff"),
    "image/webp": (".webp", b"RIFF"),
}


def get_active_product_or_404(session, product_id: int) -> Product:
    """Public reads only see products that are live (never retired) AND
    currently offered."""
    product = session.get(Product, product_id)
    if product is None or product.retired_at is not None or not product.is_active:
        raise HTTPException(status_code=404, detail="Product not found")
    return product


# --- shop settings ---

@router.get("/settings", response_model=ShopSettingsOut)
def get_settings(session: SessionDependencies):
    """Public — the storefront needs the tagline and per-order item cap."""
    return shop_services.get_shop_settings(session)


@router.patch(
    "/settings",
    response_model=ShopSettingsOut,
    dependencies=[Depends(require_shop_admin)],
)
def update_settings(payload: ShopSettingsUpdate, session: SessionDependencies):
    settings = shop_services.get_shop_settings(session)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)
    session.add(settings)
    session.commit()
    session.refresh(settings)
    return settings


# --- public: catalog ---

@router.get("/products", response_model=list[ProductOut])
def list_products(session: SessionDependencies):
    return session.exec(
        select(Product)
        .where(Product.is_active == True, Product.retired_at.is_(None))  # noqa: E712
        .order_by(Product.created_at)
    ).all()


@router.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: int, session: SessionDependencies):
    return get_active_product_or_404(session, product_id)


@router.get("/products/{product_id}/image")
def get_product_image(product_id: int, session: SessionDependencies):
    product = session.get(Product, product_id)
    if product is None or not product.image_filename:
        raise HTTPException(status_code=404, detail="No image for this product")

    path = PRODUCT_IMAGE_DIR / product.image_filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="No image for this product")

    ext = path.suffix.lower()
    media_type = next(
        (ct for ct, (e, _) in IMAGE_TYPES.items() if e == ext), "application/octet-stream"
    )
    # Filenames are content-addressed (see upload_product_image), so a given
    # URL always maps to the same bytes and can be cached forever. Without
    # this every shop view re-downloads the full image from the origin:
    # FileResponse does send an ETag, but the 304 short-circuit only exists
    # in StaticFiles, so conditional requests still transfer the whole body.
    return FileResponse(
        path,
        media_type=media_type,
        headers={"Cache-Control": "public, max-age=31536000, immutable"},
    )


# --- public: orders ---

@router.post("/orders", response_model=OrderOut, status_code=status.HTTP_201_CREATED)
@limiter.limit(ORDER_LIMIT)
def place_order(
    request: Request,
    payload: OrderCreate,
    session: SessionDependencies,
    user: Annotated[User | None, Depends(get_optional_user)] = None,
):
    """Charge the card via Square, then create the order. The total is
    recomputed from DB prices — any client-sent total is ignored — and the
    charge uses that server-side amount. Without SQUARE_* config the charge
    is a dev-mode no-op (simulated checkout, same flow as before)."""
    validated = shop_services.validate_order_items(session, payload)
    order_lines, total_cents = validated

    # Dues are one-per-member and require an account — reject before charging.
    shop_services.enforce_dues_rules(session, order_lines, user.id if user else None)

    # Mirror the cart into Square line items so every charge shows up
    # itemized in the Square Dashboard and its sales reports ("2× Tee (M)").
    # These sum to total_cents by construction — Square enforces the match.
    line_items = [
        {
            "name": f"{product.name} ({size})" if size else product.name,
            "quantity": qty,
            "unit_price_cents": product.price_cents,
        }
        for product, size, qty in order_lines
    ]

    if square_services.is_configured() and not payload.payment_token:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing payment token — refresh the page and try again.",
        )

    # Blocking Square client is fine here: this route is sync, so FastAPI
    # already runs it in the threadpool. No order row exists yet — a declined
    # card leaves nothing behind.
    try:
        charge = square_services.charge_card(
            payload.payment_token,
            total_cents,
            payload.buyer_email,
            note=f"SHPE UH shop order — {payload.buyer_name}",
            line_items=line_items,
        )
    except square_services.PaymentError as exc:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED, detail=str(exc)
        ) from exc

    order = shop_services.create_order(
        session,
        payload,
        user.id if user else None,
        square_payment_id=charge.payment_id if charge else None,
        validated=validated,
    )
    shop_services.notify_managers_new_order(session, order)
    shop_services.send_buyer_receipt(
        session, order, charge.receipt_url if charge else None
    )
    return shop_services.order_to_out(session, order)


@router.get("/orders/me", response_model=list[OrderOut])
def my_orders(
    session: SessionDependencies,
    user: Annotated[User, Depends(get_current_user)],
):
    """Order history for the signed-in member (defined before /orders/{code}
    so 'me' isn't swallowed by the code lookup)."""
    orders = session.exec(
        select(Order).where(Order.user_id == user.id).order_by(Order.created_at.desc())
    ).all()
    return [shop_services.order_to_out(session, order) for order in orders]


@router.get("/orders/{order_code}", response_model=OrderOut)
def lookup_order(order_code: str, email: str, session: SessionDependencies):
    # One generic 404 for unknown code OR wrong email — never reveal a code exists
    not_found = HTTPException(status_code=404, detail="Order not found")

    order = session.exec(select(Order).where(Order.order_code == order_code)).first()
    if order is None or order.buyer_email != normalize_email(email):
        raise not_found
    return shop_services.order_to_out(session, order)


# --- manager: products ---

@router.post(
    "/products",
    response_model=ProductOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(require_shop_admin)],
)
def create_product(payload: ProductCreate, session: SessionDependencies):
    product = Product.model_validate(payload)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.patch(
    "/products/{product_id}",
    response_model=ProductOut,
    dependencies=[Depends(require_shop_admin)],
)
def update_product(product_id: int, payload: ProductUpdate, session: SessionDependencies):
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(product, field, value)

    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.delete(
    "/products/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    dependencies=[Depends(require_shop_admin)],
)
def retire_product(product_id: int, session: SessionDependencies):
    """Retire (soft-delete) a product: it leaves the storefront and can't be
    ordered, but the row and its image file stay so order history keeps
    resolving and an admin can restore it. Nothing is ever destroyed.
    Idempotent — retiring an already-retired product is a no-op."""
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    # Dues checkout finds this product BY NAME (see shop_services and the
    # frontend's utils/dues.js) — retiring it would silently break the
    # post-email-verification dues redirect with no other symptom.
    if product.name == shop_services.DUES_PRODUCT_NAME:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f'"{shop_services.DUES_PRODUCT_NAME}" can\'t be retired — new members '
                "are sent to it right after verifying their email. Hide it instead if "
                "you need it off the storefront."
            ),
        )

    if product.retired_at is None:
        product.retired_at = utcnow()
    product.is_active = False

    session.add(product)
    session.commit()
    return None


@router.post(
    "/products/{product_id}/restore",
    response_model=ProductOut,
    dependencies=[Depends(require_shop_admin)],
)
def restore_product(product_id: int, session: SessionDependencies):
    """Bring a retired product back. It returns Hidden (is_active is left
    alone) so the admin republishes it deliberately. Idempotent on a product
    that was never retired."""
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    product.retired_at = None

    session.add(product)
    session.commit()
    session.refresh(product)
    return product


@router.post("/products/{product_id}/image", dependencies=[Depends(require_shop_admin)])
async def upload_product_image(
    product_id: int,
    session: SessionDependencies,
    file: UploadFile = File(...),
):
    product = session.get(Product, product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    if file.content_type not in IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Image must be a PNG, JPEG, or WebP.")

    ext, magic = IMAGE_TYPES[file.content_type]
    contents = await file.read()

    if len(contents) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Image must be {MAX_IMAGE_BYTES // (1024 * 1024)} MB or smaller.",
        )
    if not contents.startswith(magic):
        raise HTTPException(status_code=400, detail="File is not a valid image.")

    # Drop the previous image (its name differs, so it would otherwise linger)
    if product.image_filename:
        (PRODUCT_IMAGE_DIR / product.image_filename).unlink(missing_ok=True)

    # Random suffix makes every upload a distinct URL, which is what lets the
    # response above be cached immutably: replacing a product photo changes
    # the filename, so no browser or CDN can serve the old one.
    filename = f"product_{product.id}_{secrets.token_hex(4)}{ext}"
    PRODUCT_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    (PRODUCT_IMAGE_DIR / filename).write_bytes(contents)

    product.image_filename = filename
    session.add(product)
    session.commit()

    return {"image_filename": product.image_filename}


@router.get(
    "/admin/products",
    response_model=list[ProductOut],
    dependencies=[Depends(require_shop_admin)],
)
def list_all_products(session: SessionDependencies):
    """Admin catalog view — includes hidden AND retired products; the panel
    splits them on retired_at."""
    return session.exec(select(Product).order_by(Product.created_at)).all()


# --- manager: orders ---

@router.get(
    "/orders",
    response_model=list[OrderOut],
    dependencies=[Depends(require_shop_admin)],
)
def list_orders(
    session: SessionDependencies,
    status_filter: Annotated[OrderStatus | None, Query(alias="status")] = None,
):
    stmt = select(Order).order_by(Order.created_at.desc())
    if status_filter is not None:
        stmt = stmt.where(Order.status == status_filter)
    orders = session.exec(stmt).all()
    return [shop_services.order_to_out(session, order) for order in orders]


@router.patch(
    "/orders/{order_id}",
    response_model=OrderOut,
    dependencies=[Depends(require_shop_admin)],
)
def update_order(order_id: int, payload: OrderUpdate, session: SessionDependencies):
    order = session.get(Order, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")

    if payload.status is not None:
        shop_services.apply_status_transition(session, order, payload.status)
    if payload.notes is not None:
        order.notes = payload.notes

    session.add(order)
    session.commit()
    session.refresh(order)
    return shop_services.order_to_out(session, order)
