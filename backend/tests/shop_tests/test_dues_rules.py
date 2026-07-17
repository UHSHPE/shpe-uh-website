"""Dues purchase rules — one T-Shirt Dues per member, signed-in only."""

import pytest
from sqlmodel import select

from main import app
from models.shop.order import Order, OrderStatus
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
