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


# --- retire / restore (soft delete; no product row is ever destroyed) ---

def test_retire_product_as_manager(manager_client, session):
    """DELETE retires: the row survives, stamped retired_at + is_active False,
    hidden from the public detail route but still in the admin catalog."""
    product = make_product(session)

    res = manager_client.delete(f"/shop/products/{product.id}")

    assert res.status_code == 204

    session.refresh(product)
    assert product.retired_at is not None
    assert product.is_active is False

    assert manager_client.get(f"/shop/products/{product.id}").status_code == 404

    admin = manager_client.get("/shop/admin/products")
    assert admin.status_code == 200
    assert product.id in [p["id"] for p in admin.json()]


def test_retired_product_hidden_from_public_list(manager_client, session):
    make_product(session, name="Visible")
    retired = make_product(session, name="Retired One")

    manager_client.delete(f"/shop/products/{retired.id}")

    res = manager_client.get("/shop/products")
    assert [p["name"] for p in res.json()] == ["Visible"]


def test_restore_clears_retired_at_but_leaves_inactive(manager_client, session):
    """A restored product comes back Hidden — the admin republishes it deliberately."""
    product = make_product(session)
    manager_client.delete(f"/shop/products/{product.id}")

    res = manager_client.post(f"/shop/products/{product.id}/restore")

    assert res.status_code == 200
    body = res.json()
    assert body["retired_at"] is None
    assert body["is_active"] is False

    session.refresh(product)
    assert product.retired_at is None
    assert product.is_active is False


def test_restore_is_idempotent_on_live_product(manager_client, session):
    product = make_product(session)

    res = manager_client.post(f"/shop/products/{product.id}/restore")

    assert res.status_code == 200
    assert res.json()["retired_at"] is None
    session.refresh(product)
    assert product.is_active is True


def test_retire_is_idempotent(manager_client, session):
    product = make_product(session)

    assert manager_client.delete(f"/shop/products/{product.id}").status_code == 204
    session.refresh(product)
    first_retired_at = product.retired_at

    assert manager_client.delete(f"/shop/products/{product.id}").status_code == 204
    session.refresh(product)
    assert product.retired_at == first_retired_at


def test_retire_unknown_product_404(manager_client):
    assert manager_client.delete("/shop/products/999").status_code == 404


def test_restore_unknown_product_404(manager_client):
    assert manager_client.post("/shop/products/999/restore").status_code == 404


def test_retire_product_as_member_403(client, session):
    product = make_product(session)
    assert client.delete(f"/shop/products/{product.id}").status_code == 403


def test_restore_product_as_member_403(client, session):
    product = make_product(session)
    assert client.post(f"/shop/products/{product.id}/restore").status_code == 403


def test_retire_keeps_the_image_file(manager_client, session, tmp_path, monkeypatch):
    """Retired rows still show thumbnails in the admin table, and restoring
    has to bring the image back with it — so retiring must not unlink."""
    from routes import shop_routes

    monkeypatch.setattr(shop_routes, "PRODUCT_IMAGE_DIR", tmp_path)
    product = make_product(session)
    manager_client.post(
        f"/shop/products/{product.id}/image",
        files={"file": ("shirt.png", PNG_BYTES, "image/png")},
    )
    session.refresh(product)
    filename = product.image_filename
    assert filename

    assert manager_client.delete(f"/shop/products/{product.id}").status_code == 204

    session.refresh(product)
    assert product.image_filename == filename
    assert (tmp_path / filename).exists()


def test_retiring_the_dues_product_400(manager_client, session):
    """Dues checkout looks the product up by name — retiring it would silently
    break the post-verification redirect."""
    from services import shop_services

    product = make_product(session, name=shop_services.DUES_PRODUCT_NAME)

    res = manager_client.delete(f"/shop/products/{product.id}")

    assert res.status_code == 400
    session.refresh(product)
    assert product.retired_at is None


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


def test_image_is_cached_immutably(manager_client, session, tmp_path, monkeypatch):
    """Product images are the heaviest thing the API serves. Without a cache
    header every shop view re-downloads them from the origin."""
    from routes import shop_routes

    monkeypatch.setattr(shop_routes, "PRODUCT_IMAGE_DIR", tmp_path)
    product = make_product(session)
    manager_client.post(
        f"/shop/products/{product.id}/image",
        files={"file": ("shirt.png", PNG_BYTES, "image/png")},
    )

    served = manager_client.get(f"/shop/products/{product.id}/image")

    assert "immutable" in served.headers["cache-control"]
    assert "max-age=31536000" in served.headers["cache-control"]


def test_replacing_an_image_changes_the_filename(manager_client, session, tmp_path, monkeypatch):
    """The filename is what makes immutable caching safe: if a replacement
    reused the name, every cache would keep serving the old photo forever."""
    from routes import shop_routes

    monkeypatch.setattr(shop_routes, "PRODUCT_IMAGE_DIR", tmp_path)
    product = make_product(session)

    manager_client.post(
        f"/shop/products/{product.id}/image",
        files={"file": ("shirt.png", PNG_BYTES, "image/png")},
    )
    session.refresh(product)
    first = product.image_filename

    manager_client.post(
        f"/shop/products/{product.id}/image",
        files={"file": ("shirt.png", PNG_BYTES, "image/png")},
    )
    session.refresh(product)
    second = product.image_filename

    assert first != second
    # The superseded file is removed rather than left orphaned on the volume.
    assert not (tmp_path / first).exists()
    assert (tmp_path / second).exists()


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
