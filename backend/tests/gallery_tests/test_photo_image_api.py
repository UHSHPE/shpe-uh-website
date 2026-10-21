import pytest

from models.gallery_photo import GalleryPhotoStatus
from models.user.user_enums import Role
from services import gallery_services
from tests.gallery_tests.helpers import make_gallery_photo


PNG_BYTES = b"\x89PNG\r\n\x1a\nimage data"


def make_photo(session, user, *, status=GalleryPhotoStatus.pending, filename="photo.png"):
    return make_gallery_photo(session, user, status=status, filename=filename)


def test_reviewer_can_fetch_pending_image(client, session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    user.role = Role.comm_director
    session.add(user)
    session.commit()
    photo = make_photo(session, user)
    (tmp_path / photo.image_filename).write_bytes(PNG_BYTES)

    response = client.get(f"/gallery/admin/photos/{photo.id}/image")

    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "private, no-store"


def test_member_cannot_fetch_pending_image(client, session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    photo = make_photo(session, user)
    (tmp_path / photo.image_filename).write_bytes(PNG_BYTES)

    assert client.get(f"/gallery/admin/photos/{photo.id}/image").status_code == 403


def test_pending_image_requires_authentication(unauth_client, session, user):
    photo = make_photo(session, user)

    assert unauth_client.get(f"/gallery/admin/photos/{photo.id}/image").status_code == 401


def test_missing_photo_or_file_returns_404(client, session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    user.role = Role.president
    session.add(user)
    session.commit()
    photo = make_photo(session, user)

    assert client.get(f"/gallery/admin/photos/{photo.id}/image").status_code == 404
    assert client.get("/gallery/admin/photos/999999/image").status_code == 404


@pytest.mark.parametrize("status", [GalleryPhotoStatus.approved, GalleryPhotoStatus.rejected])
def test_reviewer_can_fetch_reviewed_image(client, session, user, tmp_path, monkeypatch, status):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    user.role = Role.vpe
    session.add(user)
    session.commit()
    photo = make_photo(session, user, status=status)
    (tmp_path / photo.image_filename).write_bytes(PNG_BYTES)

    response = client.get(f"/gallery/admin/photos/{photo.id}/image")
    assert response.status_code == 200
    assert response.content == PNG_BYTES
