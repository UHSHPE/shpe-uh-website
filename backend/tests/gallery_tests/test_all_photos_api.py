from models.gallery_photo import GalleryPhotoStatus
from models.user.user_enums import Role
from services.time_services import utcnow
from tests.conftest import make_user
from tests.gallery_tests.helpers import make_gallery_photo


def test_all_photos_includes_pending_without_reviewer_and_approved_with_reviewer(client, session, user):
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
        reviewer_id=user.id,
        reviewed_at=utcnow(),
    )

    response = client.get("/gallery/admin/photos")

    assert response.status_code == 200
    photos = {photo["id"]: photo for photo in response.json()}
    assert set(photos) == {pending.id, approved.id}
    assert photos[pending.id]["submitter_name"] == "Photo Member"
    assert photos[pending.id]["reviewer_name"] is None
    assert photos[pending.id]["reviewed_at"] is None
    assert photos[approved.id]["reviewer_name"] == "Test User"
    assert photos[approved.id]["reviewed_at"] == approved.reviewed_at.isoformat()

    pending_response = client.get("/gallery/admin/photos?status=pending")
    approved_response = client.get("/gallery/admin/photos?status=approved")
    rejected_response = client.get("/gallery/admin/photos?status=rejected")

    assert [photo["id"] for photo in pending_response.json()] == [pending.id]
    assert [photo["id"] for photo in approved_response.json()] == [approved.id]
    assert rejected_response.json() == []
    assert client.get("/gallery/admin/photos?status=invalid").status_code == 422
