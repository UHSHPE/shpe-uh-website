"""Construct the API application, wire middleware, and register routes."""

import asyncio
import os
from services import drive_services, square_services

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import cors_origins, docs_urls, is_production, max_body_bytes, square_is_production
from database import create_db
from services.background_jobs import dues_sync_loop, event_sync_loop, reminder_loop
from services.body_limit import BodyLimitMiddleware
from services.forwarded_proto import ForwardedProtoMiddleware
from services.rate_limit import limiter

from routes import admin_routes, auth_routes, committee_routes, dues_routes, event_routes, health_routes, leaderboard_routes, notification_routes, pw_reset_routes, resume_routes, shop_routes


@asynccontextmanager
async def lifespan(app):
    """Start background jobs and cancel them when the application stops."""
    assert_production_config()
    create_db()
    tasks = [asyncio.create_task(job()) for job in (reminder_loop, event_sync_loop, dues_sync_loop)]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


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
    # Drive is the one dev-mode no-op whose absence is silently destructive:
    # an unconfigured delete can't remove the Drive copy, and resumes carry
    # PSIDs and phone numbers. Presence is all a startup check can see, and
    # all it needs to — present-but-revoked credentials already fail safe.
    if not drive_services.is_configured():
        missing.append("GDRIVE_RESUME_FOLDER_ID / GDRIVE_OAUTH_*")
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
app.add_middleware(BodyLimitMiddleware, max_bytes=max_body_bytes())

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

# Added LAST, so it ends up OUTERMOST (add_middleware inserts at index 0) and
# corrects scope["scheme"] before anything downstream reads it — the router's
# redirect_slashes being the one that bit us. Outside CORS is fine: this
# middleware only edits the scope and never produces a response, so it cannot
# emit anything that would miss the CORS headers. Requires
# TRUST_PROXY_IP_HEADERS=1; it is a no-op locally and in tests.
app.add_middleware(ForwardedProtoMiddleware)

app.include_router(health_routes.router)
app.include_router(admin_routes.router)
app.include_router(dues_routes.router)
app.include_router(auth_routes.router)
app.include_router(committee_routes.router)
app.include_router(event_routes.router)
app.include_router(leaderboard_routes.router)
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
