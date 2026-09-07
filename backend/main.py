"""
Constructs the app, wires the rate limiter & middle ware, and includes the routes
"""

import asyncio
import os
from services import drive_services, square_services

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from contextlib import asynccontextmanager

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from config import cors_origins,docs_urls,is_production,max_body_bytes,square_is_production
from database import create_db
from services.body_limit import BodyLimitMiddleware
from services.forwarded_proto import ForwardedProtoMiddleware
from services.rate_limit import limiter
from services.background_jobs import reminder_loop, event_sync_loop

from routes import admin_routes, auth_routes, committee_routes, event_routes, notification_routes, pw_reset_routes, resume_routes, shop_routes, health_routes

load_dotenv()

@asynccontextmanager
async def lifespan(app):
    assert_production_config()
    create_db()
    reminder_task = asyncio.create_task(reminder_loop())
    event_sync_task = asyncio.create_task(event_sync_loop())
    yield
    reminder_task.cancel()
    event_sync_task.cancel()

def assert_production_config():
    """ Prevents prod from deploying backend if not set up correctly  """
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
    if not drive_services.is_configured():
        missing.append("GDRIVE_RESUME_FOLDER_ID / GDRIVE_OAUTH_*")
    if any("localhost" in o or "127.0.0.1" in o for o in cors_origins()):
        missing.append("CORS_ORIGINS/FRONTEND_URL (still points at localhost)")
    if missing:
        raise RuntimeError(
            f"ENVIRONMENT=production but required config is missing: {', '.join(missing)}"
        )

app = FastAPI(lifespan=lifespan, **docs_urls())

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

_allowed_hosts = os.getenv("ALLOWED_HOSTS")
if _allowed_hosts:
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[h.strip() for h in _allowed_hosts.split(",") if h.strip()],
    )

app.add_middleware(BodyLimitMiddleware, max_bytes=max_body_bytes())
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ForwardedProtoMiddleware)

app.include_router(admin_routes.router)
app.include_router(auth_routes.router)
app.include_router(committee_routes.router)
app.include_router(event_routes.router)
app.include_router(notification_routes.router)
app.include_router(pw_reset_routes.router)
app.include_router(resume_routes.router)
app.include_router(shop_routes.router)
app.include_router(health_routes.router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=not is_production(),
        proxy_headers=True,
    )