from sqlmodel import SQLModel, Field

DEFAULT_TAGLINE = (
    "Buy merch to rep SHPE UH. Pay online, then pick up in person at an "
    "upcoming chapter event."
)
DEFAULT_ORDER_ITEM_CAP = 5


class ShopSettings(SQLModel, table=True):
    """Singleton row of admin-editable storefront settings. Always access it
    through shop_services.get_shop_settings(), which creates the default row
    on first use."""

    id: int | None = Field(default=None, primary_key=True)
    tagline: str = Field(default=DEFAULT_TAGLINE)
    # Max units of a single line item per order (no persistent inventory).
    order_item_cap: int = Field(default=DEFAULT_ORDER_ITEM_CAP)


class ShopSettingsOut(SQLModel):
    tagline: str
    order_item_cap: int


class ShopSettingsUpdate(SQLModel):
    tagline: str | None = None
    order_item_cap: int | None = Field(default=None, gt=0)
