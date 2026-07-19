import asyncio
import logging
import os
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

from routes import auth_routes, committee_routes, event_routes, notification_routes, pw_reset_routes, resume_routes, shop_routes

REMINDER_CHECK_SECONDS = 60

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

# Inits the DB and starts the reminder email loop
@asynccontextmanager
async def lifespan(app):
    assert_production_config()
    create_db()
    reminder_task = asyncio.create_task(reminder_loop())
    yield
    reminder_task.cancel()

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
