import pytest

from models.gallery_photo import GalleryPhotoStatus, GallerySubmission
from models.user.user_enums import Role
from tests.conftest import make_user
from tests.gallery_tests.helpers import make_gallery_photo


@pytest.mark.parametrize(
    "role",
    [Role.president, Role.vpe, Role.vpi, Role.comm_director, Role.marketing_chair],
)
def test_gallery_reviewers_can_list_pending_photos(client, session, user, role):
    user.role = role
    session.add(user)
    session.commit()

    response = client.get("/gallery/admin/photos?status=pending")

    assert response.status_code == 200
    assert response.json() == []


@pytest.mark.parametrize("role", [Role.member, Role.nonmember])
def test_non_reviewers_cannot_list_pending_photos(client, session, user, role):
    user.role = role
    session.add(user)
    session.commit()

    assert client.get("/gallery/admin/photos?status=pending").status_code == 403


def test_pending_list_requires_authentication(unauth_client):
    assert unauth_client.get("/gallery/admin/photos?status=pending").status_code == 401


def test_pending_list_includes_submitter_name_but_not_approved_photos(client, session, user):
    user.role = Role.comm_director
    session.add(user)
    submitter = make_user(
        session,
        first_name="Photo",
        last_name="Member",
        cougarnet_email="photo@cougarnet.uh.edu",
        personal_email="photo@example.com",
        psid="7654321",
    )
    pending = make_gallery_photo(session, submitter, filename="pending.png")
    approved = make_gallery_photo(
        session,
        submitter,
        filename="approved.png",
        status=GalleryPhotoStatus.approved,
    )
    submission = session.get(GallerySubmission, pending.submission_id)

    response = client.get("/gallery/admin/photos?status=pending")

    assert response.status_code == 200
    assert response.json() == [
        {
            "id": pending.id,
            "submitter_name": "Photo Member",
            "submitted_at": submission.submitted_at.isoformat(),
            "semester": "spring",
            "year": 2026,
            "status": "pending",
            "reviewer_name": None,
            "reviewed_at": None,
        }
    ]
    assert "image_filename" not in response.json()[0]
