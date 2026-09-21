from datetime import timedelta

import pytest
from sqlmodel import select

from models.gallery_photo import (
    PHOTO_APPROVAL_POINTS,
    GalleryPhoto,
    GalleryPhotoPoints,
    GalleryPhotoStatus,
    Semester,
)
from models.user.user_enums import Role
from services.time_services import utcnow


def make_photo(session, user, *, status=GalleryPhotoStatus.pending, reviewer_id=None, reviewed_at=None):
    photo = GalleryPhoto(
        submitted_by_user_id=user.id,
        image_filename="photo.png",
        semester=Semester.spring,
        year=2026,
        status=status,
        reviewed_by_user_id=reviewer_id,
        reviewed_at=reviewed_at,
    )
    session.add(photo)
    session.commit()
    session.refresh(photo)
    return photo


def test_reviewer_approves_pending_photo_with_overrides(client, session, user):
    user.role = Role.comm_director
    session.add(user)
    session.commit()
    photo = make_photo(session, user)

    response = client.patch(
        f"/gallery/admin/photos/{photo.id}/update",
        json={"decision": "approved", "semester": "fall", "year": 2027},
    )

    assert response.status_code == 200
    session.refresh(photo)
    assert photo.status == GalleryPhotoStatus.approved
    assert photo.semester == Semester.fall
    assert photo.year == 2027
    assert photo.reviewed_by_user_id == user.id
    assert photo.reviewed_at is not None
    assert response.json() == {"id": photo.id, "status": "approved", "semester": "fall", "year": 2027}


def test_approval_awards_points_only_once_and_rejection_does_not_revoke_them(client, session, user):
    user.role = Role.comm_director
    starting_points = user.points
    session.add(user)
    session.commit()
    photo = make_photo(session, user)

    assert client.patch(
        f"/gallery/admin/photos/{photo.id}/update",
        json={"decision": "approved"},
    ).status_code == 200

    session.refresh(user)
    awards = session.exec(
        select(GalleryPhotoPoints).where(GalleryPhotoPoints.gallery_photo_id == photo.id)
    ).all()
    assert user.points == starting_points + PHOTO_APPROVAL_POINTS
    assert len(awards) == 1
    assert awards[0].submitted_by_user_id == user.id
    assert awards[0].points_awarded == PHOTO_APPROVAL_POINTS

    # Repeating approval, rejecting, and approving again must not mint another
    # permanent award for the same photo.
    for decision in ("approved", "rejected", "approved"):
        assert client.patch(
            f"/gallery/admin/photos/{photo.id}/update",
            json={"decision": decision},
        ).status_code == 200

    session.refresh(user)
    awards = session.exec(
        select(GalleryPhotoPoints).where(GalleryPhotoPoints.gallery_photo_id == photo.id)
    ).all()
    assert user.points == starting_points + PHOTO_APPROVAL_POINTS
    assert len(awards) == 1


def test_soft_delete_preserves_previously_awarded_points(client, session, user):
    user.role = Role.president
    starting_points = user.points
    session.add(user)
    session.commit()
    photo = make_photo(session, user)

    assert client.patch(
        f"/gallery/admin/photos/{photo.id}/update",
        json={"decision": "approved"},
    ).status_code == 200
    assert client.delete(f"/gallery/admin/photos/{photo.id}").status_code == 204

    session.refresh(user)
    session.refresh(photo)
    award = session.exec(
        select(GalleryPhotoPoints).where(GalleryPhotoPoints.gallery_photo_id == photo.id)
    ).one()
    assert photo.is_deleted is True
    assert user.points == starting_points + PHOTO_APPROVAL_POINTS
    assert award.points_awarded == PHOTO_APPROVAL_POINTS


@pytest.mark.parametrize(
    ("current_status", "new_status"),
    [
        (GalleryPhotoStatus.approved, GalleryPhotoStatus.rejected),
        (GalleryPhotoStatus.rejected, GalleryPhotoStatus.approved),
    ],
)
def test_reviewer_can_reverse_review_decision(client, session, user, current_status, new_status):
    user.role = Role.vpi
    session.add(user)
    session.commit()
    previous_reviewed_at = utcnow() - timedelta(days=1)
    photo = make_photo(
        session,
        user,
        status=current_status,
        reviewer_id=user.id,
        reviewed_at=previous_reviewed_at,
    )

    response = client.patch(
        f"/gallery/admin/photos/{photo.id}/update",
        json={"decision": new_status.value},
    )

    assert response.status_code == 200
    session.refresh(photo)
    assert photo.status == new_status
    assert photo.reviewed_by_user_id == user.id
    assert photo.reviewed_at > previous_reviewed_at


def test_unchanged_review_does_not_replace_reviewer_or_time(client, session, user):
    user.role = Role.president
    session.add(user)
    session.commit()
    previous_reviewed_at = utcnow() - timedelta(days=1)
    photo = make_photo(
        session,
        user,
        status=GalleryPhotoStatus.approved,
        reviewer_id=user.id,
        reviewed_at=previous_reviewed_at,
    )
    stored_reviewed_at = photo.reviewed_at

    response = client.patch(
        f"/gallery/admin/photos/{photo.id}/update",
        json={"decision": "approved"},
    )

    assert response.status_code == 200
    session.refresh(photo)
    assert photo.status == GalleryPhotoStatus.approved
    assert photo.reviewed_at == stored_reviewed_at


def test_member_cannot_review_photo(client, session, user):
    photo = make_photo(session, user)

    response = client.patch(
        f"/gallery/admin/photos/{photo.id}/update",
        json={"decision": "approved"},
    )

    assert response.status_code == 403
    session.refresh(photo)
    assert photo.status == GalleryPhotoStatus.pending


def test_review_requires_authentication(unauth_client):
    response = unauth_client.patch(
        "/gallery/admin/photos/1/update",
        json={"decision": "approved"},
    )

    assert response.status_code == 401


def test_review_rejects_invalid_decision_and_missing_photo(client, session, user):
    user.role = Role.comm_director
    session.add(user)
    session.commit()

    assert client.patch(
        "/gallery/admin/photos/999999/update",
        json={"decision": "approved"},
    ).status_code == 404
    assert client.patch(
        "/gallery/admin/photos/999999/update",
        json={"decision": "pending"},
    ).status_code == 422
