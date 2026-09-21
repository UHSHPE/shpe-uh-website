import pytest

from models.gallery_photo import GalleryPhoto, GalleryPhotoStatus, Semester
from models.user.user_enums import Role
from services import gallery_services


PNG_BYTES = b"\x89PNG\r\n\x1a\nimage data"


def make_photo(session, user, status):
    photo = GalleryPhoto(
        submitted_by_user_id=user.id,
        image_filename="photo.png",
        semester=Semester.spring,
        year=2026,
        status=status,
    )
    session.add(photo)
    session.commit()
    session.refresh(photo)
    return photo


@pytest.mark.parametrize(
    "status",
    [GalleryPhotoStatus.pending, GalleryPhotoStatus.approved, GalleryPhotoStatus.rejected],
)
def test_reviewer_delete_soft_deletes_photo_and_removes_file(client, session, user, tmp_path, monkeypatch, status):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    user.role = Role.comm_director
    session.add(user)
    session.commit()
    photo = make_photo(session, user, status)
    image_path = tmp_path / photo.image_filename
    image_path.write_bytes(PNG_BYTES)

    response = client.delete(f"/gallery/admin/photos/{photo.id}")

    assert response.status_code == 204
    session.refresh(photo)
    assert photo.is_deleted is True
    assert not image_path.exists()
    assert client.get("/gallery/admin/photos").json() == []
    assert client.get(f"/gallery/admin/photos/{photo.id}/image").status_code == 404


def test_member_cannot_delete_photo(client, session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    photo = make_photo(session, user, GalleryPhotoStatus.pending)
    image_path = tmp_path / photo.image_filename
    image_path.write_bytes(PNG_BYTES)

    response = client.delete(f"/gallery/admin/photos/{photo.id}")

    assert response.status_code == 403
    session.refresh(photo)
    assert photo.is_deleted is False
    assert image_path.read_bytes() == PNG_BYTES


def test_delete_requires_authentication(unauth_client, session, user):
    photo = make_photo(session, user, GalleryPhotoStatus.pending)

    assert unauth_client.delete(f"/gallery/admin/photos/{photo.id}").status_code == 401
    assert session.get(GalleryPhoto, photo.id) is not None


def test_delete_unknown_photo_returns_404(client, session, user):
    user.role = Role.president
    session.add(user)
    session.commit()

    assert client.delete("/gallery/admin/photos/999999").status_code == 404
