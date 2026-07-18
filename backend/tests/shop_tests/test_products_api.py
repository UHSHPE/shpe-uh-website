"""§11.2 — products API: public reads, manager-only writes."""

from tests.shop_tests.conftest import make_product

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"fakeimagedata"

NEW_PRODUCT = {
    "name": "SHPE UH Sticker",
    "description": "Die-cut chapter logo sticker.",
    "price_cents": 300,
    "product_type": "item",
}


# --- public reads ---

def test_list_products_is_public_and_returns_active(unauth_client, session):
    make_product(session, name="Quarter-Zip")

    res = unauth_client.get("/shop/products")

    assert res.status_code == 200
    assert [p["name"] for p in res.json()] == ["Quarter-Zip"]


def test_list_products_hides_inactive(unauth_client, session):
    make_product(session, name="Visible")
    make_product(session, name="Hidden", is_active=False)

    res = unauth_client.get("/shop/products")

    assert [p["name"] for p in res.json()] == ["Visible"]


def test_get_product_returns_type_and_sizes(unauth_client, session):
    product = make_product(session, sizes=["S", "M"])

    res = unauth_client.get(f"/shop/products/{product.id}")

    assert res.status_code == 200
    body = res.json()
    assert body["product_type"] == "apparel"
    assert body["sizes"] == ["S", "M"]


def test_get_unknown_product_404(unauth_client):
    assert unauth_client.get("/shop/products/999").status_code == 404


# --- manager writes ---

def test_create_product_as_manager(manager_client):
    res = manager_client.post("/shop/products", json=NEW_PRODUCT)

    assert res.status_code == 201
    body = res.json()
    assert body["name"] == "SHPE UH Sticker"
    assert body["price_cents"] == 300
    assert body["is_active"] is True


def test_create_product_as_marketing_chair(session):
    """Both shop-admin roles work — marketing_chair as well as comm_director."""
    from fastapi.testclient import TestClient

    from database import get_session
    from main import app
    from models.user.user_enums import Role
    from services.dependencies import get_current_user
    from tests.shop_tests.conftest import make_manager

    chair = make_manager(
        session,
        cougarnet_email="marketing@cougarnet.uh.edu",
        personal_email="marketing@gmail.com",
        psid="7777777",
        role=Role.marketing_chair,
    )
    app.dependency_overrides[get_session] = lambda: session
    app.dependency_overrides[get_current_user] = lambda: chair
    try:
        assert TestClient(app).post("/shop/products", json=NEW_PRODUCT).status_code == 201
    finally:
        app.dependency_overrides.clear()


def test_create_product_as_member_403(client):
    assert client.post("/shop/products", json=NEW_PRODUCT).status_code == 403


def test_create_product_unauthenticated_401(unauth_client):
    assert unauth_client.post("/shop/products", json=NEW_PRODUCT).status_code == 401


def test_patch_product_toggles_active(manager_client, session):
    product = make_product(session)

    res = manager_client.patch(f"/shop/products/{product.id}", json={"is_active": False})

    assert res.status_code == 200
    assert res.json()["is_active"] is False
    session.refresh(product)
    assert product.is_active is False


def test_patch_product_as_member_403(client, session):
    product = make_product(session)
    assert client.patch(f"/shop/products/{product.id}", json={"is_active": False}).status_code == 403


def test_delete_product_as_manager(manager_client, session):
    product = make_product(session)

    res = manager_client.delete(f"/shop/products/{product.id}")

    assert res.status_code in (200, 204)
    assert manager_client.get(f"/shop/products/{product.id}").status_code == 404


# --- image upload ---

def test_upload_product_image_as_manager(manager_client, session, tmp_path, monkeypatch):
    from routes import shop_routes

    monkeypatch.setattr(shop_routes, "PRODUCT_IMAGE_DIR", tmp_path)
    product = make_product(session)

    res = manager_client.post(
        f"/shop/products/{product.id}/image",
        files={"file": ("shirt.png", PNG_BYTES, "image/png")},
    )

    assert res.status_code == 200
    session.refresh(product)
    assert product.image_filename

    served = manager_client.get(f"/shop/products/{product.id}/image")
    assert served.status_code == 200
    assert served.content == PNG_BYTES


def test_upload_non_image_400(manager_client, session, tmp_path, monkeypatch):
    from routes import shop_routes

    monkeypatch.setattr(shop_routes, "PRODUCT_IMAGE_DIR", tmp_path)
    product = make_product(session)

    res = manager_client.post(
        f"/shop/products/{product.id}/image",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert res.status_code == 400


def test_upload_image_as_member_403(client, session):
    product = make_product(session)

    res = client.post(
        f"/shop/products/{product.id}/image",
        files={"file": ("shirt.png", PNG_BYTES, "image/png")},
    )

    assert res.status_code == 403
