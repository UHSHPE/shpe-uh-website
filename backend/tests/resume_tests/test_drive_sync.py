import pytest

import routes.resume_routes as resume_routes
from services import drive_services

PDF_BYTES = b"%PDF-1.4\n%fake pdf body\n"


@pytest.fixture
def resume_dir(monkeypatch, tmp_path):
    """Point resume storage at a throwaway dir so tests never touch real uploads."""
    target = tmp_path / "resumes"
    monkeypatch.setattr(resume_routes, "RESUME_DIR", target)
    return target


@pytest.fixture
def drive_calls(monkeypatch):
    """Stub the Drive sync functions and record how the routes call them."""
    calls = {"uploads": [], "deletes": [], "upload_result": "drive-id-1", "delete_result": True}

    def fake_upload(existing_file_id, name, content):
        calls["uploads"].append((existing_file_id, name, content))
        return calls["upload_result"]

    def fake_delete(file_id):
        calls["deletes"].append(file_id)
        return calls["delete_result"]

    monkeypatch.setattr(resume_routes, "upload_resume_to_drive", fake_upload)
    monkeypatch.setattr(resume_routes, "delete_resume_from_drive", fake_delete)
    return calls


def upload(client, name="my_resume.pdf"):
    return client.post("/me/resume", files={"file": (name, PDF_BYTES, "application/pdf")})


# --- upload syncs to Drive ---

def test_upload_sends_resume_to_drive_and_stores_file_id(client, resume_dir, drive_calls, session, user):
    res = upload(client)

    assert res.status_code == 200
    # Drive copy uses the canonical First_Last_PSID.pdf name, not the uploaded one.
    assert drive_calls["uploads"] == [(None, "Test_User_1234567.pdf", PDF_BYTES)]
    session.refresh(user)
    assert user.resume_drive_file_id == "drive-id-1"


def test_reupload_replaces_the_existing_drive_file(client, resume_dir, drive_calls, session, user):
    upload(client)
    upload(client, name="my_resume_v2.pdf")

    # Second call passes the stored id so Drive updates in place (old copy replaced).
    assert drive_calls["uploads"][1] == ("drive-id-1", "Test_User_1234567.pdf", PDF_BYTES)
    session.refresh(user)
    assert user.resume_drive_file_id == "drive-id-1"


def test_drive_upload_failure_does_not_break_the_upload(client, resume_dir, drive_calls, session, user):
    drive_calls["upload_result"] = None  # Drive down / misconfigured

    res = upload(client)

    assert res.status_code == 200  # local copy is still the source of truth
    session.refresh(user)
    assert user.resume_filename == "Test_User_1234567.pdf"
    assert user.resume_drive_file_id is None


def test_invalid_upload_never_touches_drive(client, resume_dir, drive_calls):
    client.post("/me/resume", files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert drive_calls["uploads"] == []


# --- delete syncs to Drive ---

def test_delete_removes_the_drive_copy_and_clears_the_id(client, resume_dir, drive_calls, session, user):
    upload(client)

    res = client.delete("/me/resume")

    assert res.status_code == 204
    assert drive_calls["deletes"] == ["drive-id-1"]
    session.refresh(user)
    assert user.resume_drive_file_id is None
    assert user.resume_filename is None


def test_failed_drive_delete_keeps_the_id_for_later_cleanup(client, resume_dir, drive_calls, session, user):
    upload(client)
    drive_calls["delete_result"] = False  # Drive unreachable

    res = client.delete("/me/resume")

    assert res.status_code == 204  # local delete still succeeds
    session.refresh(user)
    assert user.resume_filename is None
    # Id is kept so the next upload replaces the orphaned Drive file instead of duplicating it.
    assert user.resume_drive_file_id == "drive-id-1"


# --- dev mode (no GDRIVE_* env vars, guaranteed by conftest's autouse
# disable_drive_sync fixture) is a safe no-op ---

def test_upload_without_drive_config_is_a_noop():
    assert drive_services.upload_resume_to_drive(None, "x.pdf", PDF_BYTES) is None


def test_delete_without_drive_config_reports_failure_so_the_id_is_kept():
    """Deliberately NOT the upload no-op's shape. The caller nulls the file id
    on success, so returning True here would strand a real Drive copy with
    nothing pointing at it — and every retry after that would short-circuit on
    the `not file_id` branch and report success forever."""
    assert drive_services.delete_resume_from_drive("some-id") is False


def test_delete_with_nothing_in_drive_still_reports_success():
    """The other unconfigured path, which is genuinely a no-op: no file id
    means no Drive copy to lose, which is every local dev run and every test."""
    assert drive_services.delete_resume_from_drive(None) is True


def test_drive_config_dropped_after_upload_keeps_the_pointer(client, resume_dir, session, user):
    """The F5 finding. Drive was configured when the resume was uploaded and is
    gone by the time it's deleted — a redeploy, a rotated credential. Runs the
    REAL delete_resume_from_drive (no drive_calls stub), unconfigured via the
    autouse disable_drive_sync fixture. If the id is cleared here, the Drive
    copy is orphaned permanently and nothing in the app can reach it again."""
    upload(client)
    user.resume_drive_file_id = "drive-id-1"  # as a configured instance would have left it
    session.add(user)
    session.commit()

    res = client.delete("/me/resume")

    assert res.status_code == 204  # local delete still succeeds
    session.refresh(user)
    assert user.resume_filename is None
    assert user.resume_drive_file_id == "drive-id-1"


def test_oauth_env_vars_count_as_configured(monkeypatch):
    # Credentials are built offline — no network here.
    monkeypatch.setenv("GDRIVE_RESUME_FOLDER_ID", "folder-1")
    monkeypatch.setenv("GDRIVE_OAUTH_CLIENT_ID", "id")
    monkeypatch.setenv("GDRIVE_OAUTH_CLIENT_SECRET", "secret")
    monkeypatch.setenv("GDRIVE_OAUTH_REFRESH_TOKEN", "refresh")
    config = drive_services._drive_config()
    assert config is not None
    creds, folder_id = config
    assert folder_id == "folder-1"
    assert creds.refresh_token == "refresh"
