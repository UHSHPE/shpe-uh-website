"""Deployment-facing behavior: health probes, the CORS allowlist, API docs
exposure, and the production config gate that refuses to boot a misconfigured
server."""
import pytest

import main
from main import assert_production_config, cors_origins, docs_urls


# --- health probes ---

def test_health_is_ok_without_touching_the_db(client):
    res = client.get("/health")

    assert res.status_code == 200
    assert res.json() == {"status": "ok"}


def test_health_db_reports_db_reachable(client):
    res = client.get("/health/db")

    assert res.status_code == 200
    assert res.json()["db"] == "ok"


# --- CORS allowlist ---

def test_cors_defaults_to_the_vite_dev_server(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.delenv("FRONTEND_URL", raising=False)

    assert cors_origins() == ["http://localhost:5173"]


def test_cors_falls_back_to_frontend_url(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    monkeypatch.setenv("FRONTEND_URL", "https://shpeuh.org")

    assert cors_origins() == ["https://shpeuh.org"]


def test_cors_accepts_a_list_and_strips_trailing_slashes(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "https://shpeuh.org/, https://www.shpeuh.org")

    assert cors_origins() == ["https://shpeuh.org", "https://www.shpeuh.org"]


def test_unlisted_origin_is_not_allowed(client):
    """Pins the absence of allow_origin_regex. Starlette matches that pattern
    with fullmatch, so anything broad enough for our own Vercel previews also
    matches a stranger's Vercel project — this fails if one is ever re-added."""
    res = client.get("/health", headers={"Origin": "https://attacker.vercel.app"})

    assert "access-control-allow-origin" not in res.headers


# --- API docs exposure ---

def test_docs_are_served_outside_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "")

    assert docs_urls() == {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }


def test_production_disables_docs_redoc_and_the_schema(monkeypatch):
    """openapi_url has to go too: /docs and /redoc only render it, so leaving
    the schema up means the interactive console is one paste away."""
    monkeypatch.setenv("ENVIRONMENT", "production")

    assert docs_urls() == {
        "docs_url": None,
        "redoc_url": None,
        "openapi_url": None,
    }


# --- production config gate ---

def _production_env(monkeypatch, **overrides):
    env = {
        "ENVIRONMENT": "production",
        "SECRET_KEY": "not-the-dev-key",
        "SMTP_HOST": "smtp-relay.example.com",
        "SQUARE_ENVIRONMENT": "production",
        "CORS_ORIGINS": "https://shpeuh.org",
    }
    env.update(overrides)
    for key, value in env.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    # Square reads its own vars at call time; stub the check itself so these
    # tests never depend on real credentials.
    monkeypatch.setattr(main.square_services, "is_configured", lambda: True)


def test_non_production_never_raises(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "")

    assert assert_production_config() is None


def test_fully_configured_production_boots(monkeypatch):
    _production_env(monkeypatch)

    assert assert_production_config() is None


@pytest.mark.parametrize(
    "missing_var, expected_fragment",
    [
        ("SECRET_KEY", "SECRET_KEY"),
        ("SMTP_HOST", "SMTP_HOST"),
    ],
)
def test_missing_required_var_refuses_to_boot(monkeypatch, missing_var, expected_fragment):
    _production_env(monkeypatch, **{missing_var: None})

    with pytest.raises(RuntimeError, match=expected_fragment):
        assert_production_config()


def test_sandbox_square_refuses_to_boot(monkeypatch):
    _production_env(monkeypatch, SQUARE_ENVIRONMENT="sandbox")

    with pytest.raises(RuntimeError, match="SQUARE_ENVIRONMENT=production"):
        assert_production_config()


def test_unconfigured_square_refuses_to_boot(monkeypatch):
    _production_env(monkeypatch)
    monkeypatch.setattr(main.square_services, "is_configured", lambda: False)

    with pytest.raises(RuntimeError, match="SQUARE_ACCESS_TOKEN"):
        assert_production_config()


def test_localhost_cors_refuses_to_boot(monkeypatch):
    """The quiet one: without this the deploy goes green and then every
    browser call fails CORS, with nothing in the server logs to explain it."""
    _production_env(monkeypatch, CORS_ORIGINS="http://localhost:5173")

    with pytest.raises(RuntimeError, match="still points at localhost"):
        assert_production_config()


def test_forgotten_cors_var_refuses_to_boot(monkeypatch):
    # Neither CORS_ORIGINS nor FRONTEND_URL set → falls back to localhost.
    _production_env(monkeypatch, CORS_ORIGINS=None, FRONTEND_URL=None)

    with pytest.raises(RuntimeError, match="still points at localhost"):
        assert_production_config()
