from datetime import datetime
from enum import Enum

from sqlalchemy import Column, JSON
from sqlmodel import SQLModel, Field

from services.time_services import utcnow


class ProductType(str, Enum):
    apparel = "apparel"
    item = "item"


class Product(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str
    price_cents: int
    product_type: ProductType
    # Apparel size options (e.g. ["S","M","L"]); None/empty for item products.
    sizes: list[str] | None = Field(default=None, sa_column=Column(JSON))
    # Disk filename under uploads/products/ (product_<id>.<ext>); None = no image.
    image_filename: str | None = Field(default=None)
    # Currently-offered toggle: True lists the product on the storefront,
    # False hides it while keeping it in the admin Products table (an admin
    # can flip it back any time). NOT a delete — see retired_at. No numeric
    # inventory is tracked; the only purchase limit is ShopSettings' item cap.
    is_active: bool = Field(default=True)
    # Soft delete: NULL = live, a timestamp = retired. Retired products are
    # gone from the storefront and unorderable, and live in the admin's
    # Retired section until restored. Rows are never destroyed, so order-line
    # history and the image file always survive.
    retired_at: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=utcnow)


class ProductOut(SQLModel):
    id: int
    name: str
    description: str
    price_cents: int
    product_type: ProductType
    sizes: list[str] | None
    image_filename: str | None
    is_active: bool
    # Always null on public responses (retired products never reach them) —
    # it's the admin Products table that splits live vs retired on this.
    retired_at: datetime | None


class ProductCreate(SQLModel):
    name: str
    description: str = ""
    price_cents: int = Field(ge=0)
    product_type: ProductType
    sizes: list[str] | None = None
    is_active: bool = True


class ProductUpdate(SQLModel):
    name: str | None = None
    description: str | None = None
    price_cents: int | None = Field(default=None, ge=0)
    product_type: ProductType | None = None
    sizes: list[str] | None = None
    is_active: bool | None = None
