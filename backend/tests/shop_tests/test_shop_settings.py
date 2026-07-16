"""FIX 3 — editable shop settings (tagline + per-order item cap)."""

from tests.shop_tests.conftest import make_product, order_payload


def test_get_settings_is_public_with_defaults(unauth_client):
    res = unauth_client.get("/shop/settings")

    assert res.status_code == 200
    body = res.json()
    assert body["order_item_cap"] == 5
    assert body["tagline"]


def test_admin_can_update_tagline_and_cap(manager_client):
    res = manager_client.patch(
        "/shop/settings", json={"tagline": "New drop out now", "order_item_cap": 3}
    )

    assert res.status_code == 200
    assert res.json() == {"tagline": "New drop out now", "order_item_cap": 3}

    # persists on the public read
    assert manager_client.get("/shop/settings").json()["order_item_cap"] == 3


def test_member_cannot_update_settings(client):
    assert client.patch("/shop/settings", json={"tagline": "hax"}).status_code == 403


def test_unauthenticated_cannot_update_settings(unauth_client):
    assert unauth_client.patch("/shop/settings", json={"tagline": "hax"}).status_code == 401


def test_cap_must_be_positive(manager_client):
    assert manager_client.patch("/shop/settings", json={"order_item_cap": 0}).status_code == 422


def test_lowered_cap_is_enforced_on_orders(manager_client, unauth_client, session, sent_emails):
    product = make_product(session)
    manager_client.patch("/shop/settings", json={"order_item_cap": 2})

    ok = unauth_client.post("/shop/orders", json=order_payload(product, quantity=2))
    too_many = unauth_client.post("/shop/orders", json=order_payload(product, quantity=3))

    assert ok.status_code == 201
    assert too_many.status_code == 400
    assert "2" in too_many.json()["detail"]
