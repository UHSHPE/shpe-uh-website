import pytest

import routes.resume_routes as resume_routes
from models.user.user_schemas import UserOut
from services.rate_limit import UPLOAD_LIMIT, limit_count

PDF_BYTES = b"%PDF-1.4\n%fake pdf body\n"


@pytest.fixture
def resume_dir(monkeypatch, tmp_path):
    """Point resume storage at a throwaway dir so tests never touch real uploads."""
    target = tmp_path / "resumes"
    monkeypatch.setattr(resume_routes, "RESUME_DIR", target)
    return target


# --- POST /me/resume ---

def test_upload_valid_pdf_persists_and_returns_canonical_name(client, resume_dir, user):
    res = client.post(
        "/me/resume",
        files={"file": ("my_resume.pdf", PDF_BYTES, "application/pdf")},
    )

    assert res.status_code == 200
    # The uploaded filename is discarded — resumes are renamed First_Last_PSID.pdf.
    assert res.json()["resume_filename"] == "Test_User_1234567.pdf"
    assert (resume_dir / f"user_{user.id}.pdf").read_bytes() == PDF_BYTES


def test_upload_sets_resume_filename_on_user(client, resume_dir, session, user):
    client.post(
        "/me/resume",
        files={"file": ("my_resume.pdf", PDF_BYTES, "application/pdf")},
    )

    session.refresh(user)
    assert user.resume_filename == "Test_User_1234567.pdf"


def test_multi_word_names_join_with_underscores(session):
    from routes.resume_routes import _canonical_resume_name
    from tests.conftest import make_user

    user = make_user(
        session,
        first_name="Mary Ann",
        last_name="De La Cruz",
        cougarnet_email="maryann@cougarnet.uh.edu",
        personal_email="maryann@gmail.com",
        psid="7654321",
    )
    assert _canonical_resume_name(user) == "Mary_Ann_De_La_Cruz_7654321.pdf"


def test_upload_over_2mb_is_rejected_with_413(client, resume_dir):
    big = PDF_BYTES + b"0" * (2 * 1024 * 1024)
    res = client.post(
        "/me/resume",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert res.status_code == 413


def test_size_is_checked_before_the_body_is_read(client, resume_dir, monkeypatch):
    """The cap must be enforced against file.size, BEFORE read().

    Reading first is what makes an oversized upload dangerous: read() with no
    argument copies the whole spooled body into one bytes object, so a large
    upload lands in resident memory and OOM-kills the worker — and the Dockerfile
    pins --workers 1, so that process is the entire API. Blowing up inside read()
    is how this test notices the check has moved back below it.
    """
    from starlette.datastructures import UploadFile

    async def boom(self, size=-1):
        raise AssertionError("read() ran before the size check")

    monkeypatch.setattr(UploadFile, "read", boom)

    # Over the route's 2 MB cap but under the global middleware cap, so this
    # exercises the handler's own check rather than being stopped at the edge.
    big = PDF_BYTES + b"0" * (2 * 1024 * 1024)
    res = client.post(
        "/me/resume",
        files={"file": ("big.pdf", big, "application/pdf")},
    )
    assert res.status_code == 413


def test_upload_is_rate_limited(client, resume_dir):
    # Derived from the configured limit (RATE_LIMIT_UPLOAD) rather than
    # hardcoded, so retuning the limit doesn't break this test.
    for _ in range(limit_count(UPLOAD_LIMIT)):
        client.post(
            "/me/resume",
            files={"file": ("my_resume.pdf", PDF_BYTES, "application/pdf")},
        )

    res = client.post(
        "/me/resume",
        files={"file": ("my_resume.pdf", PDF_BYTES, "application/pdf")},
    )
    assert res.status_code == 429


def test_user_out_exposes_resume_filename():
    # Locks the API contract: /me (UserOut) surfaces the resume to the frontend.
    assert "resume_filename" in UserOut.model_fields


def test_upload_non_pdf_is_rejected(client, resume_dir):
    res = client.post(
        "/me/resume",
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )
    assert res.status_code == 400


def test_upload_pdf_name_but_wrong_magic_bytes_is_rejected(client, resume_dir):
    res = client.post(
        "/me/resume",
        files={"file": ("fake.pdf", b"not really a pdf", "application/pdf")},
    )
    assert res.status_code == 400


# --- GET /me/resume ---

def test_get_resume_returns_the_pdf(client, resume_dir):
    client.post(
        "/me/resume",
        files={"file": ("my_resume.pdf", PDF_BYTES, "application/pdf")},
    )

    res = client.get("/me/resume")
    assert res.status_code == 200
    assert res.headers["content-type"] == "application/pdf"
    assert res.content == PDF_BYTES


def test_get_resume_when_none_returns_404(client, resume_dir):
    res = client.get("/me/resume")
    assert res.status_code == 404


# --- DELETE /me/resume ---

def test_delete_resume_clears_file_and_field(client, resume_dir, session, user):
    client.post(
        "/me/resume",
        files={"file": ("my_resume.pdf", PDF_BYTES, "application/pdf")},
    )

    res = client.delete("/me/resume")
    assert res.status_code == 204
    assert not (resume_dir / f"user_{user.id}.pdf").exists()

    assert client.get("/me/resume").status_code == 404
    session.refresh(user)
    assert user.resume_filename is None
