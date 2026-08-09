"""Deployment-facing behavior: health probes, the CORS allowlist, API docs
exposure, the production config gate that refuses to boot a misconfigured
server, and the guard that keeps seed.py off a deployed database."""
import pytest

import main
from config import is_production, square_is_production
from database import assert_local_database
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


# --- what counts as production ---

@pytest.mark.parametrize(
    "value",
    ["production", "production ", " production", "  production  ", "Production", "PRODUCTION\n"],
)
def test_padded_or_miscased_environment_still_reads_as_production(monkeypatch, value):
    """A pasted dashboard value carrying whitespace is the most common way an
    env var goes wrong, and it used to disable the payment guards while
    leaving every visible production signal intact."""
    monkeypatch.setenv("ENVIRONMENT", value)

    assert is_production() is True


@pytest.mark.parametrize("value", ["", " ", "prod", "development", "staging", "productionx"])
def test_other_environment_values_are_not_production(monkeypatch, value):
    monkeypatch.setenv("ENVIRONMENT", value)

    assert is_production() is False


def test_unset_environment_is_not_production(monkeypatch):
    monkeypatch.delenv("ENVIRONMENT", raising=False)

    assert is_production() is False


def test_square_environment_defaults_to_sandbox(monkeypatch):
    """An unset value must never mean live charges."""
    monkeypatch.delenv("SQUARE_ENVIRONMENT", raising=False)

    assert square_is_production() is False


@pytest.mark.parametrize("value", ["production", "production ", "Production"])
def test_padded_square_environment_reads_as_production(monkeypatch, value):
    monkeypatch.setenv("SQUARE_ENVIRONMENT", value)

    assert square_is_production() is True


# --- API docs exposure ---

def test_docs_are_served_outside_production(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "")

    assert docs_urls() == {
        "docs_url": "/docs",
        "redoc_url": "/redoc",
        "openapi_url": "/openapi.json",
    }


@pytest.mark.parametrize("value", ["production", "production "])
def test_production_disables_docs_redoc_and_the_schema(monkeypatch, value):
    """openapi_url has to go too: /docs and /redoc only render it, so leaving
    the schema up means the interactive console is one paste away."""
    monkeypatch.setenv("ENVIRONMENT", value)

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
    # Square and Drive read their own vars at call time; stub the checks
    # themselves so these tests never depend on real credentials. Drive is
    # stubbed rather than set via env because conftest's autouse
    # disable_drive_sync clears all four GDRIVE_* vars for every test.
    monkeypatch.setattr(main.square_services, "is_configured", lambda: True)
    monkeypatch.setattr(main.drive_services, "is_configured", lambda: True)


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


def test_unconfigured_drive_refuses_to_boot(monkeypatch):
    """Resumes carry PSIDs and phone numbers, and an unconfigured Drive delete
    cannot remove the Drive copy. Without this the instance boots green and
    every deletion request reports success while the file survives."""
    _production_env(monkeypatch)
    monkeypatch.setattr(main.drive_services, "is_configured", lambda: False)

    with pytest.raises(RuntimeError, match="GDRIVE_RESUME_FOLDER_ID"):
        assert_production_config()


def test_padded_environment_still_enforces_the_gate(monkeypatch):
    """The finding this normalization exists for. With a trailing space on
    ENVIRONMENT the gate used to return without checking anything, so the app
    booted green with no Square credentials — and charge_card then simulated
    every charge, meaning free merch and free dues, while /docs stayed hidden
    and seed.py still refused, so both visible signals said production."""
    _production_env(monkeypatch, ENVIRONMENT="production ")
    monkeypatch.setattr(main.square_services, "is_configured", lambda: False)

    with pytest.raises(RuntimeError, match="SQUARE_ACCESS_TOKEN"):
        assert_production_config()


def test_padded_square_environment_still_boots(monkeypatch):
    """The mirror image, which failed closed instead: a padded value made the
    gate demand SQUARE_ENVIRONMENT=production when it had in fact been set."""
    _production_env(monkeypatch, SQUARE_ENVIRONMENT="production ")

    assert assert_production_config() is None


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


# --- seed.py's non-local database guard ---

def test_docker_compose_default_url_is_accepted():
    url = "postgresql+psycopg://shpe:shpe_dev_password@localhost:5433/shpe"

    assert assert_local_database(url) is None


def test_test_database_is_accepted():
    url = "postgresql+psycopg://shpe:shpe_dev_password@127.0.0.1:5433/shpe_test"

    assert assert_local_database(url) is None


def test_unix_socket_url_is_accepted():
    assert assert_local_database("postgresql+psycopg:///shpe?host=/tmp") is None


def test_remote_host_is_refused_even_with_environment_unset(monkeypatch):
    """The finding this guard exists for. ENVIRONMENT is the documented
    local-dev default (unset), so seed.py's other guard passes — the target
    database is the only thing that reveals this is production."""
    monkeypatch.delenv("ENVIRONMENT", raising=False)
    url = "postgresql+psycopg://u:p@containers-us-west-9.railway.app:7233/railway"

    with pytest.raises(RuntimeError, match="is not local"):
        assert_local_database(url)


def test_railway_internal_host_is_refused():
    url = "postgresql+psycopg://u:p@postgres.railway.internal:5432/shpe"

    with pytest.raises(RuntimeError, match="is not local"):
        assert_local_database(url)


def test_unexpected_database_name_on_a_local_host_is_refused():
    """The second layer: right host, wrong database. Catches a loopback tunnel
    or a stray local instance holding something other than the dev db."""
    url = "postgresql+psycopg://shpe:shpe_dev_password@localhost:5433/production"

    with pytest.raises(RuntimeError, match="is not one of"):
        assert_local_database(url)


def test_socket_url_naming_a_remote_host_in_the_query_is_refused():
    """libpq accepts a hostname in ?host=, where make_url reports host=None —
    without this it would read as a local socket."""
    url = "postgresql+psycopg:///shpe?host=postgres.railway.internal"

    with pytest.raises(RuntimeError, match="is not local"):
        assert_local_database(url)


def test_no_argument_falls_back_to_the_resolved_database_url(monkeypatch):
    """seed.py calls this with no argument, so the fallback to the module's
    own DATABASE_URL is the path that actually runs. Patched rather than read
    from the ambient .env so the test doesn't depend on a developer's config."""
    monkeypatch.setattr(
        "database.DATABASE_URL",
        "postgresql+psycopg://u:p@postgres.railway.internal:5432/railway",
    )

    with pytest.raises(RuntimeError, match="is not local"):
        assert_local_database()
