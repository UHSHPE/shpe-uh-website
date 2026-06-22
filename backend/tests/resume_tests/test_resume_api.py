import pytest

import routes.resume_routes as resume_routes
from models.user.user_schemas import UserOut

PDF_BYTES = b"%PDF-1.4\n%fake pdf body\n"


@pytest.fixture
def resume_dir(monkeypatch, tmp_path):
    """Point resume storage at a throwaway dir so tests never touch real uploads."""
    target = tmp_path / "resumes"
    monkeypatch.setattr(resume_routes, "RESUME_DIR", target)
    return target


# --- POST /me/resume ---

def test_upload_valid_pdf_persists_and_returns_filename(client, resume_dir, user):
    res = client.post(
        "/me/resume",
        files={"file": ("my_resume.pdf", PDF_BYTES, "application/pdf")},
    )

    assert res.status_code == 200
    assert res.json()["resume_filename"] == "my_resume.pdf"
    assert (resume_dir / f"user_{user.id}.pdf").read_bytes() == PDF_BYTES


def test_upload_sets_resume_filename_on_user(client, resume_dir, session, user):
    client.post(
        "/me/resume",
        files={"file": ("my_resume.pdf", PDF_BYTES, "application/pdf")},
    )

    session.refresh(user)
    assert user.resume_filename == "my_resume.pdf"


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
