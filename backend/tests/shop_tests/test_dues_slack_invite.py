"""The Slack invite that rides along on a dues receipt.

Paying dues is what earns Slack access, so the receipt for a dues order is the
one place the chapter hands over the invite link. `in_slack` flips only once
that email is actually away — recording someone as invited when the relay
dropped the message would strand them with no link and no prompt to ask.
"""

import pytest
from sqlmodel import select

from main import app
from models.shop.order import Order
from services import shop_services
from services.dependencies import get_optional_user
from tests.shop_tests.conftest import make_product, order_payload

SLACK_INVITE = "https://join.slack.com/t/shpeuh/shared_invite/zt-test"
WEB_DEV_EMAIL = "Web.Dev@shpeuhchair.org"


@pytest.fixture
def slack_configured(monkeypatch):
    monkeypatch.setenv("SLACK_URL", SLACK_INVITE)


@pytest.fixture
def buyer(session, user, monkeypatch):
    """A signed-in member who is not in Slack yet."""
    user.in_slack = False
    session.add(user)
    session.commit()
    app.dependency_overrides[get_optional_user] = lambda: user
    return user


def buy(client, session, name="T-Shirt Dues"):
    product = make_product(session, name=name, price_cents=2000)
    res = client.post("/shop/orders", json=order_payload(product))
    assert res.status_code == 201
    return res


def receipt(sent_emails):
    return next(m for m in sent_emails if m["subject"].startswith("Your SHPE UH order"))


def test_dues_receipt_carries_the_invite_and_the_web_dev_contact(
    unauth_client, session, buyer, sent_emails, slack_configured
):
    buy(unauth_client, session)

    body = receipt(sent_emails)["body"]
    assert SLACK_INVITE in body
    assert WEB_DEV_EMAIL in body
    session.refresh(buyer)
    assert buyer.in_slack is True


def test_a_member_already_in_slack_gets_no_invite(
    unauth_client, session, buyer, sent_emails, slack_configured
):
    buyer.in_slack = True
    session.add(buyer)
    session.commit()

    buy(unauth_client, session)

    assert SLACK_INVITE not in receipt(sent_emails)["body"]


def test_an_unconfigured_slack_url_sends_no_invite_and_flips_nothing(
    unauth_client, session, buyer, sent_emails, monkeypatch
):
    monkeypatch.delenv("SLACK_URL", raising=False)

    buy(unauth_client, session)

    assert WEB_DEV_EMAIL not in receipt(sent_emails)["body"]
    session.refresh(buyer)
    assert buyer.in_slack is False


def test_merch_receipts_carry_no_invite(
    unauth_client, session, buyer, sent_emails, slack_configured
):
    buy(unauth_client, session, name="Chapter Hoodie")

    assert SLACK_INVITE not in receipt(sent_emails)["body"]
    session.refresh(buyer)
    assert buyer.in_slack is False


def test_a_guest_dues_order_cannot_happen_so_nothing_is_flipped(
    unauth_client, session, sent_emails, slack_configured
):
    # enforce_dues_rules rejects an anonymous dues purchase before the charge,
    # which is what guarantees the receipt always has a member to look up.
    product = make_product(session, name="T-Shirt Dues", price_cents=2000)
    res = unauth_client.post("/shop/orders", json=order_payload(product))

    assert res.status_code == 400
    assert session.exec(select(Order)).first() is None


def test_a_failed_send_leaves_in_slack_alone(
    unauth_client, session, buyer, monkeypatch, slack_configured
):
    monkeypatch.setattr(shop_services, "send_email", lambda to, subject, body: False)

    buy(unauth_client, session)

    session.refresh(buyer)
    assert buyer.in_slack is False
