"""Square payment step in POST /shop/orders — charge before order creation.

The real Square API is never hit: conftest's autouse disable_square_payments
clears SQUARE_* env vars (dev-mode no-op), and configured-mode tests
monkeypatch square_services directly."""

import pytest
from sqlmodel import select

from models.shop.order import Order
from services import square_services
from services.rate_limit import FAILED_CHARGE_LIMIT, limit_count
from tests.shop_tests.conftest import make_product, order_payload


@pytest.fixture
def square(monkeypatch):
    """Pretend Square is configured and record charge attempts."""
    calls = {
        "charges": [],
        "result": square_services.ChargeResult(
            "sq-payment-1", "https://squareup.com/receipt/preview/sq-payment-1"
        ),
        "error": None,
    }

    def fake_is_configured():
        return True

    def fake_charge_card(payment_token, amount_cents, buyer_email, note, line_items=None):
        calls["charges"].append((payment_token, amount_cents, buyer_email))
        calls["line_items"] = line_items
        if calls["error"] is not None:
            raise calls["error"]
        return calls["result"]

    monkeypatch.setattr(square_services, "is_configured", fake_is_configured)
    monkeypatch.setattr(square_services, "charge_card", fake_charge_card)
    return calls


def place(client, session, product=None, **overrides):
    product = product or make_product(session)
    return client.post("/shop/orders", json=order_payload(product, **overrides))


# --- dev mode (no SQUARE_* env vars — guaranteed by the autouse fixture) ---

def test_dev_mode_accepts_orders_without_a_token(unauth_client, session, sent_emails):
    res = place(unauth_client, session)

    assert res.status_code == 201
    order = session.exec(select(Order)).one()
    assert order.square_payment_id is None


def test_charge_card_without_config_is_a_noop():
    assert square_services.charge_card(None, 4500, "x@y.com", note="t") is None


def test_env_vars_count_as_configured(monkeypatch):
    assert square_services.is_configured() is False
    monkeypatch.setenv("SQUARE_ACCESS_TOKEN", "token")
    monkeypatch.setenv("SQUARE_LOCATION_ID", "loc")
    assert square_services.is_configured() is True


@pytest.mark.parametrize("environment", ["production", "production "])
def test_unconfigured_square_refuses_to_simulate_in_production(monkeypatch, environment):
    """Dev mode is a silent free order, so on the live site it must raise
    rather than fall back. Parametrized on the padded value because that
    spelling used to slip past the check and simulate the charge — with no
    order-side symptom, since the route only demands a payment token when
    is_configured() is true. Called directly rather than through the client:
    conftest builds TestClient without a `with`, so lifespan (and therefore
    assert_production_config) never runs, and this stays independent of that.
    """
    monkeypatch.setenv("ENVIRONMENT", environment)

    with pytest.raises(RuntimeError, match="refusing to simulate"):
        square_services.charge_card(None, 4500, "x@y.com", note="t")


# --- configured: the charge gates order creation ---

def test_charges_server_side_total_and_stores_payment_id(unauth_client, session, square, sent_emails):
    product = make_product(session, price_cents=4500)
    res = place(unauth_client, session, product=product, quantity=2, payment_token="tok-1")

    assert res.status_code == 201
    # Charged exactly the recomputed total — never a client-sent amount.
    assert square["charges"] == [("tok-1", 9000, "jane@example.com")]
    # Cart mirrored into Square line items (size folded into the name) so the
    # charge is itemized in the Square Dashboard.
    assert square["line_items"] == [
        {"name": "SHPE UH Quarter-Zip (M)", "quantity": 2, "unit_price_cents": 4500}
    ]
    order = session.exec(select(Order)).one()
    assert order.square_payment_id == "sq-payment-1"


def test_missing_token_is_rejected_before_charging(unauth_client, session, square, sent_emails):
    res = place(unauth_client, session)  # no payment_token

    assert res.status_code == 400
    assert square["charges"] == []
    assert session.exec(select(Order)).first() is None


def test_declined_card_returns_402_and_no_order(unauth_client, session, square, sent_emails):
    square["error"] = square_services.PaymentError(square_services._DECLINED_MESSAGE)

    res = place(unauth_client, session, payment_token="tok-bad")

    assert res.status_code == 402
    assert res.json()["detail"] == square_services._DECLINED_MESSAGE
    assert session.exec(select(Order)).first() is None


def test_invalid_items_fail_before_the_card_is_charged(unauth_client, session, square, sent_emails):
    product = make_product(session, is_active=False)

    res = place(unauth_client, session, product=product, payment_token="tok-1")

    assert res.status_code == 400
    assert square["charges"] == []


def test_receipt_email_includes_square_receipt_link(unauth_client, session, square, sent_emails):
    res = place(unauth_client, session, payment_token="tok-1")

    assert res.status_code == 201
    buyer_emails = [e for e in sent_emails if e["to"] == "jane@example.com"]
    assert len(buyer_emails) == 1
    assert "https://squareup.com/receipt/preview/sq-payment-1" in buyer_emails[0]["body"]


# --- the 402 body must not identify WHICH check the card failed ---
#
# /shop/orders is anonymous, so a decline message that distinguished a bad
# number from a bad CVC from a bad ZIP turned the chapter's live Square
# account into a card-validation oracle. These two pin that shut.

def test_every_decline_code_returns_one_identical_message():
    messages = {
        square_services._buyer_message(code)
        for code in square_services._DECLINE_CODES
    }

    assert messages == {square_services._DECLINED_MESSAGE}


@pytest.mark.parametrize("code", ["UNAUTHORIZED", "INTERNAL_SERVER_ERROR", None])
def test_non_decline_errors_are_not_reported_as_a_decline(code):
    """A bad access token or a Square outage is our problem, not the card's —
    telling the buyer their card was declined would send them to their bank
    for nothing."""
    assert square_services._buyer_message(code) == square_services._GENERIC_MESSAGE


# --- failed-charge budget (separate from the generous ORDER_LIMIT) ---

def test_repeated_declines_are_throttled_before_reaching_square(
    unauth_client, session, square, sent_emails
):
    square["error"] = square_services.PaymentError(square_services._DECLINED_MESSAGE)
    product = make_product(session)
    budget = limit_count(FAILED_CHARGE_LIMIT)

    for _ in range(budget):
        res = place(unauth_client, session, product=product, payment_token="tok-bad")
        assert res.status_code == 402

    assert len(square["charges"]) == budget

    res = place(unauth_client, session, product=product, payment_token="tok-bad")

    assert res.status_code == 429
    # The point is not touching Square at all once the budget is gone —
    # every probe that reaches it is a real authorization against the
    # chapter's merchant account.
    assert len(square["charges"]) == budget


def test_successful_orders_do_not_spend_the_failed_charge_budget(
    unauth_client, session, square, sent_emails
):
    product = make_product(session)
    for _ in range(limit_count(FAILED_CHARGE_LIMIT) + 2):
        assert place(
            unauth_client, session, product=product, payment_token="tok-1"
        ).status_code == 201

    square["error"] = square_services.PaymentError(square_services._DECLINED_MESSAGE)
    res = place(unauth_client, session, product=product, payment_token="tok-bad")

    assert res.status_code == 402
