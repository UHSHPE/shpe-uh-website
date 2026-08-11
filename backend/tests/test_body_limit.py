"""BodyLimitMiddleware — the hard ceiling on request body size.

Why this layer exists at all (see services/body_limit.py): FastAPI parses the
multipart form BEFORE it solves dependencies, and Starlette's parser puts a
file part into an unbounded SpooledTemporaryFile. So an oversized upload is
written to disk in full before any route handler — or its auth dependency —
runs. The per-route file.size checks cannot reach that; only this can.
"""

import pytest
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from services.body_limit import TOO_LARGE_DETAIL, BodyLimitMiddleware

CAP = 1024  # 1 KB, so these tests don't have to move megabytes around

PDF_BYTES = b"%PDF-1.4\n%fake pdf body\n"


@pytest.fixture
def tiny_app():
    """A minimal app with a small cap. `reached` records whether the handler
    ever ran. No exception handler is registered — the middleware owns the
    413 response on its own, which is the point of test_chunked_upload_* below.
    """
    app = FastAPI()
    reached = []

    @app.post("/echo")
    async def echo(request: Request):
        body = await request.body()
        reached.append(len(body))
        return {"received": len(body)}

    app.add_middleware(BodyLimitMiddleware, max_bytes=CAP)
    app.state.reached = reached
    return app


def test_oversized_content_length_is_rejected_before_the_handler_runs(tiny_app):
    client = TestClient(tiny_app)

    res = client.post("/echo", content=b"x" * (CAP + 1))

    assert res.status_code == 413
    assert res.json()["detail"] == TOO_LARGE_DETAIL
    # The point of the whole layer: the app is never called, so nothing is
    # parsed and nothing is spooled to disk.
    assert tiny_app.state.reached == []


def test_a_body_at_the_cap_is_allowed(tiny_app):
    client = TestClient(tiny_app)

    res = client.post("/echo", content=b"x" * CAP)

    assert res.status_code == 200
    assert res.json()["received"] == CAP


def test_chunked_body_over_the_cap_is_rejected(tiny_app):
    """A chunked request carries no Content-Length, so the fast path can't see
    the size up front — the counting receive() has to catch it mid-stream.
    Passing a generator as content makes httpx send Transfer-Encoding: chunked.
    """
    client = TestClient(tiny_app)

    def chunks():
        for _ in range(4):
            yield b"x" * CAP

    res = client.post("/echo", content=chunks())

    assert res.status_code == 413
    assert res.json()["detail"] == TOO_LARGE_DETAIL


def test_ordinary_requests_are_untouched(tiny_app):
    client = TestClient(tiny_app)

    res = client.post("/echo", content=b"hello")

    assert res.status_code == 200
    assert res.json()["received"] == 5


# --- wiring on the real app ---

def test_oversized_upload_is_rejected_without_authentication(unauth_client):
    """413 rather than 401 is the proof that the rejection happens before the
    router — i.e. before get_current_user, and before the form parser writes
    the body to disk. That half of the defect needed no credentials."""
    from main import _max_body_bytes

    oversized = b"%PDF-1.4\n" + b"0" * (_max_body_bytes() + 1)

    res = unauth_client.post(
        "/me/resume",
        files={"file": ("big.pdf", oversized, "application/pdf")},
    )

    assert res.status_code == 413


def test_chunked_upload_over_the_cap_returns_413_not_a_parse_error(unauth_client):
    """Regression: a chunked oversized upload must report 413, not 400.

    Caught against a live server, not by the isolated middleware tests. On a
    route with a File body_field, FastAPI wraps the form parse in a broad
    `except Exception` that re-raises everything as HTTPException(400, "There
    was an error parsing the body") — so cutting the stream off mid-parse gets
    reported as a malformed request unless the middleware overrides the
    response. The DoS was prevented either way; the status code was the lie.
    """
    from main import _max_body_bytes

    boundary = "----probe"
    head = (
        f"--{boundary}\r\n"
        'Content-Disposition: form-data; name="file"; filename="big.pdf"\r\n'
        "Content-Type: application/pdf\r\n\r\n"
    ).encode()

    def chunked_body():
        # A generator body makes httpx use Transfer-Encoding: chunked, so there
        # is no Content-Length and the counting receive() has to catch it.
        yield head
        chunk = b"0" * 100_000
        for _ in range((_max_body_bytes() // len(chunk)) + 2):
            yield chunk

    res = unauth_client.post(
        "/me/resume",
        content=chunked_body(),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )

    assert res.status_code == 413
    assert res.json()["detail"] == TOO_LARGE_DETAIL


def test_the_cap_leaves_room_for_a_legitimate_upload(client, tmp_path, monkeypatch):
    """The global cap must sit above the per-route caps, or it would start
    rejecting valid uploads with the wrong error before they reach the route."""
    from routes import resume_routes

    monkeypatch.setattr(resume_routes, "RESUME_DIR", tmp_path)
    realistic = PDF_BYTES + b"0" * (1_500_000 - len(PDF_BYTES))

    res = client.post(
        "/me/resume",
        files={"file": ("resume.pdf", realistic, "application/pdf")},
    )

    assert res.status_code == 200
