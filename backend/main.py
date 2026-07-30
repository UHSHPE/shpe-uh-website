import asyncio
import logging
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from services import square_services

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlmodel import Session

from database import create_db, engine
from services.rate_limit import limiter
from services.reminder_services import send_due_reminders
from services.event_tracker_services import sync_events

from routes import admin_routes, auth_routes, committee_routes, event_routes, notification_routes, pw_reset_routes, resume_routes, shop_routes

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

def seconds_until_next_sync() -> float:
    now = datetime.now(SYNC_TZ)
    target = now.replace(hour=SYNC_HOUR, minute=0, second=0, microsecond=0)
    if target <= now:
        target += timedelta(days=1)   # already past sync time today → aim for tomorrow
    return (target - now).total_seconds()

async def event_sync_loop():
    while True:
        try:
            await asyncio.to_thread(dispatch_event_sync)
        except Exception:
            logging.exception("Event sheet sync failed")
        await asyncio.sleep(seconds_until_next_sync())

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

def assert_production_config():
    if os.getenv("ENVIRONMENT", "").lower() != "production":
        return
    missing = []
    if not square_services.is_configured():
        missing.append("SQUARE_ACCESS_TOKEN / SQUARE_LOCATION_ID")
    if not os.getenv("SMTP_HOST"):
        missing.append("SMTP_HOST")
    if os.getenv("SQUARE_ENVIRONMENT", "sandbox").lower() != "production":
        missing.append("SQUARE_ENVIRONMENT=production")
    if missing:
        raise RuntimeError(
            f"ENVIRONMENT=production but required config is missing: {', '.join(missing)}"
        )

app = FastAPI(lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
