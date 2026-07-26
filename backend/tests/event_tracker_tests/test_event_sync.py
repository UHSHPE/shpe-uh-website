# Event-tracker DB reconciliation tests.
#
# Two different fake seams, on purpose:
#   - fetch_sheet_events tests monkeypatch get_worksheet with a stub gspread
#     worksheet, so the real parse_row path and the row-2 template skip both
#     actually execute.
#   - sync_events tests monkeypatch fetch_sheet_events directly, so they only
#     exercise DB reconciliation and don't re-test parsing.
#
# No test here ever reaches the network: the autouse disable_event_tracker_sync
# fixture in tests/conftest.py clears CREDENTIALS/SHEET_ID for every test.

import pytest
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

import services.event_tracker_services as event_tracker_services
from models.event import Event
from services.event_tracker_services import event_key, fetch_sheet_events, sync_events
from tests.conftest import make_event
from tests.event_tracker_tests.test_event_parsing import sheet_row


# --- helpers ---

class FakeWorksheet:
    """Stands in for a gspread Worksheet -- fetch_sheet_events only ever
    calls get_all_records() on it."""

    def __init__(self, records):
        self._records = records

    def get_all_records(self):
        return self._records


def _stub_worksheet(monkeypatch, records):
    monkeypatch.setattr(event_tracker_services, "get_worksheet", lambda: FakeWorksheet(records))


def _stub_fetch(monkeypatch, rows):
    monkeypatch.setattr(event_tracker_services, "fetch_sheet_events", lambda: rows)


def fake_sheet_event(**overrides):
    """A dict shaped like parse_row's output -- what fetch_sheet_events
    returns for one row. NOT a DB row (contrast with make_event, which
    persists a real Event): this is the input sync_events reconciles
    against the DB.
    """
    fields = dict(
        source_row_id="2026-08-05|gbm 1",
        title="GBM 1",
        description="Come hang out with SHPE!",
        location="PGH 232",
        start_time=datetime(2026, 8, 5, 23, 0),
        end_time=None,
    )
    fields.update(overrides)
    return fields


# --- schema constraint: source_row_id unique index ---

def test_duplicate_non_null_source_row_id_raises_integrity_error(session):
    session.add(Event(title="A", start_time=datetime(2026, 8, 5, 23, 0), source_row_id="dup-key"))
    session.add(Event(title="B", start_time=datetime(2026, 8, 6, 23, 0), source_row_id="dup-key"))

    with pytest.raises(IntegrityError):
        session.commit()

def test_multiple_null_source_row_ids_coexist(session):
    # SQL unique indexes treat NULLs as distinct -- this is what lets
    # seed.py / hand-added events (no source_row_id) coexist freely.
    session.add(Event(title="A", start_time=datetime(2026, 8, 5, 23, 0), source_row_id=None))
    session.add(Event(title="B", start_time=datetime(2026, 8, 6, 23, 0), source_row_id=None))
    session.commit()

    assert len(session.exec(select(Event)).all()) == 2


# --- fetch_sheet_events (stubs get_worksheet) ---

def test_fetch_unconfigured_returns_empty_and_touches_no_network():
    # conftest's autouse disable_event_tracker_sync fixture clears
    # CREDENTIALS/SHEET_ID, so get_worksheet() returns None on its own --
    # no monkeypatch needed (or wanted) for this case.
    assert fetch_sheet_events() == []

def test_fetch_skips_the_row_2_template_row(monkeypatch):
    template_row = sheet_row(name="SHOULD NEVER APPEAR - TEMPLATE ROW")
    real_row = sheet_row(name="GBM 1")
    _stub_worksheet(monkeypatch, [template_row, real_row])

    events = fetch_sheet_events()

    assert [e["title"] for e in events] == ["GBM 1"]

def test_fetch_skips_a_bad_row_but_keeps_the_rest(monkeypatch):
    template_row = sheet_row(name="TEMPLATE")
    bad_row = sheet_row(name="Broken Event", date="13/45")   # unparseable date
    good_row = sheet_row(name="GBM 1")
    _stub_worksheet(monkeypatch, [template_row, bad_row, good_row])

    events = fetch_sheet_events()

    assert [e["title"] for e in events] == ["GBM 1"]

def test_fetch_drops_excluded_and_blank_name_rows(monkeypatch):
    template_row = sheet_row(name="TEMPLATE")
    excluded_row = sheet_row(name="C&E Retreat")
    blank_row = sheet_row(name="")
    good_row = sheet_row(name="GBM 1")
    _stub_worksheet(monkeypatch, [template_row, excluded_row, blank_row, good_row])

    events = fetch_sheet_events()

    assert [e["title"] for e in events] == ["GBM 1"]


# --- sync_events (stubs fetch_sheet_events) ---

def test_sync_creates_new_events(session, monkeypatch):
    rows = [
        fake_sheet_event(source_row_id="2026-08-05|gbm 1", title="GBM 1"),
        fake_sheet_event(source_row_id="2026-08-12|gbm 2", title="GBM 2"),
    ]
    _stub_fetch(monkeypatch, rows)

    created, updated = sync_events(session)

    assert (created, updated) == (2, 0)
    assert {e.title for e in session.exec(select(Event)).all()} == {"GBM 1", "GBM 2"}

def test_resyncing_identical_rows_updates_instead_of_duplicating(session, monkeypatch):
    rows = [
        fake_sheet_event(source_row_id="2026-08-05|gbm 1", title="GBM 1"),
        fake_sheet_event(source_row_id="2026-08-12|gbm 2", title="GBM 2"),
    ]
    _stub_fetch(monkeypatch, rows)
    sync_events(session)

    created, updated = sync_events(session)

    assert (created, updated) == (0, 2)
    assert len(session.exec(select(Event)).all()) == 2

def test_in_place_edit_keeps_the_same_row_id(session, monkeypatch):
    key = "2026-08-05|gbm 1"
    _stub_fetch(monkeypatch, [fake_sheet_event(source_row_id=key, location="PGH 232")])
    sync_events(session)
    original_id = session.exec(select(Event).where(Event.source_row_id == key)).one().id

    _stub_fetch(monkeypatch, [fake_sheet_event(source_row_id=key, location="PGH 240")])
    sync_events(session)

    event = session.exec(select(Event).where(Event.source_row_id == key)).one()
    assert event.id == original_id
    assert event.location == "PGH 240"

def test_points_value_and_event_type_survive_an_update(session, monkeypatch):
    # points_value and event_type aren't in the sheet at all -- an update
    # must not clobber whatever a chair has set for them in the dashboard.
    key = event_key(date(2026, 8, 5), "GBM 1")
    make_event(session, source_row_id=key, title="GBM 1", points_value=50, event_type="Workshop")

    _stub_fetch(monkeypatch, [fake_sheet_event(source_row_id=key, title="GBM 1", location="New Location")])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 1)
    event = session.exec(select(Event).where(Event.source_row_id == key)).one()
    assert event.location == "New Location"
    assert event.points_value == 50
    assert event.event_type == "Workshop"

def test_rows_with_no_source_row_id_are_untouched_by_sync(session, monkeypatch):
    manual_event = make_event(session, source_row_id=None, title="Hand-Added Social")

    _stub_fetch(monkeypatch, [fake_sheet_event()])
    sync_events(session)

    session.refresh(manual_event)
    assert manual_event.title == "Hand-Added Social"
    assert manual_event.source_row_id is None

def test_dev_mode_sync_is_a_full_noop(session):
    # No monkeypatch here -- relies on the autouse fixture clearing
    # CREDENTIALS/SHEET_ID, exercising the real dev-mode fetch_sheet_events()
    # -> [] path end to end.
    existing = make_event(session, title="Existing Event")

    created, updated = sync_events(session)

    assert (created, updated) == (0, 0)
    session.refresh(existing)
    assert existing.title == "Existing Event"
    assert len(session.exec(select(Event)).all()) == 1

def test_reschedule_adds_a_new_row_instead_of_moving_the_old_one(session, monkeypatch):
    # There is deliberately no delete/sweep pass: rescheduling an event to a
    # new date bakes a new key (the date is part of event_key), so
    # sync_events treats it as a brand-new event and leaves the old row
    # behind. This is accepted behavior, not a bug -- don't "fix" it by
    # adding a sweep pass.
    _stub_fetch(monkeypatch, [fake_sheet_event(
        source_row_id=event_key(date(2026, 8, 5), "GBM 1"), title="GBM 1",
    )])
    sync_events(session)

    _stub_fetch(monkeypatch, [fake_sheet_event(
        source_row_id=event_key(date(2026, 8, 12), "GBM 1"), title="GBM 1",
    )])
    created, updated = sync_events(session)

    assert (created, updated) == (1, 0)
    assert len(session.exec(select(Event).where(Event.title == "GBM 1")).all()) == 2

def test_two_rows_sharing_one_key_in_one_sync_yield_one_db_row(session, monkeypatch):
    # When two sheet rows share a source_row_id in the SAME pull: the first
    # is session.add()-ed (not yet flushed); the second row's SELECT (inside
    # sync_events' existing-lookup) triggers SQLAlchemy's autoflush, which
    # flushes the first pending INSERT before the SELECT runs -- so the
    # second row's lookup finds the first (now-flushed) row as "existing"
    # and updates it in place. Net effect: no IntegrityError, no duplicate
    # row -- one DB row left holding the SECOND row's values, and
    # (created, updated) == (1, 1).
    dup_key = event_key(date(2026, 8, 5), "GBM 1")
    rows = [
        fake_sheet_event(source_row_id=dup_key, description="first"),
        fake_sheet_event(source_row_id=dup_key, description="second"),
    ]
    _stub_fetch(monkeypatch, rows)

    created, updated = sync_events(session)

    assert (created, updated) == (1, 1)
    events = session.exec(select(Event).where(Event.source_row_id == dup_key)).all()
    assert len(events) == 1
    assert events[0].description == "second"

def test_resyncing_unchanged_sheet_does_not_raise_integrity_error(session, monkeypatch):
    # Regression guard on the source_row_id unique constraint: a clean
    # re-sync must take the update path on the second run, never insert path.
    _stub_fetch(monkeypatch, [fake_sheet_event()])
    sync_events(session)

    created, updated = sync_events(session)   # would raise IntegrityError if this mistakenly re-inserted

    assert (created, updated) == (0, 1)
