import json, os, logging, re
import secrets
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from sqlmodel import select
from models.committee import Committee
from models.event import Event
from models.event_host import EventHost
from models.event_reminder import EventReminder
from models.user.user_enums import Role   
from services.event_services import live_events
from services.reminder_services import reschedule_reminders
from services.time_services import utcnow

load_dotenv()
logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
SHEET_TZ = ZoneInfo("America/Chicago")
COLUMNS = {"date":"DATE",
           "name":"EVENT NAME",
           "description":"DESCRIPTION",
           "location":"LOCATION",
           "start_time":"START TIME",
           "end_time":"END TIME",
           "owners":"OWNER(S)",
           "collab(s)": "COLLAB(S)?",}

# Event names (normalized: lowercased, whitespace-collapsed) to keep off the public calendar
EXCLUDED_EVENTS = {
    "c&e retreat",
    "national convention",
    "thanksgiving break",
    "eboard & chair photos",
    "first day of class",
    "cat's back day 1",
    "cat's back day 2",
    "labor day",
    "priority registration day 1",
    "priority registration day 2",
    "career fair day 1",
    "career fair day 2",
    "last day of class",
    "official closing of term",
}

COMMITTEE_ROLES = {
    "academic":             Role.academic_chair,
    "wellness & athletics": Role.athletic_chair,
    "cfc":                  Role.career_fair_chair,
    "eec":                  Role.eec_chair,
    "marketing":            Role.marketing_chair,
    "member relations":     Role.member_relations_chair,
    "mentorshpe":           Role.mentorshpe_chair,
    "outreach":             Role.outreach_chair,
    "professional":         Role.professional_chair,
    "project":              Role.projects_chair,   # OWNER(S) spelling
    "projects":             Role.projects_chair,   # COLLAB(S)? spelling
    "shpe jr.":             Role.shpe_jr_chair,    # OWNER(S) spelling
    "shpe jr":              Role.shpe_jr_chair,    # COLLAB(S)? spelling
    "shpetina":             Role.shpetina_chair,
    "social":               Role.social_chair,
    "web development":      Role.web_dev_chair,
}

EBOARD: dict[str, Role | None] = {
    "president": Role.president,
    "vpe": Role.vpe,
    "vpi": Role.vpi,
    "secretary": Role.secretary,
    "treasurer": Role.treasurer,
    "communications": Role.comm_director,
    "new member rep": Role.new_member_rep,
    "regional rep": Role.regional_rep,
    "director of internal affairs": Role.dir_int_aff,
    "eboard": None,
}


class _NoMatch:
    """Sentinel for resolve_committee: distinguishes 'no host committee at
    all' (blank cell, an outside-org collab like "NSBE") from a genuine match
    to the generic "E-Board" catch-all committee, whose chair_role is
    legitimately None. Plain None can't serve as the "no match" signal
    anymore because None is now itself a valid resolution."""

    def __repr__(self):
        return "NO_MATCH"


NO_MATCH = _NoMatch()

def is_configured() -> bool:
    has_creds = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON") or os.getenv("CREDENTIALS")
    return bool(has_creds and os.getenv("SHEET_ID"))

def _service_account_credentials():
    """Credentials from the inline JSON if present, else the file path.

    The inline form exists for deployment: the key file is gitignored, so it
    is never in the image, and container hosts have no secret-file mount.
    Service-account JSON already escapes newlines inside private_key as
    literal \\n, so `jq -c . key.json` yields a safe single-line env value.
    The file path stays supported for local development (see the README).
    """
    raw = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
    if raw:
        return Credentials.from_service_account_info(json.loads(raw), scopes=SCOPES)
    return Credentials.from_service_account_file(os.getenv("CREDENTIALS"), scopes=SCOPES)

def get_worksheet():
    if not is_configured():
        return None
    creds = _service_account_credentials()
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

def local_date(utc_naive: datetime) -> date:
    """The Central calendar day an event falls on. The inverse of to_utc()'s
    date half: Event.start_time is naive UTC, but the sheet's identity is
    expressed in Central dates, so the two have to be compared in Central."""
    return utc_naive.replace(tzinfo=ZoneInfo("UTC")).astimezone(SHEET_TZ).date()

def _normalize_owner(raw: str | None) -> str:
    text = " ".join((raw or "").split()).lower()
    text = re.split(r"[-–—]", text, maxsplit=1)[0]      # drop "- <chair name(s)>"
    return re.sub(r"\s+chairs?$", "", text.strip()).strip()


def resolve_committee(raw: str | None):
    """Committee-linking key for an OWNER(S) or COLLAB(S)? value.

    Returns a Role for a specific chair/position committee, None for the
    generic "E-Board" catch-all (a real match -- see EBOARD["eboard"]), or
    NO_MATCH when the text isn't recognized at all (blank cell, an
    outside-org collab like "NSBE"). NO_MATCH -- not None -- is what
    parse_row filters host_roles on, because None is itself a legitimate
    resolution here (chair_role=None on the generic E-Board committee).

    Silent by design on a miss — an unrecognized COLLAB(S)? is an outside
    org, which is the normal case. All logging lives in get_event_type().
    """
    text = _normalize_owner(raw)
    if text in COMMITTEE_ROLES:
        return COMMITTEE_ROLES[text]
    if text in EBOARD:
        return EBOARD[text]
    return NO_MATCH


def get_event_type(raw_owner: str | None) -> str | None:
    text = _normalize_owner(raw_owner)
    if not text:
        return None                     # unfilled cell isn't a positive claim about E-Board
    if text in COMMITTEE_ROLES:
        return COMMITTEE_ROLES[text].name.removesuffix("_chair")   # "academic", "eec", "shpe_jr"
    if text not in EBOARD:
        logger.warning("Unrecognized event owner %r — filing under eboard", raw_owner)
    return "eboard"


def parse_row(row: dict, sheet_row: int) -> dict | None:
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
        "sheet_row": sheet_row,
        "title": name,
        "description": row.get(COLUMNS["description"]),
        "location": row.get(COLUMNS["location"]),
        "start_time": to_utc(start_local),
        "end_time": to_utc(end_local) if end_local else None,
        "event_type": get_event_type(row.get(COLUMNS["owners"])),
        "host_roles": [r for r in (resolve_committee(row.get(COLUMNS["owners"])),
                                   resolve_committee(row.get(COLUMNS["collab(s)"])))
                       if r is not NO_MATCH],
    }

def fetch_sheet_events() -> list[dict]:
    ws = get_worksheet()
    if ws is None:
        print("[event tracker dev mode] no creds — skipping sync")
        return []
    rows = []
    # row 1 = headers, row 2 = sample/template row -> real events start at row 3.
    # get_all_records() already consumed row 1 as the header, and [1:] drops the
    # template, so enumerate's start=3 is what maps a list index back onto the
    # ACTUAL spreadsheet row number -- which is the sync's identity, so an
    # off-by-one here silently re-identifies every event.
    for sheet_row, raw in enumerate(ws.get_all_records()[1:], start=3):
        try:
            parsed = parse_row(raw, sheet_row)
        except Exception:
            logger.exception("Bad event row, skipping: %r", raw)   # per-row isolation
            continue
        if parsed:
            rows.append(parsed)
    return rows


def _reconcile_hosts(session, event: Event, host_roles: list, committee_ids: dict) -> None:
    """Point EventHost at exactly the committees the sheet names for this event.

    A deliberate, narrow exception to this file's no-hard-delete rule:
    EventHost has no dependents (unlike Event, whose FKs from EventReminder /
    EventAttendance / EventHost have no ondelete), so dropping a row is safe.
    Leaving hosts additive-only would mean a collab pulled from the sheet keeps
    that chair able to see -- and mint QR codes for -- an event they no longer
    run.
    """
    existing_hosts = set(session.exec(
        select(EventHost.committee_id).where(EventHost.event_id == event.id)
    ).all())
    for role in host_roles:
        if role not in committee_ids:
            logger.warning(
                "No Committee row for chair role %s — skipping host link on %r",
                role, event.title,
            )
    wanted = {committee_ids[r] for r in host_roles if r in committee_ids}
    # The wanted - existing_hosts difference is load-bearing: sync_events has no
    # per-row try/except (that isolation lives in fetch_sheet_events), so a blind
    # session.add(EventHost(...)) on a second sync would raise IntegrityError on
    # the composite PK at commit and kill the entire sync, not just one row.
    for cid in wanted - existing_hosts:
        session.add(EventHost(event_id=event.id, committee_id=cid))
    for cid in existing_hosts - wanted:
        session.delete(session.get(EventHost, (event.id, cid)))


def sync_events(session) -> tuple[int, int]:
    """Reconcile the calendar against the current state of the tracker sheet.

    Identity is the SHEET ROW NUMBER, paired with the row's Central date.

    The tracker is a fixed skeleton -- rows 1..n are pre-laid out by date, a
    chair fills in a free row, and rows are never inserted, so nothing ever
    shifts. That makes the row number stable across any content edit, which the
    old "<date>|<title>" key was not: it was derived from the two fields people
    edit, so every rename or reschedule minted a fresh identity, inserted a
    second event, and left the stale one on the calendar forever. That is the
    duplicate bug this replaced.

    The date rides along only as a cross-semester guard. Row 40 means something
    different in the fall and spring trackers, and without the date the frozen
    fall event sitting at row 40 would block the spring one from ever being
    created. Pairing them keeps identity stable through a rename (the row's
    date does not move) while letting the same row carry a new event next term.

    Three rules:

      1. Upsert by (sheet_row, Central date).
      2. Sweep -- a sheet-sourced event whose pair is no longer in the sheet is
         SOFT-deleted, never destroyed.
      3. Past events are frozen: an event that has already started is never
         modified and never swept. This is what protects attendance history,
         and it is also why a stale SHEET_ID read in January is harmless -- every
         row resolves to a frozen past event and the sync does nothing.

    Returns (created, updated); the sweep count goes to the log.
    """
    created = updated = swept = frozen = 0
    now = utcnow()
    # Role -> Committee.id, built once outside the loop (one query, no N+1).
    # Keyed on chair_role, the same anchor COMMITTEE_ROLES uses, so a committee
    # rename in seed.py can't break this link.
    committee_ids = {c.chair_role: c.id for c in session.exec(select(Committee)).all()}

    rows = fetch_sheet_events()
    seen: set[tuple[int, date]] = set()

    for data in rows:
        # Not an Event column -- EventHost is a different table. Must come out
        # before Event(**data) and, more sharply, before the setattr update loop
        # below: setattr on an already-built SQLModel instance raises ValueError
        # on an unrecognized field, unlike the constructor, which silently drops
        # an unknown kwarg.
        host_roles = data.pop("host_roles", [])
        row_date = local_date(data["start_time"])
        seen.add((data["sheet_row"], row_date))

        # Deliberately NOT filtered on deleted_at: a chair who blanks a row and
        # re-fills it should get their event back with the same Event.id (and
        # its reminders), not a fresh row alongside the hidden one. This is also
        # what keeps "at most one Event per (sheet_row, date)" true -- we only
        # ever create when nothing, hidden or visible, holds that pair.
        existing = next(
            (e for e in session.exec(
                select(Event).where(Event.sheet_row == data["sheet_row"])
            ).all() if local_date(e.start_time) == row_date),
            None,
        )

        if existing is not None:
            if existing.start_time <= now:
                frozen += 1          # rule 3 -- already started, leave it alone
                continue
            was_at = existing.start_time
            for k, v in data.items():
                setattr(existing, k, v)
            existing.deleted_at = None
            if existing.start_time != was_at:
                # The row's time moved. remind_at is computed once when the
                # member sets the reminder and never revisited, so without this
                # the reminder keeps firing on the old schedule.
                reschedule_reminders(session, existing.id, existing.start_time, now)
            updated += 1
            event = existing
        else:
            event = Event(**data)
            event.sign_in_code = secrets.token_urlsafe(nbytes=16)
            event.sign_out_code = secrets.token_urlsafe(nbytes=16)

            session.add(event)
            session.flush()          # a new Event has no .id until this
            created += 1

        _reconcile_hosts(session, event, host_roles, committee_ids)

    # An empty pull means "unconfigured" or "the fetch failed" -- both return []
    # -- so it must never be read as "the sheet is empty, hide everything".
    if rows:
        swept = _sweep(session, seen, now)

    session.commit()
    logger.info(
        "Event sync: %d created, %d updated, %d soft-deleted, %d frozen (past)",
        created, updated, swept, frozen,
    )
    return created, updated


def _sweep(session, seen: set[tuple[int, date]], now: datetime) -> int:
    """Soft-delete future sheet events whose row is no longer filled in.

    Scoped to future events by rule 3, and soft only: EventReminder,
    EventHost and EventAttendance all carry a plain foreign_key="event.id"
    with no ondelete and no ORM Relationship(), so a real delete would raise
    ForeignKeyViolation -- and since sync_events commits once at the end, that
    would roll back every create and update in the batch, not just this row.

    Unsent reminders ARE hard-deleted alongside: nothing should email a member
    about an event that is off the calendar, and leaving the row behind would
    let it resurface pointing at a different event if the row is re-filled.
    """
    stale = [
        e for e in session.exec(
            live_events().where(
                Event.sheet_row != None,  # noqa: E711
                Event.start_time > now,
            )
        ).all()
        if (e.sheet_row, local_date(e.start_time)) not in seen
    ]

    for event in stale:
        event.deleted_at = now
        session.add(event)
        for reminder in session.exec(
            select(EventReminder).where(
                EventReminder.event_id == event.id,
                EventReminder.sent_at == None,  # noqa: E711
            )
        ).all():
            session.delete(reminder)
        logger.info(
            "Soft-deleted event %r (id=%s, sheet row %s) — no longer in the sheet",
            event.title, event.id, event.sheet_row,
        )

    return len(stale)
