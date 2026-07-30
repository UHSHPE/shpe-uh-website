"""§11.1 — model/contract tests (pure, no DB)."""

from models.shop.order import OrderOut, OrderStatus
from models.shop.product import Product, ProductOut, ProductType
from models.shop.shop_settings import ShopSettings
from models.user.user_enums import Role, SHOP_ADMIN_ROLES


def test_shop_admin_roles_are_comm_director_marketing_chair_and_president():
    assert SHOP_ADMIN_ROLES == {Role.comm_director, Role.marketing_chair, Role.president}
    assert not hasattr(Role, "shop_manager")


def test_product_type_values():
    assert {t.value for t in ProductType} == {"apparel", "item"}


def test_order_status_values():
    assert {s.value for s in OrderStatus} == {"paid", "ready", "picked_up", "cancelled"}


def test_product_out_fields():
    expected = {"id", "name", "description", "price_cents", "product_type", "sizes", "is_active"}
    assert expected <= set(ProductOut.model_fields)


def test_product_has_no_stock_column():
    assert "stock" not in Product.model_fields


def test_order_out_fields():
    expected = {"order_code", "status", "total_cents", "buyer_name", "items"}
    assert expected <= set(OrderOut.model_fields)


def test_shop_settings_defaults():
    settings = ShopSettings()
    assert settings.order_item_cap == 5
    assert settings.tagline
