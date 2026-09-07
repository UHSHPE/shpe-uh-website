"""
Background jobs that run for the lifetime of the app, started and cancelled
by main.py's lifespan.
"""

import asyncio
import logging
from zoneinfo import ZoneInfo
from sqlmodel import Session
from datetime import datetime, timedelta

from database import engine
from services.reminder_services import send_due_reminders 
from services.event_tracker_services import sync_events

REMINDER_CHECK_SECONDS = 60

SYNC_TZ = ZoneInfo("America/Chicago")   
SYNC_HOUR = 6

def dispatch_due_reminders():
    """Send any reminder emails that are now due, in a fresh DB session."""
    with Session(engine) as session:
        send_due_reminders(session)

async def reminder_loop():
    """Dispatch due reminders every REMINDER_CHECK_SECONDS, forever."""
    while True:
        try:
            await asyncio.to_thread(dispatch_due_reminders)
        except Exception:
            logging.exception("Reminder dispatch failed")
        await asyncio.sleep(REMINDER_CHECK_SECONDS)

def dispatch_event_sync():
    """Reconcile the event-tracker sheet into the Event table, in a fresh DB session."""
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
    """Sync the event sheet on startup, then once a day at SYNC_HOUR Central."""
    while True:
        try:
            await asyncio.to_thread(dispatch_event_sync)
        except Exception:
            logging.exception("Event sheet sync failed")
        await asyncio.sleep(seconds_until(SYNC_HOUR))