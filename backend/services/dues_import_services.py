"""Read membership-sheet checkboxes and import dues claims for their academic year.

Only TRUE grants dues. Verified claims survive later unchecks and missing rows.
"""

import json
import logging
import os
import re
from datetime import datetime
from threading import Lock

import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import Session

from models.dues_import import DuesSyncResult, ImportedDues
from services.shop_services import DUES_RESET_DAY, DUES_RESET_MONTH
from services.time_services import utcnow

logger = logging.getLogger(__name__)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets.readonly"]
PSID_HEADER = "student psid"
VERIFIED_HEADER = "payment verified?"
_sync_lock = Lock()


def is_configured() -> bool:
    """Return whether both dedicated dues settings are present."""
    return all(os.getenv(name, "").strip() for name in ("DUES_TRACKER_CREDENTIALS", "DUES_SHEET_ID"))


def get_sheet() -> gspread.Spreadsheet | None:
    """Open the configured membership spreadsheet with read-only credentials.

    Returns:
        The spreadsheet, or None when dues sync is unconfigured.
    """
    if not is_configured():
        return None
    credentials_value = os.environ["DUES_TRACKER_CREDENTIALS"].strip()
    if credentials_value.startswith("{"):
        credentials = Credentials.from_service_account_info(json.loads(credentials_value), scopes=SCOPES)
    else:
        credentials = Credentials.from_service_account_file(credentials_value, scopes=SCOPES)
    client = gspread.authorize(credentials)
    client.set_timeout(30)
    return client.open_by_key(os.environ["DUES_SHEET_ID"].strip())


def period_from_title(title: str) -> datetime:
    """Resolve one consecutive academic-year pair to its dues reset date.

    Args:
        title: Spreadsheet title containing a year pair such as 2026-2027.
    Returns:
        The May 30 period start; raises ValueError for an ambiguous or invalid title.
    """
    year_pairs = re.findall(r"(?<!\d)(20\d{2})\s*[-–]\s*(20\d{2})(?!\d)", title)
    if len(year_pairs) != 1:
        raise ValueError("Spreadsheet title must contain exactly one academic year, such as 2026-2027.")
    start_year, end_year = map(int, year_pairs[0])
    if end_year != start_year + 1:
        raise ValueError("Spreadsheet academic years must be consecutive.")
    return datetime(start_year, DUES_RESET_MONTH, DUES_RESET_DAY)


def parse_sheet_rows(values: list[list[str]]) -> tuple[dict[str, bool], int]:
    """Validate headers and merge payment claims by PSID.

    Args:
        values: Worksheet cells as strings, including the header row.
    Returns:
        Verification by PSID and the skipped-row count; invalid headers raise ValueError.
    """
    headers = [header.strip().casefold() for header in values[0]] if values else []
    if any(headers.count(header) != 1 for header in (PSID_HEADER, VERIFIED_HEADER)):
        raise ValueError("Expected one Student PSID column and one Payment Verified? column.")
    psid_column = headers.index(PSID_HEADER)
    verified_column = headers.index(VERIFIED_HEADER)
    claims: dict[str, bool] = {}
    skipped = 0
    for row_number, row in enumerate(values[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        psid = row[psid_column].strip() if len(row) > psid_column else ""
        if not re.fullmatch(r"[0-9]{7}", psid):
            logger.warning("Skipping dues row %s with invalid PSID %r", row_number, psid[:32])
            skipped += 1
            continue
        checkbox = row[verified_column].strip().casefold() if len(row) > verified_column else ""
        claims[psid] = claims.get(psid, False) or checkbox == "true"
    return claims, skipped


def save_claims(
    session: Session,
    sheet: gspread.Spreadsheet,
    period_start: datetime,
    claims: dict[str, bool],
) -> None:
    """Upsert a validated snapshot without revoking previously verified dues.

    Args:
        session: Database session used to commit or roll back the import.
        sheet: Source spreadsheet metadata.
        period_start: Membership period established by the sheet title.
        claims: Deduplicated PSIDs and their current checkbox values.
    Returns:
        None.
    """
    if not claims:
        return
    imported_at = utcnow()
    rows = [
        {
            "psid": psid,
            "period_start": period_start,
            "verified": verified,
            "source_sheet_id": getattr(sheet, "id", None),
            "source_title": sheet.title,
            "imported_at": imported_at,
            "last_seen_at": imported_at,
        }
        for psid, verified in sorted(claims.items())
    ]
    statement = insert(ImportedDues).values(rows)
    statement = statement.on_conflict_do_update(
        constraint="uq_imported_dues_psid_period",
        set_={
            "verified": ImportedDues.verified | statement.excluded.verified,
            "source_sheet_id": statement.excluded.source_sheet_id,
            "source_title": statement.excluded.source_title,
            "last_seen_at": statement.excluded.last_seen_at,
        },
    )
    try:
        session.execute(statement)
        session.commit()
    except Exception:
        session.rollback()
        raise


def sync_dues(session: Session) -> DuesSyncResult:
    """Import one sheet snapshot, skipping overlapping sync attempts.

    Args:
        session: Database session for the import.
    Returns:
        Counts and outcome; network and database errors propagate to the caller.
    """
    if not _sync_lock.acquire(blocking=False):
        return DuesSyncResult(status="busy")
    try:
        sheet = get_sheet()
        if sheet is None:
            return DuesSyncResult(status="unconfigured")
        values = sheet.sheet1.get_all_values()
        try:
            period_start = period_from_title(sheet.title)
            claims, skipped = parse_sheet_rows(values)
        except ValueError as error:
            logger.warning("Dues import aborted: %s", error)
            return DuesSyncResult(status="invalid_sheet", message=str(error))
        save_claims(session, sheet, period_start, claims)
        result = DuesSyncResult(
            status="synced",
            period_start=period_start,
            processed=len(claims),
            verified=sum(claims.values()),
            skipped=skipped,
        )
        logger.info("Dues sync: %s claims, %s checked, %s skipped", result.processed, result.verified, result.skipped)
        return result
    finally:
        _sync_lock.release()
