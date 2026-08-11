from datetime import datetime
from enum import Enum

from pydantic import field_validator
from sqlmodel import SQLModel, Field

from services.time_services import utcnow
from validators.email import normalize_email


class OrderStatus(str, Enum):
    paid = "paid"
    ready = "ready"
    picked_up = "picked_up"
    cancelled = "cancelled"


class Order(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    order_code: str = Field(unique=True, index=True)
    buyer_name: str
    buyer_email: str
    buyer_phone: str = ""
    user_id: int | None = Field(default=None, foreign_key="user.id")
    status: OrderStatus = Field(default=OrderStatus.paid)
    total_cents: int
    created_at: datetime = Field(default_factory=utcnow)
    ready_at: datetime | None = Field(default=None)
    picked_up_at: datetime | None = Field(default=None)
    notes: str | None = Field(default=None)
    # Square payment id backing this order (square_services.py); None for
    # dev-mode/simulated orders. Internal — deliberately NOT in OrderOut.
    square_payment_id: str | None = Field(default=None)


class OrderItem(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    order_id: int = Field(foreign_key="order.id")
    product_id: int = Field(foreign_key="product.id")
    # Snapshots so the order stays readable if the product is edited/deleted.
    product_name: str
    quantity: int
    unit_price_cents: int
    size: str | None = Field(default=None)


class OrderItemIn(SQLModel):
    product_id: int
    size: str | None = None
    quantity: int = Field(gt=0)


class OrderItemOut(SQLModel):
    product_id: int
    product_name: str
    size: str | None
    quantity: int
    unit_price_cents: int


class OrderCreate(SQLModel):
    buyer_name: str = Field(min_length=1)
    buyer_email: str
    buyer_phone: str = ""
    items: list[OrderItemIn] = Field(min_length=1, max_length=20)
    # One-time card token from the Square Web Payments SDK. None is only
    # accepted in dev mode (no SQUARE_* config), where checkout is simulated.
    payment_token: str | None = None

    @field_validator("buyer_email", mode="before")
    @classmethod
    def normalize_buyer_email(cls, v: str) -> str:
        return normalize_email(str(v))


class OrderOut(SQLModel):
    id: int
    order_code: str
    status: OrderStatus
    total_cents: int
    buyer_name: str
    buyer_email: str
    buyer_phone: str
    user_id: int | None
    created_at: datetime
    ready_at: datetime | None
    picked_up_at: datetime | None
    notes: str | None
    items: list[OrderItemOut] = []


class OrderUpdate(SQLModel):
    status: OrderStatus | None = None
    notes: str | None = None
