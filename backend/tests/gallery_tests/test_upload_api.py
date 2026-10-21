from sqlmodel import select

from datetime import timedelta

import pytest
from sqlmodel import select

from models.gallery_photo import GalleryPhoto, GalleryPhotoStatus, GallerySubmission
from services import gallery_services
from services.gallery_services import (
    MAX_IMAGE_BYTES,
    MAX_PHOTOS_PER_SUBMISSION,
    MAX_SUBMISSIONS_PER_WEEK,
)
from services.time_services import get_start_of_week
from tests.conftest import make_user


PNG_BYTES = b"\x89PNG\r\n\x1a\nimage data"


@pytest.mark.parametrize("photo_count", [1, 2, 3])
def test_member_upload_creates_one_submission_with_pending_photos(
    client, session, user, tmp_path, monkeypatch, photo_count
):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)

    response = client.post(
        "/gallery/photos",
        files=[
            ("files", (f"photo-{index}.png", PNG_BYTES, "image/png"))
            for index in range(photo_count)
        ],
    )

    assert response.status_code == 201
    submission = session.exec(select(GallerySubmission)).one()
    photos = session.exec(select(GalleryPhoto)).all()
    assert response.json()["submission_id"] == submission.id
    assert response.json()["photo_ids"] == [photo.id for photo in photos]
    assert response.json()["status"] == GalleryPhotoStatus.pending.value
    assert submission.submitted_by_user_id == user.id
    assert len(photos) == photo_count
    assert all(photo.submission_id == submission.id for photo in photos)
    assert all(photo.status == GalleryPhotoStatus.pending for photo in photos)
    assert all((tmp_path / photo.image_filename).read_bytes() == PNG_BYTES for photo in photos)


def test_upload_requires_authentication(unauth_client, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)

    response = unauth_client.post(
        "/gallery/photos",
        files={"files": ("photo.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 401
    assert list(tmp_path.iterdir()) == []


def test_oversized_upload_is_rejected(client, session, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)

    response = client.post(
        "/gallery/photos",
        files={"files": ("photo.png", PNG_BYTES + b"x" * MAX_IMAGE_BYTES, "image/png")},
    )

    assert response.status_code == 413
    assert session.exec(select(GalleryPhoto)).all() == []
    assert list(tmp_path.iterdir()) == []


def test_mismatched_image_signature_is_rejected(client, session, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)

    response = client.post(
        "/gallery/photos",
        files={"files": ("photo.png", b"not a PNG", "image/png")},
    )

    assert response.status_code == 400
    assert session.exec(select(GalleryPhoto)).all() == []
    assert list(tmp_path.iterdir()) == []


def test_submission_rejects_more_than_three_photos(client, session, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)

    response = client.post(
        "/gallery/photos",
        files=[
            ("files", (f"photo-{index}.png", PNG_BYTES, "image/png"))
            for index in range(MAX_PHOTOS_PER_SUBMISSION + 1)
        ],
    )

    assert response.status_code == 400
    assert session.exec(select(GallerySubmission)).all() == []
    assert session.exec(select(GalleryPhoto)).all() == []


def test_sixth_submission_in_week_is_rejected(client, session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    start_of_week = get_start_of_week()
    session.add_all(
        [
            GallerySubmission(
                submitted_by_user_id=user.id,
                submitted_at=start_of_week + timedelta(hours=index),
            )
            for index in range(MAX_SUBMISSIONS_PER_WEEK)
        ]
    )
    session.commit()

    response = client.post(
        "/gallery/photos",
        files={"files": ("photo.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 429
    assert len(session.exec(select(GallerySubmission)).all()) == MAX_SUBMISSIONS_PER_WEEK
    assert list(tmp_path.iterdir()) == []


def test_previous_week_does_not_count_toward_limit(client, session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    session.add_all(
        [
            GallerySubmission(
                submitted_by_user_id=user.id,
                submitted_at=get_start_of_week() - timedelta(seconds=index + 1),
            )
            for index in range(MAX_SUBMISSIONS_PER_WEEK)
        ]
    )
    session.commit()

    response = client.post(
        "/gallery/photos",
        files={"files": ("photo.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201
    assert len(session.exec(select(GallerySubmission)).all()) == MAX_SUBMISSIONS_PER_WEEK + 1


def test_weekly_limit_is_per_member(client, session, user, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)
    other_user = make_user(
        session,
        cougarnet_email="gallery.other@cougarnet.uh.edu",
        personal_email="gallery.other@example.com",
        psid="7654321",
    )
    session.add_all(
        [
            GallerySubmission(submitted_by_user_id=other_user.id)
            for _ in range(MAX_SUBMISSIONS_PER_WEEK)
        ]
    )
    session.commit()

    response = client.post(
        "/gallery/photos",
        files={"files": ("photo.png", PNG_BYTES, "image/png")},
    )

    assert response.status_code == 201
    created = session.get(GallerySubmission, response.json()["submission_id"])
    assert created.submitted_by_user_id == user.id


def test_invalid_photo_rejects_entire_batch(client, session, tmp_path, monkeypatch):
    monkeypatch.setattr(gallery_services, "GALLERY_IMAGE_DIR", tmp_path)

    response = client.post(
        "/gallery/photos",
        files=[
            ("files", ("valid.png", PNG_BYTES, "image/png")),
            ("files", ("invalid.png", b"not a PNG", "image/png")),
        ],
    )

    assert response.status_code == 400
    assert session.exec(select(GallerySubmission)).all() == []
    assert session.exec(select(GalleryPhoto)).all() == []
    assert list(tmp_path.iterdir()) == []
