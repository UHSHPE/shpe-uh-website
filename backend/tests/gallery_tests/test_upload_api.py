from sqlmodel import select

from models.gallery_photo import GalleryPhoto, GalleryPhotoStatus
from routes import gallery_routes
from services.gallery_services import MAX_IMAGE_BYTES


PNG_BYTES = b"\x89PNG\r\n\x1a\nimage data"


def test_member_upload_creates_pending_photo(client, session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_routes, "GALLERY_IMAGE_DIR", tmp_path)

    response = client.post(
        "/gallery/photos",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201
    photo = session.exec(select(GalleryPhoto)).one()
    assert response.json()["photo_id"] == photo.id
    assert response.json()["status"] == GalleryPhotoStatus.pending.value
    assert photo.submitted_by_user_id == user.id
    assert photo.status == GalleryPhotoStatus.pending
    assert (tmp_path / photo.image_filename).read_bytes() == PNG_BYTES


def test_upload_requires_authentication(unauth_client, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_routes, "GALLERY_IMAGE_DIR", tmp_path)

    response = unauth_client.post(
        "/gallery/photos",
        files={"file": ("photo.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 401
    assert list(tmp_path.iterdir()) == []


def test_oversized_upload_is_rejected(client, session, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_routes, "GALLERY_IMAGE_DIR", tmp_path)

    response = client.post(
        "/gallery/photos",
        files={"file": ("photo.png", PNG_BYTES + b"x" * MAX_IMAGE_BYTES, "image/png")},
    )

    assert response.status_code == 413
    assert session.exec(select(GalleryPhoto)).all() == []
    assert list(tmp_path.iterdir()) == []


def test_mismatched_image_signature_is_rejected(client, session, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_routes, "GALLERY_IMAGE_DIR", tmp_path)

    response = client.post(
        "/gallery/photos",
        files={"file": ("photo.png", b"not a PNG", "image/png")},
    )

    assert response.status_code == 400
    assert session.exec(select(GalleryPhoto)).all() == []
    assert list(tmp_path.iterdir()) == []
