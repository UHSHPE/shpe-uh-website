"""§11.3–11.6 — order creation, buyer lookup privacy, manager transitions, rate limit."""

import re

from models.shop.order import Order, OrderItem
from models.shop.product import ProductType
from sqlmodel import select

from services.rate_limit import ORDER_LIMIT, limit_count
from tests.shop_tests.conftest import make_product, order_payload


def create_order(client, session, product=None, **payload_overrides):
    product = product or make_product(session)
    res = client.post("/shop/orders", json=order_payload(product, **payload_overrides))
    return res, product


# --- §11.3 creation (public, simulated payment) ---
def test_item_cap_cannot_be_bypassed_with_duplicate_lines(client, session):
    product = make_product(session, price_cents=1500)
    resp = client.post("/shop/orders", json={
        "buyer_name": "Cap Dodger",
        "buyer_email": "dodger@example.com",
        "items": [
            {"product_id": product.id, "size": "M", "quantity": 3},
            {"product_id": product.id, "size": "M", "quantity": 3}, # 6 total > cap of 5
        ],
    })
    assert resp.status_code == 400
    assert "limited to" in resp.json()["detail"]

def test_create_order_is_public_and_starts_paid(unauth_client, session, sent_emails):
    res, _ = create_order(unauth_client, session)

    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "paid"
    assert re.fullmatch(r"SHPE-[A-Z0-9]{4}", body["order_code"])


def test_total_computed_server_side_ignoring_client_total(unauth_client, session, sent_emails):
    product = make_product(session, price_cents=4500)
    payload = order_payload(product, quantity=2)
    payload["total_cents"] = 1  # must be ignored

    res = unauth_client.post("/shop/orders", json=payload)

    assert res.status_code == 201
    assert res.json()["total_cents"] == 9000


def test_order_item_snapshots_unit_price(unauth_client, session, sent_emails):
    product = make_product(session, price_cents=4500)
    res = unauth_client.post("/shop/orders", json=order_payload(product))
    assert res.status_code == 201

    # price changes after purchase must not affect the order line
    product.price_cents = 9900
    session.add(product)
    session.commit()

    item = session.exec(select(OrderItem)).one()
    assert item.unit_price_cents == 4500


def test_apparel_without_size_400(unauth_client, session, sent_emails):
    res, _ = create_order(unauth_client, session, size=None)
    assert res.status_code == 400


def test_item_product_without_size_201(unauth_client, session, sent_emails):
    sticker = make_product(
        session, name="Sticker", product_type=ProductType.item, sizes=None, price_cents=300
    )
    res = unauth_client.post("/shop/orders", json=order_payload(sticker, size=None))
    assert res.status_code == 201


def test_inactive_product_400(unauth_client, session, sent_emails):
    product = make_product(session, is_active=False)
    res = unauth_client.post("/shop/orders", json=order_payload(product))
    assert res.status_code == 400


def test_retired_product_400(unauth_client, session, sent_emails):
    """retired_at alone blocks the order — is_active is left True here so the
    rejection can only come from the retired check."""
    from services.time_services import utcnow

    product = make_product(session, retired_at=utcnow())
    res = unauth_client.post("/shop/orders", json=order_payload(product))
    assert res.status_code == 400
    assert res.json()["detail"] == "One of the products is unavailable."


def test_unknown_product_400(unauth_client, session, sent_emails):
    payload = order_payload(make_product(session))
    payload["items"][0]["product_id"] = 999
    res = unauth_client.post("/shop/orders", json=payload)
    assert res.status_code == 400


def test_quantity_zero_422(unauth_client, session, sent_emails):
    res, _ = create_order(unauth_client, session, quantity=0)
    assert res.status_code == 422


def test_quantity_at_default_cap_201(unauth_client, session, sent_emails):
    res, _ = create_order(unauth_client, session, quantity=5)
    assert res.status_code == 201


def test_quantity_above_default_cap_400(unauth_client, session, sent_emails):
    res, _ = create_order(unauth_client, session, quantity=6)
    assert res.status_code == 400


def test_authenticated_buyer_links_user_id(client, session, user, sent_emails):
    from main import app
    from services.dependencies import get_optional_user

    app.dependency_overrides[get_optional_user] = lambda: user
    res, _ = create_order(client, session)

    assert res.status_code == 201
    order = session.exec(select(Order)).one()
    assert order.user_id == user.id


def test_guest_order_has_no_user_id(unauth_client, session, sent_emails):
    res, _ = create_order(unauth_client, session)

    assert res.status_code == 201
    order = session.exec(select(Order)).one()
    assert order.user_id is None


# --- §11.4 buyer lookup privacy ---

def test_lookup_with_correct_email_200(unauth_client, session, sent_emails):
    res, _ = create_order(unauth_client, session)
    code = res.json()["order_code"]

    lookup = unauth_client.get(f"/shop/orders/{code}", params={"email": "jane@example.com"})

    assert lookup.status_code == 200
    assert lookup.json()["order_code"] == code


def test_lookup_with_wrong_email_generic_404(unauth_client, session, sent_emails):
    res, _ = create_order(unauth_client, session)
    code = res.json()["order_code"]

    lookup = unauth_client.get(f"/shop/orders/{code}", params={"email": "evil@example.com"})

    assert lookup.status_code == 404
    # same body as a nonexistent code — never reveal the code exists
    missing = unauth_client.get("/shop/orders/SHPE-ZZZZ", params={"email": "evil@example.com"})
    assert lookup.json() == missing.json()


def test_lookup_without_email_rejected(unauth_client, session, sent_emails):
    res, _ = create_order(unauth_client, session)
    code = res.json()["order_code"]

    assert unauth_client.get(f"/shop/orders/{code}").status_code in (404, 422)


def test_my_orders_returns_only_own_orders(client, session, user, sent_emails):
    from main import app
    from services.dependencies import get_optional_user

    # one guest order + one order linked to the signed-in user
    create_order(client, session)
    app.dependency_overrides[get_optional_user] = lambda: user
    create_order(client, session)

    res = client.get("/shop/orders/me")

    assert res.status_code == 200
    assert len(res.json()) == 1
    assert res.json()[0]["user_id"] == user.id


# --- §11.5 manager status transitions ---

def get_order_id(session):
    return session.exec(select(Order)).one().id


def test_manager_advances_paid_ready_picked_up(manager_client, unauth_client, session, sent_emails):
    create_order(unauth_client, session)
    order_id = get_order_id(session)

    res = manager_client.patch(f"/shop/orders/{order_id}", json={"status": "ready"})
    assert res.status_code == 200
    assert res.json()["status"] == "ready"

    res = manager_client.patch(f"/shop/orders/{order_id}", json={"status": "picked_up"})
    assert res.status_code == 200
    assert res.json()["status"] == "picked_up"


def test_illegal_jump_paid_to_picked_up_400(manager_client, unauth_client, session, sent_emails):
    create_order(unauth_client, session)
    order_id = get_order_id(session)

    res = manager_client.patch(f"/shop/orders/{order_id}", json={"status": "picked_up"})

    assert res.status_code == 400


def test_manager_can_cancel_from_paid_and_ready(manager_client, unauth_client, session, sent_emails):
    create_order(unauth_client, session)
    order_id = get_order_id(session)

    assert manager_client.patch(f"/shop/orders/{order_id}", json={"status": "cancelled"}).status_code == 200

    create_order(unauth_client, session)
    second_id = [o.id for o in session.exec(select(Order)).all() if o.id != order_id][0]
    manager_client.patch(f"/shop/orders/{second_id}", json={"status": "ready"})
    assert manager_client.patch(f"/shop/orders/{second_id}", json={"status": "cancelled"}).status_code == 200


def test_member_cannot_patch_order_403(client, unauth_client, session, sent_emails):
    create_order(unauth_client, session)
    order_id = get_order_id(session)

    assert client.patch(f"/shop/orders/{order_id}", json={"status": "ready"}).status_code == 403


def test_list_orders_as_manager(manager_client, unauth_client, session, sent_emails):
    create_order(unauth_client, session)

    res = manager_client.get("/shop/orders")
    assert res.status_code == 200
    assert len(res.json()) == 1


def test_list_orders_as_member_403(client):
    assert client.get("/shop/orders").status_code == 403


def test_list_orders_filters_by_status(manager_client, unauth_client, session, sent_emails):
    create_order(unauth_client, session)
    order_id = get_order_id(session)
    manager_client.patch(f"/shop/orders/{order_id}", json={"status": "ready"})
    create_order(unauth_client, session)

    res = manager_client.get("/shop/orders", params={"status": "ready"})

    assert res.status_code == 200
    assert [o["status"] for o in res.json()] == ["ready"]


# --- §11.6 rate limiting ---

def test_order_creation_rate_limited(unauth_client, session, sent_emails):
    product = make_product(session)

    # Derived from the configured limit (RATE_LIMIT_ORDER) rather than
    # hardcoded, so retuning the limit doesn't break this test.
    for _ in range(limit_count(ORDER_LIMIT)):
        assert unauth_client.post("/shop/orders", json=order_payload(product)).status_code == 201

    assert unauth_client.post("/shop/orders", json=order_payload(product)).status_code == 429
