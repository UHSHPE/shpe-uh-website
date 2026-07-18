import pytest
from fastapi.testclient import TestClient

from database import get_session
from models.shop.product import Product, ProductType
from models.user.user_enums import Role
from services.dependencies import get_current_user
from tests.conftest import make_user


def make_product(session, **overrides):
    fields = dict(
        name="SHPE UH Quarter-Zip",
        description="Navy quarter-zip with the embroidered chapter logo.",
        price_cents=4500,
        product_type=ProductType.apparel,
        sizes=["S", "M", "L", "XL", "2XL"],
        is_active=True,
    )
    fields.update(overrides)
    product = Product(**fields)
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


def make_manager(session, **overrides):
    """A shop-admin user — comm_director by default (marketing_chair also works)."""
    fields = dict(
        cougarnet_email="manager@cougarnet.uh.edu",
        personal_email="manager@gmail.com",
        psid="9999999",
        role=Role.comm_director,
    )
    fields.update(overrides)
    return make_user(session, **fields)


@pytest.fixture
def manager(session):
    return make_manager(session)


@pytest.fixture
def manager_client(session, manager):
    from main import app

    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: manager
    yield TestClient(app)
    app.dependency_overrides.clear()


@pytest.fixture
def sent_emails(monkeypatch):
    """Capture emails sent by shop_services instead of hitting SMTP/console."""
    from services import shop_services

    sent = []

    def fake_send_email(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr(shop_services, "send_email", fake_send_email)
    return sent


def order_payload(product, *, size="M", quantity=1, **overrides):
    payload = dict(
        buyer_name="Jane Cougar",
        buyer_email="jane@example.com",
        buyer_phone="713-555-0000",
        items=[{"product_id": product.id, "size": size, "quantity": quantity}],
    )
    payload.update(overrides)
    return payload
