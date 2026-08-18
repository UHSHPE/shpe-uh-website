"""ForwardedProtoMiddleware — restoring the request scheme behind a proxy.

The bug this exists to prevent (see services/forwarded_proto.py): behind
Railway, uvicorn accepts a plain http connection, so FastAPI built its
trailing-slash redirect as http://. The browser blocked that as mixed content
on an https:// page and the frontend reported an opaque network error, while
curl and the whole test suite saw nothing wrong.

test_redirect_location_uses_https is the regression test for that specific
failure; the rest pin the header parsing around it.
"""

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from services.forwarded_proto import ForwardedProtoMiddleware


@pytest.fixture
def proxied_app():
    """A minimal app carrying the middleware, plus a router whose route is
    declared as '/' under a prefix — the exact shape that makes the router
    answer /thing with a 307 to /thing/.
    """
    app = FastAPI()
    router = APIRouter(prefix="/thing")

    @router.get("/")
    async def listing():
        return {"ok": True}

    app.include_router(router)
    app.add_middleware(ForwardedProtoMiddleware)
    return app


@pytest.fixture
def trusted(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_IP_HEADERS", "1")


def test_redirect_location_uses_https(proxied_app, trusted):
    """The regression test: /thing 307s to /thing/, and that Location must
    carry https:// or the browser blocks it as mixed content."""
    client = TestClient(proxied_app)
    resp = client.get(
        "/thing", headers={"X-Forwarded-Proto": "https"}, follow_redirects=False
    )
    assert resp.status_code == 307
    assert resp.headers["location"].startswith("https://")


def test_redirect_stays_http_without_the_header(proxied_app, trusted):
    """No forwarded header (local dev, direct connection) changes nothing."""
    client = TestClient(proxied_app)
    resp = client.get("/thing", follow_redirects=False)
    assert resp.status_code == 307
    assert resp.headers["location"].startswith("http://")


def test_header_ignored_when_proxy_is_not_trusted(proxied_app, monkeypatch):
    """Off by default. Without TRUST_PROXY_IP_HEADERS anyone could send the
    header directly, so it must not be believed."""
    monkeypatch.delenv("TRUST_PROXY_IP_HEADERS", raising=False)
    client = TestClient(proxied_app)
    resp = client.get(
        "/thing", headers={"X-Forwarded-Proto": "https"}, follow_redirects=False
    )
    assert resp.headers["location"].startswith("http://")


def test_rightmost_entry_wins(proxied_app, trusted):
    """Mirrors client_ip's rightmost X-Forwarded-For rule: the last entry is
    the one our own edge set. A leading 'http' here is what a client trying to
    force a downgrade would inject."""
    client = TestClient(proxied_app)
    resp = client.get(
        "/thing",
        headers={"X-Forwarded-Proto": "http, https"},
        follow_redirects=False,
    )
    assert resp.headers["location"].startswith("https://")


def test_garbage_scheme_is_ignored(proxied_app, trusted):
    """An unrecognised value must not be written into the scope, where it
    would corrupt every URL the app generates."""
    client = TestClient(proxied_app)
    resp = client.get(
        "/thing",
        headers={"X-Forwarded-Proto": "javascript"},
        follow_redirects=False,
    )
    assert resp.headers["location"].startswith("http://")


def test_events_route_does_not_redirect_at_all():
    """The other half of the fix: /events is declared as '' so no redirect is
    generated in the first place. Belt and braces — the middleware makes a
    redirect survivable, this makes it unnecessary."""
    import main

    paths = {r.path for r in main.app.routes if getattr(r, "path", "") == "/events"}
    assert paths == {"/events"}
