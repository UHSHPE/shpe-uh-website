import os, logging
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from sqlmodel import select
from models.event import Event

load_dotenv()
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEET_TZ = ZoneInfo("America/Chicago")
COLUMNS = {"date":"DATE","name":"EVENT NAME","description":"DESCRIPTION","location":"LOCATION","start_time":"START TIME","end_time":"END TIME","owners":"OWNER(S)","sign_in_form":"SIGN IN FORM"}

# Event names (normalized: lowercased, whitespace-collapsed) to keep off the public calendar
EXCLUDED_EVENTS = {"c&e retreat"}

def is_configured() -> bool:
    return bool(os.getenv("CREDENTIALS") and os.getenv("SHEET_ID"))

def get_worksheet():
    if not is_configured():
        return None
    creds = Credentials.from_service_account_file(os.getenv("CREDENTIALS"), scopes=SCOPES)
    return gspread.authorize(creds).open_by_key(os.getenv("SHEET_ID")).sheet1

def parse_time(raw: str) -> time | None:
    """A time, or None for blank / 'All Day' / 'TBD' cells."""
    raw = (raw or "").strip()
    if not raw:
        return None
    for fmt in ("%I:%M:%S %p", "%I:%M %p", "%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(raw, fmt).time()
        except ValueError:
            continue
    return None                                   # 'All Day', 'TBD', etc.

def parse_date(raw: str) -> date:
    """Sheet DATE is MM/DD with no year -> assume the current Central year."""
    year = datetime.now(SHEET_TZ).year
    return datetime.strptime(f"{year}/{raw.strip()}", "%Y/%m/%d").date()

def to_utc(local_naive: datetime) -> datetime:
    return local_naive.replace(tzinfo=SHEET_TZ).astimezone(ZoneInfo("UTC")).replace(tzinfo=None)

def event_key(local_date, title: str) -> str:
    # normalize so trivial edits (extra spaces, casing) don't fork the key
    norm_title = " ".join(title.split()).lower()
    return f"{local_date.isoformat()}|{norm_title}"     # e.g. "2026-08-05|gbm 1"

def parse_row(row: dict) -> dict | None:
    name = " ".join((row.get(COLUMNS["name"]) or "").split())
    if not name:
        return None                               # blank/template row
    if name.lower() in EXCLUDED_EVENTS:
        return None                               # explicitly hidden from the calendar

    day = parse_date(row[COLUMNS["date"]])        # bad date -> raises -> row skipped
    start_local = datetime.combine(day, parse_time(row.get(COLUMNS["start_time"])) or time(0, 0))
    end_t = parse_time(row.get(COLUMNS["end_time"]))
    end_local = datetime.combine(day, end_t) if end_t else None

    return {
        "source_row_id": event_key(day, name),
        "title": name,
        "description": row.get(COLUMNS["description"]),
        "location": row.get(COLUMNS["location"]),
        "start_time": to_utc(start_local),
        "end_time": to_utc(end_local) if end_local else None,
    }

def fetch_sheet_events() -> list[dict]:
    ws = get_worksheet()
    if ws is None:
        print("[event tracker dev mode] no creds — skipping sync")
        return []
    rows = []
    # row 1 = headers, row 2 = sample/template row -> real events start at row 3
    for raw in ws.get_all_records()[1:]:
        try:
            parsed = parse_row(raw)
        except Exception:
            logger.exception("Bad event row, skipping: %r", raw)   # per-row isolation
            continue
        if parsed:
            rows.append(parsed)
    return rows

def sync_events(session) -> tuple[int, int]:
    created = updated = 0
    for data in fetch_sheet_events():
        existing = session.exec(
            select(Event).where(Event.source_row_id == data["source_row_id"])
        ).first()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
        else:
            session.add(Event(**data))
            created += 1
    session.commit()
    logger.info("Event sync: %d created, %d updated", created, updated)
    return created, updated