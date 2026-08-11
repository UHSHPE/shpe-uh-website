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

import logging

import pytest
from datetime import date, datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

import services.event_tracker_services as event_tracker_services
from models.committee import Committee
from models.event import Event
from models.event_host import EventHost
from models.user.user_enums import Role
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

    Call this again for each _stub_fetch if a test syncs more than once and
    cares about host_roles: sync_events pops "host_roles" off the dict it's
    given (mutating it in place), so reusing one dict/list across two
    sync_events() calls silently hands the second call host_roles=[].
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


def make_committee(session, name="Social", chair_role=Role.social_chair):
    """A Committee row for EventHost reconciliation tests -- not from
    seed.py, so tests stay independent of the real roster.
    """
    committee = Committee(name=name, description="Test committee", chair_role=chair_role)
    session.add(committee)
    session.commit()
    session.refresh(committee)
    return committee


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

def test_points_value_survives_an_update(session, monkeypatch):
    # points_value isn't in the sheet at all -- an update must not clobber
    # whatever a chair has set for it in the dashboard.
    key = event_key(date(2026, 8, 5), "GBM 1")
    make_event(session, source_row_id=key, title="GBM 1", points_value=50)

    _stub_fetch(monkeypatch, [fake_sheet_event(source_row_id=key, title="GBM 1", location="New Location")])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 1)
    event = session.exec(select(Event).where(Event.source_row_id == key)).one()
    assert event.location == "New Location"
    assert event.points_value == 50


def test_event_type_is_overwritten_from_the_sheet(session, monkeypatch):
    # Unlike points_value, event_type IS sheet-derived now -- parse_row
    # always returns it, so an update must overwrite whatever was there
    # before, even a hand-set value like "Workshop" that predates this
    # feature. (This is the half of the old combined test whose premise
    # flipped: event_type used to survive updates same as points_value: now
    # it doesn't, on purpose.)
    key = event_key(date(2026, 8, 5), "GBM 1")
    make_event(session, source_row_id=key, title="GBM 1", event_type="Workshop")

    _stub_fetch(monkeypatch, [
        fake_sheet_event(source_row_id=key, title="GBM 1", event_type="social"),
    ])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 1)
    event = session.exec(select(Event).where(Event.source_row_id == key)).one()
    assert event.event_type == "social"

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


# --- event_type backfill ---

def test_sync_sets_event_type_on_a_new_event(session, monkeypatch):
    _stub_fetch(monkeypatch, [fake_sheet_event(event_type="social")])

    sync_events(session)

    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    assert event.event_type == "social"

def test_sync_backfills_event_type_on_an_existing_event(session, monkeypatch):
    # An event synced before this feature shipped has event_type=None
    # forever unless a later sync backfills it. event_type now rides the
    # same dict as every other sheet field, so the existing setattr update
    # loop does this for free -- no special-case code needed.
    key = event_key(date(2026, 8, 5), "GBM 1")
    make_event(session, source_row_id=key, title="GBM 1", event_type=None)

    _stub_fetch(monkeypatch, [fake_sheet_event(source_row_id=key, title="GBM 1", event_type="social")])
    sync_events(session)

    event = session.exec(select(Event).where(Event.source_row_id == key)).one()
    assert event.event_type == "social"


# --- EventHost reconciliation ---

def test_sync_creates_one_host_for_owner_only(session, monkeypatch):
    make_committee(session, name="Social", chair_role=Role.social_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])

    sync_events(session)

    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 1

def test_sync_creates_two_hosts_for_owner_plus_committee_collab(session, monkeypatch):
    make_committee(session, name="Social", chair_role=Role.social_chair)
    make_committee(session, name="EEC", chair_role=Role.eec_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair, Role.eec_chair])])

    sync_events(session)

    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 2

def test_sync_ignores_an_outside_org_collab(session, monkeypatch):
    # An outside-org collab (e.g. "NSBE") never resolves to a Role --
    # resolve_committee already dropped it by the time parse_row built
    # host_roles, so sync_events only ever sees the owner's role here. That
    # makes this mechanically identical to the owner-only case above; the
    # point is documenting that the org contributes no host row.
    make_committee(session, name="Social", chair_role=Role.social_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])

    sync_events(session)

    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 1

def test_resyncing_does_not_duplicate_hosts_or_raise(session, monkeypatch):
    # The landmine this reconciliation exists to defuse: sync_events has no
    # per-row try/except (that isolation lives in fetch_sheet_events), so a
    # blind session.add(EventHost(...)) on the second sync would raise
    # IntegrityError on the composite PK at commit and kill the ENTIRE sync,
    # not just one row. The wanted - existing_hosts set difference is what
    # prevents that.
    #
    # Re-stub with a FRESH fake_sheet_event() call for the second sync rather
    # than reusing the first list: sync_events pops "host_roles" off the dict
    # it's handed, which mutates that dict in place. Reusing the same dict
    # object across two sync_events() calls would silently hand the second
    # call an already-stripped host_roles=[] and this test would prove
    # nothing (it would "pass" by deleting the host, not by leaving it alone).
    make_committee(session, name="Social", chair_role=Role.social_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])
    sync_events(session)

    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])
    sync_events(session)   # would raise IntegrityError if hosts were re-added blindly

    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 1

def test_sync_removes_a_host_dropped_from_the_sheet(session, monkeypatch):
    # Host reconciliation deletes stale rows -- a deliberate, narrow
    # exception to this file's no-delete rule (EventHost has no dependents,
    # unlike Event, where deleting orphans EventReminder rows and resets
    # points_value). Without this, a collab pulled from the sheet would keep
    # that chair able to see and mint QR codes for an event they no longer run.
    social = make_committee(session, name="Social", chair_role=Role.social_chair)
    make_committee(session, name="EEC", chair_role=Role.eec_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair, Role.eec_chair])])
    sync_events(session)

    # EEC collab removed from the sheet on the next pull.
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])
    sync_events(session)

    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    hosts = session.exec(select(EventHost.committee_id).where(EventHost.event_id == event.id)).all()
    assert hosts == [social.id]

def test_sync_creates_host_for_bare_eboard_owner_via_generic_committee(session, monkeypatch):
    # The bare "eboard" sheet value now resolves to None (not "no match"),
    # which must reconcile against a Committee row whose chair_role is
    # genuinely None (seed.py's generic "E-Board" committee) rather than
    # being dropped like a real non-match (blank cell, outside-org collab).
    make_committee(session, name="E-Board", chair_role=None)
    _stub_fetch(monkeypatch, [fake_sheet_event(event_type="eboard", host_roles=[None])])

    sync_events(session)

    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 1


def test_sync_eboard_event_has_no_hosts(session, monkeypatch):
    _stub_fetch(monkeypatch, [fake_sheet_event(event_type="eboard", host_roles=[])])

    sync_events(session)

    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert event.event_type == "eboard"
    assert hosts == []

def test_sync_skips_a_host_role_with_no_committee_row(session, monkeypatch, caplog):
    # No Committee row exists for Role.social_chair here -- committee_ids
    # simply has no entry for it. This must not crash the sync; the event
    # itself still gets created, just with no host row for the missing role.
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])

    with caplog.at_level(logging.WARNING):
        created, updated = sync_events(session)

    assert (created, updated) == (1, 0)
    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert hosts == []
    assert caplog.records


# --- host_roles must never reach the Event model ---

def test_host_roles_never_reaches_the_event_model_on_create(session, monkeypatch):
    # host_roles is a different table (EventHost) -- Event has no such
    # column, so it must be popped off before Event(**data).
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])

    sync_events(session)   # must not raise

    event = session.exec(select(Event).where(Event.source_row_id == "2026-08-05|gbm 1")).one()
    assert not hasattr(event, "host_roles")

def test_host_roles_never_reaches_the_event_model_on_update(session, monkeypatch):
    # This is the branch that actually proves the pop is load-bearing:
    # setattr(existing, "host_roles", ...) raises ValueError on a SQLModel
    # instance ("... object has no field ...") -- unlike the Event(**data)
    # constructor exercised above, which silently drops an unrecognized kwarg.
    key = event_key(date(2026, 8, 5), "GBM 1")
    make_event(session, source_row_id=key, title="GBM 1")

    _stub_fetch(monkeypatch, [fake_sheet_event(source_row_id=key, host_roles=[Role.social_chair])])
    sync_events(session)   # must not raise ValueError

    event = session.exec(select(Event).where(Event.source_row_id == key)).one()
    assert not hasattr(event, "host_roles")
