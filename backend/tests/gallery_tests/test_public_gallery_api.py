import pytest

from models.gallery_photo import GalleryPhoto, GalleryPhotoStatus, Semester
from services import gallery_services


PNG_BYTES = b"\x89PNG\r\n\x1a\nimage data"


def make_photo(
    session,
    user,
    *,
    filename,
    status=GalleryPhotoStatus.pending,
    semester=Semester.spring,
    year=2026,
    is_deleted=False,
):
    photo = GalleryPhoto(
        submitted_by_user_id=user.id,
        image_filename=filename,
        semester=semester,
        year=year,
        status=status,
        is_deleted=is_deleted,
    )
    session.add(photo)
    session.commit()
    session.refresh(photo)
    return photo


def test_public_list_returns_only_approved_active_photo_metadata(unauth_client, session, user):
    approved = make_photo(
        session,
        user,
        filename="approved.png",
        status=GalleryPhotoStatus.approved,
        semester=Semester.fall,
        year=2027,
    )
    make_photo(session, user, filename="pending.png")
    make_photo(session, user, filename="rejected.png", status=GalleryPhotoStatus.rejected)
    make_photo(
        session,
        user,
        filename="deleted.png",
        status=GalleryPhotoStatus.approved,
        is_deleted=True,
    )

    response = unauth_client.get("/gallery/photos")

    assert response.status_code == 200
    assert response.json() == [
        {"id": approved.id, "semester": "fall", "year": 2027}
    ]


def test_public_can_fetch_approved_image(unauth_client, session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    photo = make_photo(
        session,
        user,
        filename="approved.png",
        status=GalleryPhotoStatus.approved,
    )
    (tmp_path / photo.image_filename).write_bytes(PNG_BYTES)

    response = unauth_client.get(f"/gallery/photos/{photo.id}/image")

    assert response.status_code == 200
    assert response.content == PNG_BYTES
    assert response.headers["content-type"] == "image/png"


@pytest.mark.parametrize(
    ("status", "is_deleted"),
    [
        (GalleryPhotoStatus.pending, False),
        (GalleryPhotoStatus.rejected, False),
        (GalleryPhotoStatus.approved, True),
    ],
)
def test_public_image_hides_non_public_photos(
    unauth_client, session, user, tmp_path, monkeypatch, status, is_deleted
):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    photo = make_photo(
        session,
        user,
        filename="private.png",
        status=status,
        is_deleted=is_deleted,
    )
    (tmp_path / photo.image_filename).write_bytes(PNG_BYTES)

    assert unauth_client.get(f"/gallery/photos/{photo.id}/image").status_code == 404


def test_public_image_returns_404_for_unknown_photo_or_missing_file(
    unauth_client, session, user, tmp_path, monkeypatch
):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    photo = make_photo(
        session,
        user,
        filename="missing.png",
        status=GalleryPhotoStatus.approved,
    )

    assert unauth_client.get(f"/gallery/photos/{photo.id}/image").status_code == 404
    assert unauth_client.get("/gallery/photos/999999/image").status_code == 404
