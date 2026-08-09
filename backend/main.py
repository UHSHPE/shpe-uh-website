import asyncio
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from services import square_services

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session, text

from config import is_production, square_is_production
from database import create_db, engine
from services.body_limit import DEFAULT_MAX_BODY_BYTES, BodyLimitMiddleware
from services.dependencies import SessionDependencies
from services.rate_limit import limiter
from services.reminder_services import send_due_reminders
from services.event_tracker_services import sync_events

from routes import admin_routes, auth_routes, committee_routes, event_routes, notification_routes, pw_reset_routes, resume_routes, shop_routes

# The imports above already pull .env in as a side effect (database.py calls
# this too), but main.py reads env vars of its own — including one at import
# time, in docs_urls() — so it must not depend on another module's import
# order to have loaded them.
load_dotenv()

REMINDER_CHECK_SECONDS = 60

SYNC_TZ = ZoneInfo("America/Chicago")   # the sheet's timezone
SYNC_HOUR = 6                           # 6 AM Central — daily event-sheet sync time

def dispatch_due_reminders():
    with Session(engine) as session:
        send_due_reminders(session)

async def reminder_loop():
    while True:
        try:
            await asyncio.to_thread(dispatch_due_reminders)
        except Exception:
            logging.exception("Reminder dispatch failed")
        await asyncio.sleep(REMINDER_CHECK_SECONDS)

def dispatch_event_sync():
    with Session(engine) as session:
        sync_events(session)

def seconds_until(hour: int) -> float:
    """Seconds from now until the next occurrence of `hour` Central."""
    now = datetime.now(SYNC_TZ)
    target = now.replace(hour=hour, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)   # already past that hour today → aim for tomorrow
    return (target - now).total_seconds()

async def event_sync_loop():
    while True:
        try:
            await asyncio.to_thread(dispatch_event_sync)
        except Exception:
            logging.exception("Event sheet sync failed")
        await asyncio.sleep(seconds_until(SYNC_HOUR))

# Inits the DB and starts the background loops (reminder emails + daily event-sheet sync)
@asynccontextmanager
async def lifespan(app):
    assert_production_config()
    create_db()
    reminder_task = asyncio.create_task(reminder_loop())
    event_sync_task = asyncio.create_task(event_sync_loop())
    yield
    reminder_task.cancel()
    event_sync_task.cancel()

def cors_origins() -> list[str]:
    """Browser origins allowed to call the API.

    CORS_ORIGINS is a comma-separated allowlist; it falls back to
    FRONTEND_URL (already set for the links in verification/reset emails) and
    finally to the Vite dev server, so local development is unchanged.
    """
    raw = (
        os.getenv("CORS_ORIGINS")
        or os.getenv("FRONTEND_URL")
        or "http://localhost:5173"
    )
    return [origin.strip().rstrip("/") for origin in raw.split(",") if origin.strip()]

def docs_urls() -> dict[str, str | None]:
    """Paths for the interactive API docs, switched off in production.

    All three go together or none of them count: /docs and /redoc are only
    renderers, and /openapi.json is the payload they fetch. Leaving the schema
    up while hiding the two HTML pages means the interactive console is one
    paste into any Swagger instance away.

    The schema is generated from the real code, so it lists every path, every
    model's field names and types, and which endpoints require auth. That is
    not a vulnerability by itself — but the privilege-escalation bug in
    tests/auth_tests/test_signup_privilege_escalation.py was reachable through
    the public /docs "Try it out" button, which is the difference it makes.

    Unlike assert_production_config() (which runs at startup, inside lifespan)
    this is read at IMPORT time, because FastAPI() is constructed at import.
    is_production() keeping the env read inside a function is what lets tests
    monkeypatch ENVIRONMENT and call docs_urls() directly instead of reloading
    the module.
    """
    if is_production():
        return {"docs_url": None, "redoc_url": None, "openapi_url": None}
    return {"docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json"}

def assert_production_config():
    if not is_production():
        return
    missing = []
    if not os.getenv("SECRET_KEY"):
        missing.append("SECRET_KEY")
    if not square_services.is_configured():
        missing.append("SQUARE_ACCESS_TOKEN / SQUARE_LOCATION_ID")
    if not os.getenv("SMTP_HOST"):
        missing.append("SMTP_HOST")
    if not square_is_production():
        missing.append("SQUARE_ENVIRONMENT=production")
    # A forgotten allowlist otherwise deploys green and then fails every
    # browser call with an opaque CORS error that leaves nothing in the logs.
    if any("localhost" in o or "127.0.0.1" in o for o in cors_origins()):
        missing.append("CORS_ORIGINS/FRONTEND_URL (still points at localhost)")
    if missing:
        raise RuntimeError(
            f"ENVIRONMENT=production but required config is missing: {', '.join(missing)}"
        )

app = FastAPI(lifespan=lifespan, **docs_urls())

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Rejects requests whose Host header isn't ours, so nobody can reach the API
# through the raw platform hostname and bypass the intended edge (which is
# also where the rate limiter gets its client IP from). Unset locally.
_allowed_hosts = os.getenv("ALLOWED_HOSTS")
if _allowed_hosts:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[h.strip() for h in _allowed_hosts.split(",") if h.strip()],
    )

def _max_body_bytes() -> int:
    """The cap for BodyLimitMiddleware. Must stay above both per-route upload
    limits (2 MB each) or valid uploads fail with the wrong error."""
    try:
        return max(1, int(os.getenv("MAX_REQUEST_BODY_BYTES", DEFAULT_MAX_BODY_BYTES)))
    except ValueError:
        return DEFAULT_MAX_BODY_BYTES


# A hard ceiling on request body size, and the ONLY layer that can stop an
# oversized upload: FastAPI parses the multipart form before it solves
# dependencies, so by the time a route handler (or its auth dependency) runs,
# the body has already been spooled to disk in full — anonymously. The
# per-route file.size checks are the second layer. See services/body_limit.py.
#
# Registered BEFORE the CORS block on purpose: add_middleware inserts at index
# 0, so the last one added ends up outermost. CORS must stay outside this, or a
# 413 goes back without CORS headers and the browser reports an opaque CORS
# failure instead of the status.
app.add_middleware(BodyLimitMiddleware, max_bytes=_max_body_bytes())

# Exact origins only. There is deliberately NO allow_origin_regex, and adding
# one back is a mistake that looks safe: Starlette matches it with re.fullmatch
# (middleware/cors.py), so a pattern broad enough to cover our Vercel preview
# URLs — ".*\.vercel\.app" was the documented example — also matches every
# OTHER person's Vercel project, and anchoring it with ^...$ changes nothing
# because fullmatch already requires the whole origin to match.
# It's survivable today only because auth is a Bearer token from localStorage,
# which is origin-scoped and unreadable by an attacker's page. allow_credentials
# is already True, so the day auth moves to cookies that stops being true.
# If a preview build ever genuinely needs the API, add its exact origin to
# CORS_ORIGINS instead.
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health", include_in_schema=False)
def health():
    """Liveness probe. Deliberately does NOT touch the database — a transient
    lock or a slow query must not make the platform kill a healthy container."""
    return {"status": "ok"}

@app.get("/health/db", include_in_schema=False)
def health_db(session: SessionDependencies):
    """Readiness check, for manual verification rather than the platform."""
    session.exec(text("SELECT 1"))
    return {"status": "ok", "db": "ok"}

app.include_router(admin_routes.router)
app.include_router(auth_routes.router)
app.include_router(committee_routes.router)
app.include_router(event_routes.router)
app.include_router(notification_routes.router)
app.include_router(pw_reset_routes.router)
app.include_router(resume_routes.router)
app.include_router(shop_routes.router)

if __name__ == "__main__":
    import uvicorn
    # The container image invokes uvicorn directly, so this block is the
    # local-dev entrypoint the README documents. Reload is forced off in
    # production so this can never start a reloading server on a live host.
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=not is_production(),
        proxy_headers=True,
    )
