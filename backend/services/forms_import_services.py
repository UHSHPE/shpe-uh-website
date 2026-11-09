"""Read the points index Sheet and the Google Form response sheets it links to.

The index tab lists one event per row; its Sign in / Sign out cells hyperlink
to each form's RESPONSE spreadsheet (not the form), so everything is read
through the Sheets API as the shared chairs account. Pure parsing is split
from fetching so it can be tested without Google.

Fetchers make blocking network calls: call them from a sync route or a thread,
never directly inside an `async def` handler.
"""

import logging
import os
import re
from collections import defaultdict
from dataclasses import dataclass
from threading import Lock
from typing import NamedTuple
from urllib.parse import parse_qs, urlsplit

import gspread
from fastapi import HTTPException
from sqlalchemy import func, or_, update
from sqlmodel import Session, select

from models.form_point_award import FormPointAward, FormsImportResult
from models.user.user import User
from services.event_tracker_services import get_event_type
from services.points import POINT_VALUES, sign_in_points
from services.time_services import utcnow
from validators.email import normalize_email

logger = logging.getLogger(__name__)
_import_lock = Lock()

SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_ENV_VARS = (
    "POINTS_OAUTH_CLIENT_ID",
    "POINTS_OAUTH_CLIENT_SECRET",
    "POINTS_OAUTH_REFRESH_TOKEN",
    "POINTS_SHEET_ID",
)
INDEX_TAB = "Sign in/out"
_INDEX_HEADERS = {
    "event_name": "event name",
    "sign_in": "sign in",
    "sign_out": "sign out",
    "committee": "committee",
    "special_type": "special event type",
}

_PSID_HEADER = re.compile(r"psid|peoplesoft|people\s*soft|\buh\s*id\b")
# Cougarnet incl. the typos seen live (Courgarnet, Couagarnet, Cougar Net), or "UH ... email".
_UH_EMAIL_HEADER = re.compile(r"cou\w*\s*net|\buh\b.*e-?mail")
_NEW_MEMBER_HEADER = re.compile(r"\bbring\b.*\bnew members?\b")


class ResponseSource(NamedTuple):
    spreadsheet_id: str
    gid: int


@dataclass(frozen=True)
class IndexRow:
    row_number: int
    event_name: str
    committee: str
    special_type: str | None
    sign_in: ResponseSource | None
    sign_out: ResponseSource | None


@dataclass(frozen=True)
class FormResponse:
    row_number: int
    psid: str | None
    email: str | None  # normalized Cougarnet email
    wore_shirt: bool
    brought_new_member: bool


def _norm(text: str | None) -> str:
    return " ".join((text or "").split()).lower()


def _cell(row: list[str], col: int | None) -> str:
    return row[col].strip() if col is not None and col < len(row) and row[col] else ""


# --- index sheet ---

def parse_response_link(url: str | None) -> ResponseSource | None:
    """(spreadsheet id, tab gid) for a Sheets link, or None for anything else."""
    parts = urlsplit((url or "").strip())
    if parts.netloc != "docs.google.com":
        return None
    match = re.match(r"/spreadsheets/d/([\w-]+)", parts.path)
    if not match:
        return None
    gid = parse_qs(parts.query).get("gid") or parse_qs(parts.fragment).get("gid") or ["0"]
    return ResponseSource(match.group(1), int(gid[0])) if gid[0].isdigit() else None


def parse_index_rows(row_data: list[dict]) -> list[IndexRow]:
    """Event rows that link at least one response sheet.

    Args:
        row_data: Sheets API `rowData` for the index tab, header row first; each
            cell is a dict with optional `formattedValue` and `hyperlink`.
    Returns:
        One IndexRow per usable row; raises ValueError if a required header is missing.
    """
    header = [_norm(c.get("formattedValue")) for c in row_data[0].get("values", [])] if row_data else []
    missing = [name for name in _INDEX_HEADERS.values() if name not in header]
    if missing:
        raise ValueError(f"Points sheet is missing required column(s): {', '.join(missing)}")
    col = {field: header.index(name) for field, name in _INDEX_HEADERS.items()}

    rows = []
    for row_number, row in enumerate(row_data[1:], start=2):
        cells = row.get("values", [])

        def cell(field):
            i = col[field]
            return cells[i] if i < len(cells) else {}

        def source(field):
            # A cell with text but no hyperlink ("no sign out ") just means no form.
            url = cell(field).get("hyperlink")
            if not url:
                return None
            parsed = parse_response_link(url)
            if parsed is None:
                logger.warning("Points sheet row %s: %s link is not a response spreadsheet; ignoring it",
                               row_number, field.replace("_", " "))
            return parsed

        sign_in, sign_out = source("sign_in"), source("sign_out")
        if sign_in is None and sign_out is None:
            continue
        rows.append(IndexRow(
            row_number=row_number,
            event_name=" ".join((cell("event_name").get("formattedValue") or "").split()),
            committee=(cell("committee").get("formattedValue") or "").strip(),
            special_type=(cell("special_type").get("formattedValue") or "").strip() or None,
            sign_in=sign_in,
            sign_out=sign_out,
        ))
    return rows


# --- response sheets ---

def _find_column(header: list[str], matches) -> int | None:
    return next((i for i, title in enumerate(header) if matches(_norm(title))), None)


def find_psid_column(header: list[str]) -> int | None:
    return _find_column(header, _PSID_HEADER.search)


def find_email_column(header: list[str]) -> int | None:
    """The UH/Cougarnet email column only; generic and personal emails are never used."""
    return _find_column(header, lambda t: "personal" not in t and _UH_EMAIL_HEADER.search(t))


def find_shirt_column(header: list[str]) -> int | None:
    return _find_column(header, lambda t: "shirt" in t)


def find_new_member_column(header: list[str]) -> int | None:
    # Keyed on "bring": "What is the new member's name?" also says "new member".
    return _find_column(header, _NEW_MEMBER_HEADER.search)


def parse_psid(raw: str | None) -> str | None:
    psid = (raw or "").strip().removeprefix("#").strip()
    return psid if re.fullmatch(r"[0-9]{7}", psid) else None


def parse_yes_no(raw: str | None) -> bool | None:
    """True / False from the answer's first word (yes | no, nope); None if blank or unrecognized."""
    word = re.match(r"[a-z]*", _norm(raw)).group()
    if word == "yes":
        return True
    if word in ("no", "nope"):
        return False
    return None


def response_identity(
    row: list[str], psid_col: int | None, email_col: int | None
) -> tuple[str | None, str | None] | None:
    """(PSID, normalized Cougarnet email), each None if blank or malformed; None if both are.

    Both are kept: which account they name is decided at lookup, not here.
    """
    psid = parse_psid(_cell(row, psid_col))
    email = _cell(row, email_col) or None
    if email:
        try:
            email = normalize_email(email)
        except HTTPException:
            email = None
    return (psid, email) if psid or email else None


def parse_responses(values: list[list[str]]) -> list[FormResponse]:
    """One FormResponse per identifiable response row.

    Args:
        values: A response tab's cells as strings, header row first.
    Returns:
        Responses in sheet order; raises ValueError if the tab is blank (a linked
        form always writes a header, so blank means wiped) or has neither a PSID
        nor a UH email column, since then nobody could be credited.
    """
    if not values:
        raise ValueError("Response sheet is empty")
    header = values[0]
    psid_col, email_col = find_psid_column(header), find_email_column(header)
    if psid_col is None and email_col is None:
        raise ValueError("Response sheet has no PSID or UH email column")
    shirt_col, new_member_col = find_shirt_column(header), find_new_member_column(header)

    responses = []
    for row_number, row in enumerate(values[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        identity = response_identity(row, psid_col, email_col)
        if identity is None:
            # Row number only -- never log the PSID/email a member typed.
            logger.warning("Response row %s has no valid PSID or UH email; skipping", row_number)
            continue
        psid, email = identity
        responses.append(FormResponse(
            row_number=row_number,
            psid=psid,
            email=email,
            wore_shirt=parse_yes_no(_cell(row, shirt_col)) is True,
            brought_new_member=parse_yes_no(_cell(row, new_member_col)) is True,
        ))
    return responses


# --- fetching ---

def is_configured() -> bool:
    return all(os.getenv(name, "").strip() for name in _ENV_VARS)


def get_client() -> gspread.Client | None:
    """gspread client acting as the shared chairs account, or None when unconfigured.

    OAuth refresh-token credentials, not a service account: the response sheets
    belong to the chairs account and are not shared with any service account.
    """
    if not is_configured():
        return None
    from google.oauth2.credentials import Credentials

    creds = Credentials(
        token=None,
        refresh_token=os.environ["POINTS_OAUTH_REFRESH_TOKEN"].strip(),
        client_id=os.environ["POINTS_OAUTH_CLIENT_ID"].strip(),
        client_secret=os.environ["POINTS_OAUTH_CLIENT_SECRET"].strip(),
        token_uri=_TOKEN_URI,
        scopes=SCOPES,
    )
    # Backoff: one pass reads ~2 requests per response tab, past the 60/min read quota.
    client = gspread.authorize(creds, http_client=gspread.BackOffHTTPClient)
    client.set_timeout(30)
    return client


def fetch_index_rows(client: gspread.Client) -> list[IndexRow]:
    """Every index row with a usable response-sheet link."""
    # get_all_values() returns display text only; the URLs live in each cell's hyperlink.
    meta = client.open_by_key(os.environ["POINTS_SHEET_ID"].strip()).fetch_sheet_metadata(params={
        "includeGridData": "true",
        "ranges": f"'{INDEX_TAB}'",
        "fields": "sheets.data.rowData.values(formattedValue,hyperlink)",
    })
    return parse_index_rows(meta["sheets"][0]["data"][0].get("rowData", []))


def fetch_responses(client: gspread.Client, source: ResponseSource) -> list[list[str]]:
    """All cells of one response tab, header row first."""
    return client.open_by_key(source.spreadsheet_id).get_worksheet_by_id(source.gid).get_all_values()


# --- awarding ---

@dataclass(frozen=True)
class _Award:
    user_id: int | None
    kind: str
    points: int
    index_row: int
    event_name: str


def _verified_users(session: Session, fetched: dict[ResponseSource, list[FormResponse]]):
    """({psid: user_id}, {cougarnet_email: user_id}) for verified accounts named in any response.

    Verified only, like the leaderboard: unverified accounts can be deleted
    (auth_routes), which a foreign key from an award would block.
    """
    psids = {r.psid for rs in fetched.values() for r in rs if r.psid}
    emails = {r.email for rs in fetched.values() for r in rs if r.email}
    if not psids and not emails:
        return {}, {}
    users = session.exec(
        select(User.id, User.psid, User.cougarnet_email)
        .where(User.email_verified == True)  # noqa: E712 -- SQL, not Python
        .where(or_(User.psid.in_(psids), func.lower(User.cougarnet_email).in_(emails)))
    ).all()
    return {u.psid: u.id for u in users}, {u.cougarnet_email.lower(): u.id for u in users}


def _match_user(response: FormResponse, by_psid: dict, by_email: dict) -> int | None:
    """A matching PSID wins; the email only counts when the PSID matches nobody."""
    psid_user, email_user = by_psid.get(response.psid), by_email.get(response.email)
    if psid_user and email_user and psid_user != email_user:
        # Row number only -- never log the PSID/email a member typed.
        logger.warning("Response row %s: PSID and UH email belong to different accounts; crediting the PSID",
                       response.row_number)
    return psid_user or email_user


def _desired_awards(session, index_rows, fetched) -> dict[tuple[str, int, str], _Award]:
    """What the sheets say every member should have right now, keyed like FormPointAward."""
    by_psid, by_email = _verified_users(session, fetched)
    desired: dict[tuple[str, int, str], _Award] = {}
    for row in index_rows:
        slug = get_event_type(row.committee)
        for kind, source in (("sign_in", row.sign_in), ("sign_out", row.sign_out)):
            for response in fetched.get(source, []) if source else []:
                user_id = _match_user(response, by_psid, by_email)
                pending_key = f"psid:{response.psid}" if response.psid else f"email:{response.email}"
                member_key = f"user:{user_id}" if user_id else pending_key
                points = (
                    sign_in_points(slug, row.special_type,
                                   brought_new_member=response.brought_new_member,
                                   wore_shirt=response.wore_shirt)
                    if kind == "sign_in" else POINT_VALUES["sign_out"]
                )
                key = (source.spreadsheet_id, source.gid, member_key)
                # Several submissions by one member: keep the best, never sum them.
                if key not in desired or points > desired[key].points:
                    desired[key] = _Award(user_id, kind, points, row.row_number, row.event_name)
    return desired


def reconcile_awards(
    session: Session,
    index_rows: list[IndexRow],
    fetched: dict[ResponseSource, list[FormResponse]],
    failed: set[ResponseSource],
) -> FormsImportResult:
    """Make FormPointAward and User.points match the sheets, in one transaction.

    Args:
        index_rows: Every usable index row, from a successful index read.
        fetched: Parsed responses for each source that was read successfully.
        failed: Sources that could not be read; their awards are left untouched,
            since a failed read must never look like a deleted row.
    Returns:
        Counts of awarded / adjusted / revoked / pending.
    """
    desired = _desired_awards(session, index_rows, fetched)
    deltas: dict[int, int] = defaultdict(int)
    result = FormsImportResult(status="synced", sources_read=len(fetched), sources_failed=len(failed))
    now = utcnow()

    for award in session.exec(select(FormPointAward)).all():
        if ResponseSource(award.spreadsheet_id, award.gid) in failed:
            continue
        want = desired.pop((award.spreadsheet_id, award.gid, award.member_key), None)
        if want is None:
            if award.user_id:
                deltas[award.user_id] -= award.points
                result.revoked += 1
            session.delete(award)
            continue
        if award.user_id and want.points != award.points:
            deltas[award.user_id] += want.points - award.points
            result.adjusted += 1
        award.kind, award.points = want.kind, want.points
        award.index_row, award.event_name, award.updated_at = want.index_row, want.event_name, now
        session.add(award)

    for (spreadsheet_id, gid, member_key), want in desired.items():
        session.add(FormPointAward(
            spreadsheet_id=spreadsheet_id, gid=gid, member_key=member_key, user_id=want.user_id,
            kind=want.kind, points=want.points, index_row=want.index_row, event_name=want.event_name,
            created_at=now, updated_at=now,
        ))
        if want.user_id:
            deltas[want.user_id] += want.points
            result.awarded += 1

    for user_id, delta in deltas.items():
        if delta:
            # In SQL, not read-modify-write, so a concurrent writer of User.points
            # isn't overwritten. Floored at 0 in case points were reset by hand.
            session.execute(
                update(User).where(User.id == user_id).values(points=func.greatest(User.points + delta, 0))
            )
    session.commit()
    result.pending = len(session.exec(select(FormPointAward.id).where(FormPointAward.user_id == None)).all())  # noqa: E711
    return result


def run_forms_import(session: Session) -> FormsImportResult:
    """Read the points sheet and every linked response sheet, then reconcile awards.

    Changes nothing unless the index sheet itself was read and validated; a
    response sheet that fails is skipped and keeps its existing awards.
    """
    if not _import_lock.acquire(blocking=False):
        return FormsImportResult(status="busy")
    try:
        client = get_client()
        if client is None:
            return FormsImportResult(status="unconfigured")
        try:
            index_rows = fetch_index_rows(client)
        except ValueError as exc:
            logger.error("Points sheet rejected: %s", exc)
            return FormsImportResult(status="invalid_sheet", message=str(exc))
        if not index_rows:
            # Reconciling against nothing would revoke every award at once.
            logger.error("Points sheet has no linked rows; refusing to revoke every award")
            return FormsImportResult(status="invalid_sheet", message="No linked rows in the points sheet.")

        fetched: dict[ResponseSource, list[FormResponse]] = {}
        failed: set[ResponseSource] = set()
        for row in index_rows:
            for kind, source in (("sign in", row.sign_in), ("sign out", row.sign_out)):
                if source is None or source in fetched or source in failed:
                    continue
                try:
                    fetched[source] = parse_responses(fetch_responses(client, source))
                except Exception:
                    # One unreadable sheet must not block the rest of the chapter's points.
                    logger.exception("Points sheet row %s: could not read %s responses", row.row_number, kind)
                    failed.add(source)

        result = reconcile_awards(session, index_rows, fetched, failed)
        logger.info("Forms import: %s", result.model_dump(exclude={"message"}))
        return result
    finally:
        _import_lock.release()
