from datetime import datetime, timezone, timedelta


def utcnow() -> datetime:
    """Naive UTC now — SQLite stores datetimes as plain text, so the project
    uses naive UTC everywhere. Replaces the deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)

def get_start_of_week() -> datetime:
    now = utcnow()

    return (now - timedelta(days=now.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
