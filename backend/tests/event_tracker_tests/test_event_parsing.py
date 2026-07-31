# Pure-function tests for event_tracker_services' sheet-parsing helpers --
# no DB, no network involved anywhere in this file (see test_event_sync.py
# for the fetch_sheet_events / sync_events DB-reconciliation tests).
#
# Recorded assumption, not a bug: end_time is derived from the same DATE
# column as start_time, so an event that ran past midnight would get an
# end_time on the wrong day. The user confirmed no SHPE events run past
# midnight, so that case is intentionally not exercised below.

import logging

import pytest
from datetime import date, datetime, time

from models.user.user_enums import CHAIR_ROLES, Role
from services.event_tracker_services import (
    COLUMNS,
    COMMITTEE_ROLES,
    EBOARD,
    SHEET_TZ,
    event_key,
    get_event_type,
    parse_date,
    parse_row,
    parse_time,
    resolve_committee,
    to_utc,
)


# --- helpers ---

def sheet_row(**overrides):
    """Build a raw sheet-row dict keyed by the real column headers (COLUMNS
    values). Kwargs use the COLUMNS *keys* (name=, date=, start_time=, ...)
    for readability -- this maps them to the actual header strings that the
    sheet (and parse_row) use.
    """
    fields = dict(
        name="GBM 1",
        date="08/05",
        description="Come hang out with SHPE!",
        location="PGH 232",
        start_time="6:00 PM",
        end_time="7:00 PM",
        owners="Marketing Chair - Valeria Zabala",
    )
    fields["collab(s)"] = ""
    fields.update(overrides)
    return {COLUMNS[key]: value for key, value in fields.items()}


# --- parse_time ---

@pytest.mark.parametrize("raw, expected", [
    ("6:00 PM", time(18, 0)),
    ("6:00:00 PM", time(18, 0)),
    ("18:00", time(18, 0)),
    ("18:00:00", time(18, 0)),
    ("", None),
    (None, None),
    ("   ", None),
    ("All Day", None),
    ("TBD", None),
])
def test_parse_time(raw, expected):
    assert parse_time(raw) == expected


# --- parse_date ---

@pytest.mark.parametrize("raw", ["08/05", "  08/05", "08/05  ", "  08/05  "])
def test_parse_date_uses_the_current_central_year(raw):
    # Never hardcode a year -- the sheet's DATE column has no year, so
    # parse_date always assumes "this year" (Central time). Also covers
    # leading/trailing whitespace tolerance in the same parametrize.
    year = datetime.now(SHEET_TZ).year
    assert parse_date(raw) == date(year, 8, 5)

def test_parse_date_invalid_date_raises():
    with pytest.raises(ValueError):
        parse_date("13/45")

def test_parse_date_blank_raises():
    with pytest.raises(ValueError):
        parse_date("")


# --- event_key ---

def test_event_key_normalizes_case_and_whitespace():
    assert event_key(date(2026, 8, 5), "  GBM   1 ") == "2026-08-05|gbm 1"

def test_event_key_differs_when_only_the_date_changes():
    # Pins the reschedule behavior relied on in test_event_sync.py: moving
    # the same-named event to a new date produces a DIFFERENT key, so a sync
    # treats it as a new event rather than an edit of the old one.
    key_on_aug_5 = event_key(date(2026, 8, 5), "GBM 1")
    key_on_aug_12 = event_key(date(2026, 8, 12), "GBM 1")
    assert key_on_aug_5 != key_on_aug_12


# --- parse_row ---

def test_parse_row_happy_path_maps_all_eight_fields():
    year = datetime.now(SHEET_TZ).year
    row = sheet_row(
        name="GBM 1",
        date="08/05",
        description="Come hang out with SHPE!",
        location="PGH 232",
        start_time="6:00 PM",
        end_time="7:00 PM",
    )

    parsed = parse_row(row)

    assert set(parsed.keys()) == {
        "source_row_id", "title", "description", "location", "start_time", "end_time",
        "event_type", "host_roles",
    }
    assert parsed["source_row_id"] == event_key(date(year, 8, 5), "GBM 1")
    assert parsed["title"] == "GBM 1"
    assert parsed["description"] == "Come hang out with SHPE!"
    assert parsed["location"] == "PGH 232"
    assert parsed["start_time"] == to_utc(datetime(year, 8, 5, 18, 0))
    assert parsed["end_time"] == to_utc(datetime(year, 8, 5, 19, 0))
    # owners defaults to a Marketing Chair value and collab(s) to blank --
    # see sheet_row().
    assert parsed["event_type"] == "marketing"
    assert parsed["host_roles"] == [Role.marketing_chair]

def test_parse_row_blank_name_returns_none():
    assert parse_row(sheet_row(name="")) is None

def test_parse_row_whitespace_only_name_returns_none():
    assert parse_row(sheet_row(name="   ")) is None

def test_parse_row_missing_start_time_defaults_to_local_midnight():
    row = sheet_row()
    del row[COLUMNS["start_time"]]
    year = datetime.now(SHEET_TZ).year

    parsed = parse_row(row)

    assert parsed["start_time"] == to_utc(datetime(year, 8, 5, 0, 0))

def test_parse_row_all_day_start_defaults_to_local_midnight():
    year = datetime.now(SHEET_TZ).year
    parsed = parse_row(sheet_row(start_time="All Day"))
    assert parsed["start_time"] == to_utc(datetime(year, 8, 5, 0, 0))

def test_parse_row_blank_end_time_is_none():
    parsed = parse_row(sheet_row(end_time=""))
    assert parsed["end_time"] is None

def test_parse_row_title_whitespace_is_collapsed():
    parsed = parse_row(sheet_row(name="  GBM   1  "))
    assert parsed["title"] == "GBM 1"


# --- DST: local -> UTC conversion crosses the day boundary in winter only ---

def test_august_event_converts_cdt_to_utc_same_day():
    """August is Central Daylight Time (UTC-5): 6:00 PM local -> 23:00 UTC
    the SAME day."""
    year = datetime.now(SHEET_TZ).year
    parsed = parse_row(sheet_row(date="08/05", start_time="6:00 PM"))
    assert parsed["start_time"] == datetime(year, 8, 5, 23, 0)

def test_january_event_converts_cst_to_utc_next_day():
    """January is Central Standard Time (UTC-6): 6:00 PM local -> 00:00 UTC
    the NEXT day."""
    year = datetime.now(SHEET_TZ).year
    parsed = parse_row(sheet_row(date="01/15", start_time="6:00 PM"))
    assert parsed["start_time"] == datetime(year, 1, 16, 0, 0)


# --- excluded events ---

@pytest.mark.parametrize("name", ["C&E Retreat", "C&E RETREAT", "  c&e   retreat  "])
def test_parse_row_excludes_hidden_events_regardless_of_case_or_spacing(name):
    assert parse_row(sheet_row(name=name)) is None

def test_excluded_event_with_a_garbage_date_is_dropped_without_raising():
    # The exclusion check runs before parse_date, so it short-circuits -- a
    # bad date on an already-excluded row never reaches the code that would
    # otherwise raise on it.
    row = sheet_row(name="C&E Retreat", date="not-a-date")
    assert parse_row(row) is None


# --- get_event_type: OWNER(S) values -> event_type ---
#
# get_event_type and resolve_committee share one normalizer
# (_normalize_owner) and both lookup tables (COMMITTEE_ROLES, EBOARD), so
# they're exercised together in this section rather than split in two.

@pytest.mark.parametrize("raw, expected_type", [
    ("Social Chair - Anahi Salinas", "social"),
    ("MentorSHPE Chairs - Nicolas Horton", "mentorshpe"),               # plural "Chairs"
    ("MentorSHPE Chair - Nicolas Horton | Mia Flores", "mentorshpe"),   # co-chairs, pipe after the dash
    ("EEC Chair - David Cohen", "eec"),
    ("Wellness & Athletics Chair - Smiley Trenton", "athletic"),        # "&" preserved, not normalized
    ("SHPE Jr. Chair - Isabela Morales", "shpe_jr"),                    # trailing "." preserved
    ("CFC Chair - Sara Romero", "career_fair"),
    ("  social   chair  -  x  ", "social"),                             # case + whitespace tolerance
    ("Social Chair – X", "social"),                                     # en dash (Sheets autocorrects to this)
])
def test_get_event_type_owner_values(raw, expected_type):
    assert get_event_type(raw) == expected_type


@pytest.mark.parametrize("raw", ["", None])
def test_get_event_type_blank_is_none_and_logs_nothing(raw, caplog):
    # An unfilled OWNER(S) cell isn't a positive claim about E-Board -- it
    # must not be silently filed under "eboard". It's also not anomalous
    # enough to warn about.
    with caplog.at_level(logging.WARNING):
        assert get_event_type(raw) is None
    assert caplog.records == []


# --- resolve_committee: bare COLLAB(S)? values -> Role ---

@pytest.mark.parametrize("raw, expected_role", [
    ("eec", Role.eec_chair),
    ("academic", Role.academic_chair),
])
def test_resolve_committee_bare_collab_value(raw, expected_role):
    # A bare COLLAB(S)? value has neither a dash nor a "Chair" suffix, so
    # both _normalize_owner strips are no-ops and it falls straight through
    # to the lookup -- the same function that serves the OWNER(S) column.
    assert resolve_committee(raw) == expected_role


def test_resolve_committee_project_spelling_variants_agree():
    # OWNER(S) offers "Project"; COLLAB(S)? offers "Projects" -- the two
    # dropdowns disagree on spelling, and both must resolve to the same Role.
    assert resolve_committee("project") == Role.projects_chair
    assert resolve_committee("Projects") == Role.projects_chair


def test_resolve_committee_shpe_jr_spelling_variants_agree():
    # Same divergence: OWNER(S)'s trailing "." vs COLLAB(S)?'s bare "SHPE Jr".
    assert resolve_committee("SHPE Jr.") == Role.shpe_jr_chair
    assert resolve_committee("SHPE Jr") == Role.shpe_jr_chair


# --- E-Board and the unknown case ---

@pytest.mark.parametrize("raw", sorted(EBOARD))
def test_get_event_type_eboard_values_log_nothing(raw, caplog):
    # All ten EBOARD members are expected, positively-whitelisted values --
    # none of them should ever trip the "unrecognized owner" warning.
    with caplog.at_level(logging.WARNING):
        assert get_event_type(raw) == "eboard"
    assert caplog.records == []


def test_get_event_type_eboard_with_dash_and_name():
    # Not just the bare value -- an officer's OWNER(S) cell looks like a
    # chair's, dash and name included.
    assert get_event_type("VPE - Carlos Alba") == "eboard"


@pytest.mark.parametrize("raw", ["NSBE", "SWE"])
def test_resolve_committee_outside_org_is_none_and_logs_nothing(raw, caplog):
    # An outside org in COLLAB(S)? is the NORMAL case, not an anomaly -- a
    # warning here would be noise on every collab event. All logging lives
    # in get_event_type, not resolve_committee.
    with caplog.at_level(logging.WARNING):
        assert resolve_committee(raw) is None
    assert caplog.records == []


def test_get_event_type_unlisted_owner_files_under_eboard_with_a_warning(caplog):
    # The pair with the NSBE/SWE test above: a genuinely unrecognized
    # OWNER(S) value (a new dropdown option next semester, a typo, ...) is
    # loud where an outside collab is silent. It still files under "eboard"
    # rather than None so the event stays reachable by someone likely to
    # notice the mistake.
    with caplog.at_level(logging.WARNING):
        result = get_event_type("Robotics Club")
    assert result == "eboard"
    assert len(caplog.records) == 1
    assert "Robotics Club" in caplog.records[0].getMessage()


# --- table completeness ---

def test_committee_roles_table_is_complete_and_disjoint_from_eboard():
    # Every value maps to one of the 14 real chair roles...
    assert set(COMMITTEE_ROLES.values()) <= CHAIR_ROLES
    # ...and every chair role is reachable through at least one key -- this
    # is exactly what would auto-catch the next CFC-style omission (a
    # committee with a Role but no dropdown key pointing at it).
    assert set(COMMITTEE_ROLES.values()) == CHAIR_ROLES
    # No sheet spelling can be classified two different ways depending on
    # which lookup table runs first.
    assert not (set(COMMITTEE_ROLES) & EBOARD)
