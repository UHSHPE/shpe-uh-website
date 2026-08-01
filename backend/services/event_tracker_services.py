import os, logging, re
from datetime import datetime, date, time
from zoneinfo import ZoneInfo
import gspread
from dotenv import load_dotenv
from google.oauth2.service_account import Credentials
from sqlmodel import select
from models.committee import Committee
from models.event import Event
from models.event_host import EventHost
from models.user.user_enums import Role   # leaf enum module -- no circular import


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
EXCLUDED_EVENTS = {"c&e retreat", "national convention", "thanksgiving break"}

# OWNER(S) / COLLAB(S)? -> chair Role. Keys are the SHEET's spelling
# (lowercased, whitespace-collapsed), deliberately not Committee.name --
# "wellness & athletics", "project", "shpe jr.", "eec", "cfc" all differ from
# the DB names in seed.py. Role is the anchor because Committee.chair_role
# and require_chair already key on it, so a committee rename in seed.py
# can't break this link. "&" and the trailing "." are NOT normalized away --
# they're part of the correct key.
#
# "project"/"projects" and "shpe jr."/"shpe jr" are the tell that the two
# dropdowns (OWNER(S) vs COLLAB(S)?) are independently maintained option
# lists that don't always agree -- two divergences in fourteen committees is
# a high enough rate that there are probably more. Extra aliases cost
# nothing; a missing one is a silent misfile.
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

# The sheet's own abbreviations for E-Board positions -- not Role display
# values ("vpe" vs "Vice President External", "communications" vs
# "Communication Director"). Now a dict, not a set: each specific position
# maps onto the Committee row seed.py creates for it (EBOARD_COMMITTEES) so
# EventHost rows get written -- the same reason COMMITTEE_ROLES is a dict.
# The bare "eboard" catch-all maps to None deliberately: seed.py also
# creates one generic "E-Board" committee with chair_role=None for exactly
# this value. None here is a REAL match (a specific, if generic, committee),
# never confused with "no match at all" -- see resolve_committee's docstring
# and the NO_MATCH sentinel below.
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
    # Role -> Committee.id, built once outside the loop (14 rows, one query,
    # no N+1). Keyed on chair_role, the same anchor COMMITTEE_ROLES uses, so
    # a committee rename in seed.py can't break this link.
    committee_ids = {c.chair_role: c.id for c in session.exec(select(Committee)).all()}

    for data in fetch_sheet_events():
        # Not an Event column -- EventHost is a different table. Must come
        # out before Event(**data) and, more sharply, before the setattr
        # update loop below: setattr on an already-built SQLModel instance
        # raises ValueError on an unrecognized field, unlike the
        # constructor, which silently drops an unknown kwarg.
        host_roles = data.pop("host_roles", [])

        existing = session.exec(
            select(Event).where(Event.source_row_id == data["source_row_id"])
        ).first()
        if existing:
            for k, v in data.items():
                setattr(existing, k, v)
            updated += 1
            event = existing
        else:
            event = Event(**data)
            session.add(event)
            session.flush()          # a new Event has no .id until this
            created += 1

        # Host reconciliation -- a deliberate, narrow exception to this
        # file's no-delete rule. EventHost has no dependents (unlike Event,
        # where deleting orphans EventReminder rows and resets
        # points_value), so removing a stale row is safe here. Leaving hosts
        # additive-only would mean a collab pulled from the sheet keeps that
        # chair able to see and mint QR codes for an event they no longer run.
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
        # The wanted - existing_hosts difference is load-bearing: sync_events
        # has no per-row try/except (that isolation lives in
        # fetch_sheet_events), so a blind session.add(EventHost(...)) on a
        # second sync would raise IntegrityError on the composite PK at
        # commit and kill the entire sync, not just one row.
        for cid in wanted - existing_hosts:
            session.add(EventHost(event_id=event.id, committee_id=cid))
        for cid in existing_hosts - wanted:
            session.delete(session.get(EventHost, (event.id, cid)))

    session.commit()
    logger.info("Event sync: %d created, %d updated", created, updated)
    return created, updated