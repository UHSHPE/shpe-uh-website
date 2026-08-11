import pytest
from fastapi.testclient import TestClient

from database import get_session
from models.shop.order import Order, OrderItem
from models.shop.product import Product, ProductType
from models.user.user_enums import Role
from services.dependencies import get_current_user
from tests.conftest import make_user


def make_president(session, **overrides):
    fields = dict(
        first_name="Chapter",
        last_name="President",
        cougarnet_email="president@cougarnet.uh.edu",
        personal_email="president@gmail.com",
        psid="8888888",
        role=Role.president,
    )
    fields.update(overrides)
    return make_user(session, **fields)


def make_vp(session, **overrides):
    fields = dict(
        first_name="Vice",
        last_name="President",
        cougarnet_email="vp@cougarnet.uh.edu",
        personal_email="vp@gmail.com",
        psid="7777777",
        role=Role.vpi,
    )
    fields.update(overrides)
    return make_user(session, **fields)


def make_dues_order(session, user):
    """A paid dues order for `user` — the minimal rows has_paid_dues matches
    (non-cancelled order + OrderItem whose name snapshot is the dues product)."""
    from services.shop_services import DUES_PRODUCT_NAME

    dues = Product(
        name=DUES_PRODUCT_NAME,
        description="Chapter dues",
        price_cents=2000,
        product_type=ProductType.apparel,
        sizes=["S", "M", "L"],
    )
    session.add(dues)
    session.commit()
    session.refresh(dues)

    order = Order(
        order_code=f"SHPE-T{user.id}",
        buyer_name=f"{user.first_name} {user.last_name}",
        buyer_email=user.personal_email,
        user_id=user.id,
        total_cents=dues.price_cents,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    session.add(OrderItem(
        order_id=order.id,
        product_id=dues.id,
        product_name=dues.name,
        quantity=1,
        unit_price_cents=dues.price_cents,
        size="M",
    ))
    session.commit()
    return order


@pytest.fixture
def president(session):
    return make_president(session)


@pytest.fixture
def president_client(session, president):
    from main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: president
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def vp(session):
    return make_vp(session)


@pytest.fixture
def vp_client(session, vp):
    """Auth'd as a VP — same directory access as the president, minus the
    presidency. Don't mix with `president_client`/`client` in one test: they
    all override get_current_user on the same app and the last one wins."""
    from main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: vp
    yield TestClient(app)
    app.dependency_overrides.clear()
