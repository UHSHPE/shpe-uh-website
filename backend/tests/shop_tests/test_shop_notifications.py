"""§11.7 — notifications & email on shop activity."""

from models.notification import Notification
from sqlmodel import select

from tests.shop_tests.conftest import make_manager, make_product, order_payload


def place_order(unauth_client, session):
    product = make_product(session)
    res = unauth_client.post("/shop/orders", json=order_payload(product))
    assert res.status_code == 201
    return res.json()


def test_new_order_notifies_each_shop_admin_in_app(unauth_client, session, manager, sent_emails):
    from models.user.user_enums import Role

    # both admin roles get notified — manager is comm_director, this one is marketing_chair
    second = make_manager(
        session,
        cougarnet_email="manager2@cougarnet.uh.edu",
        personal_email="manager2@gmail.com",
        psid="8888888",
        role=Role.marketing_chair,
    )

    place_order(unauth_client, session)

    rows = session.exec(select(Notification)).all()
    assert {n.user_id for n in rows} == {manager.id, second.id}


def test_new_order_emails_managers(unauth_client, session, manager, sent_emails):
    order = place_order(unauth_client, session)

    manager_emails = [e for e in sent_emails if e["to"] == manager.personal_email]
    assert len(manager_emails) == 1
    assert order["order_code"] in manager_emails[0]["body"]


def test_no_buyer_email_at_order_time(unauth_client, session, manager, sent_emails):
    place_order(unauth_client, session)

    assert all(e["to"] != "jane@example.com" for e in sent_emails)


def test_marking_ready_emails_buyer(manager_client, unauth_client, session, manager, sent_emails):
    order = place_order(unauth_client, session)
    from models.shop.order import Order

    order_id = session.exec(select(Order)).one().id
    sent_emails.clear()

    res = manager_client.patch(f"/shop/orders/{order_id}", json={"status": "ready"})

    assert res.status_code == 200
    buyer_emails = [e for e in sent_emails if e["to"] == "jane@example.com"]
    assert len(buyer_emails) == 1
    assert order["order_code"] in buyer_emails[0]["body"]
