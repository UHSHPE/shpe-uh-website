"""Dues purchase rules — one T-Shirt Dues per member per year, signed-in only."""

from datetime import datetime, timedelta

import pytest
from sqlmodel import select

from main import app
from models.shop.order import Order, OrderItem, OrderStatus
from services import shop_services
from services.dependencies import get_optional_user
from tests.shop_tests.conftest import make_product, order_payload


def make_dues(session):
    return make_product(session, name="T-Shirt Dues", price_cents=2000)


@pytest.fixture
def signed_in(user):
    """Link orders to the test user (get_optional_user override — the client
    fixtures clear all overrides on teardown)."""
    app.dependency_overrides[get_optional_user] = lambda: user
    return user


def buy_dues(client, session, product=None, **overrides):
    product = product or make_dues(session)
    return client.post("/shop/orders", json=order_payload(product, **overrides))


def test_guest_cannot_buy_dues(unauth_client, session, sent_emails):
    res = buy_dues(unauth_client, session)

    assert res.status_code == 400
    assert "Sign in" in res.json()["detail"]
    assert session.exec(select(Order)).first() is None


def test_dues_quantity_capped_at_one(unauth_client, session, signed_in, sent_emails):
    res = buy_dues(unauth_client, session, quantity=2)

    assert res.status_code == 400
    assert "one-time" in res.json()["detail"]


def test_second_dues_purchase_is_rejected(unauth_client, session, signed_in, sent_emails):
    dues = make_dues(session)
    assert buy_dues(unauth_client, session, product=dues).status_code == 201

    res = buy_dues(unauth_client, session, product=dues)

    assert res.status_code == 400
    assert "already paid" in res.json()["detail"]
    assert len(session.exec(select(Order)).all()) == 1


def test_cancelled_dues_order_does_not_count_as_paid(unauth_client, session, signed_in, sent_emails):
    dues = make_dues(session)
    assert buy_dues(unauth_client, session, product=dues).status_code == 201
    order = session.exec(select(Order)).one()
    order.status = OrderStatus.cancelled
    session.add(order)
    session.commit()

    assert buy_dues(unauth_client, session, product=dues).status_code == 201


def test_regular_products_are_unaffected(unauth_client, session, sent_emails):
    # Guests can still buy normal merch, multiple at a time.
    product = make_product(session)
    res = unauth_client.post("/shop/orders", json=order_payload(product, quantity=2))
    assert res.status_code == 201


def test_me_reports_dues_status(client, session, user, sent_emails):
    # UserOut's validators require ≥1 entry per multi-select list, and the
    # bare make_user has none — give it the minimum so /me can serialize.
    from models.user.multi_selections.user_country_origin import UserCountryOrigin
    from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
    from models.user.multi_selections.user_prof_dev import UserProfDev
    from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
    from models.user.user_enums import Industry, ProfDev, RaceEthnicity

    session.add_all([
        UserRaceEthnicity(user_id=user.id, race_and_ethnicity=RaceEthnicity.hispanic),
        UserInterestedIndustries(user_id=user.id, interested_industry=Industry.electronics),
        UserProfDev(user_id=user.id, prof_dev=ProfDev.internships),
        UserCountryOrigin(user_id=user.id, country_origin="Mexico"),
    ])
    session.commit()

    assert client.get("/me").json()["has_paid_dues"] is False

    dues = make_dues(session)
    app.dependency_overrides[get_optional_user] = lambda: user
    assert client.post("/shop/orders", json=order_payload(dues)).status_code == 201

    assert client.get("/me").json()["has_paid_dues"] is True


# --- yearly reset (dues reset every May 30) ---

def _seed_dues_order(session, user, created_at):
    dues = make_dues(session)
    order = Order(
        order_code=f"DUES-{created_at:%Y%m%d}",
        buyer_name="Test User",
        buyer_email="test@example.com",
        user_id=user.id,
        total_cents=dues.price_cents,
        created_at=created_at,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    session.add(OrderItem(
        order_id=order.id, product_id=dues.id, product_name=dues.name,
        quantity=1, unit_price_cents=dues.price_cents, size="M",
    ))
    session.commit()


def test_period_start_is_most_recent_may30(monkeypatch):
    # On/after May 30 → this year's; before → last year's; boundary inclusive.
    monkeypatch.setattr(shop_services, "utcnow", lambda: datetime(2026, 7, 1))
    assert shop_services.current_dues_period_start() == datetime(2026, 5, 30)
    monkeypatch.setattr(shop_services, "utcnow", lambda: datetime(2026, 3, 1))
    assert shop_services.current_dues_period_start() == datetime(2025, 5, 30)
    monkeypatch.setattr(shop_services, "utcnow", lambda: datetime(2026, 5, 30))
    assert shop_services.current_dues_period_start() == datetime(2026, 5, 30)


def test_dues_from_before_the_reset_do_not_count(session, user):
    start = shop_services.current_dues_period_start()
    _seed_dues_order(session, user, created_at=start - timedelta(days=1))
    assert shop_services.has_paid_dues(session, user.id) is False


def test_dues_from_within_the_period_count(session, user):
    start = shop_services.current_dues_period_start()
    _seed_dues_order(session, user, created_at=start + timedelta(days=1))
    assert shop_services.has_paid_dues(session, user.id) is True


def test_can_repurchase_after_the_reset(unauth_client, session, user, signed_in, sent_emails):
    # Last year's dues (pre-reset) don't block buying this year's.
    _seed_dues_order(session, user, created_at=shop_services.current_dues_period_start() - timedelta(days=1))
    res = buy_dues(unauth_client, session)
    assert res.status_code == 201
