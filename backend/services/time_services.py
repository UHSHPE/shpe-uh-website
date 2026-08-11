from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now — SQLite stores datetimes as plain text, so the project
    uses naive UTC everywhere. Replaces the deprecated datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
