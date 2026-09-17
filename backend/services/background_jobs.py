"""Run recurring reminder, event-sheet, and dues-sync jobs."""

import asyncio
import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlmodel import Session

from database import engine
from services import dues_import_services
from services.event_tracker_services import sync_events
from services.reminder_services import send_due_reminders

REMINDER_CHECK_SECONDS = 60
DUES_SYNC_SECONDS = 600

SYNC_TZ = ZoneInfo("America/Chicago")   # the sheet's timezone
SYNC_HOUR = 6                           # 6 AM Central — daily event-sheet sync time


def dispatch_due_reminders():
    """Send due reminders in a dedicated database session."""
    with Session(engine) as session:
        send_due_reminders(session)


async def reminder_loop():
    """Dispatch reminders every minute without blocking the API."""
    while True:
        try:
            await asyncio.to_thread(dispatch_due_reminders)
        except Exception:
            logging.exception("Reminder dispatch failed")
        await asyncio.sleep(REMINDER_CHECK_SECONDS)


def dispatch_event_sync():
    """Sync sheet events in a dedicated database session."""
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
    """Sync events immediately and then daily at the configured Central hour."""
    while True:
        try:
            await asyncio.to_thread(dispatch_event_sync)
        except Exception:
            logging.exception("Event sheet sync failed")
        await asyncio.sleep(seconds_until(SYNC_HOUR))


def dispatch_dues_sync():
    """Run a configured dues import in its own database session."""
    if dues_import_services.is_configured():
        with Session(engine) as session:
            dues_import_services.sync_dues(session)


async def dues_sync_loop():
    """Sync dues immediately and every ten minutes without blocking the API."""
    while True:
        try:
            await asyncio.to_thread(dispatch_dues_sync)
        except Exception:
            logging.exception("Membership dues sync failed")
        await asyncio.sleep(DUES_SYNC_SECONDS)
