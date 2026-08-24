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
#
# Identity is the SHEET ROW NUMBER paired with the row's Central date -- see
# sync_events' docstring. Every event in this file is therefore built around a
# (sheet_row, start_time) pair, and start_time is always relative to now rather
# than a hardcoded calendar date: rule 3 freezes events that have already
# started, so a fixed date would quietly change these tests' meaning the day it
# went past.

import logging

import pytest
from datetime import datetime, timedelta

from sqlmodel import select

import services.event_tracker_services as event_tracker_services
from models.committee import Committee
from models.event import Event
from models.event_host import EventHost
from models.event_reminder import EventReminder
from models.user.user_enums import Role
from services.event_tracker_services import fetch_sheet_events, local_date, sync_events
from services.time_services import utcnow
from tests.conftest import make_event, make_user
from tests.event_tracker_tests.test_event_parsing import sheet_row


# --- helpers ---

FUTURE = utcnow() + timedelta(days=7)
LATER = utcnow() + timedelta(days=21)
PAST = utcnow() - timedelta(days=7)


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
        sheet_row=3,
        title="GBM 1",
        description="Come hang out with SHPE!",
        location="PGH 232",
        start_time=FUTURE,
        end_time=None,
    )
    fields.update(overrides)
    return fields


def synced_event(session, **overrides):
    """A DB event that looks like it came from the sheet, matching
    fake_sheet_event()'s identity (row 3 on FUTURE's Central date) unless
    overridden."""
    fields = dict(sheet_row=3, title="GBM 1", start_time=FUTURE)
    fields.update(overrides)
    return make_event(session, **fields)


def make_committee(session, name="Social", chair_role=Role.social_chair):
    """A Committee row for EventHost reconciliation tests -- not from
    seed.py, so tests stay independent of the real roster.
    """
    committee = Committee(name=name, description="Test committee", chair_role=chair_role)
    session.add(committee)
    session.commit()
    session.refresh(committee)
    return committee


def only_event(session, **where):
    stmt = select(Event)
    for field, value in where.items():
        stmt = stmt.where(getattr(Event, field) == value)
    return session.exec(stmt).one()


# --- schema: sheet_row is deliberately NOT unique ---

def test_two_events_may_share_a_sheet_row(session):
    # The tracker is a fixed skeleton whose rows are reused across semesters,
    # and a soft-deleted event keeps its row number -- so a unique index here
    # would turn an ordinary re-fill into an IntegrityError that kills the
    # whole sync. What actually keeps identity unambiguous is the (sheet_row,
    # Central date) pair sync_events matches on, not a DB constraint.
    session.add(Event(title="Fall", start_time=PAST, sheet_row=40))
    session.add(Event(title="Spring", start_time=FUTURE, sheet_row=40))
    session.commit()

    assert len(session.exec(select(Event).where(Event.sheet_row == 40)).all()) == 2

def test_multiple_null_sheet_rows_coexist(session):
    # sheet_row IS NULL is what marks a seeded / hand-added event, and
    # sync_events never touches those.
    session.add(Event(title="A", start_time=FUTURE, sheet_row=None))
    session.add(Event(title="B", start_time=LATER, sheet_row=None))
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

def test_fetch_numbers_rows_from_the_real_spreadsheet_row(monkeypatch):
    # get_all_records() has already consumed row 1 as the header and [1:]
    # drops the row-2 template, so the first event is spreadsheet row 3.
    # This number IS the sync's identity -- an off-by-one here silently
    # re-identifies every event on the calendar.
    _stub_worksheet(monkeypatch, [
        sheet_row(name="TEMPLATE"),
        sheet_row(name="GBM 1"),
        sheet_row(name="GBM 2"),
    ])

    events = fetch_sheet_events()

    assert [e["sheet_row"] for e in events] == [3, 4]

def test_fetch_keeps_row_numbers_aligned_when_a_row_is_dropped(monkeypatch):
    # A blank or excluded row still occupies its spreadsheet row, so the rows
    # after it must keep their real numbers -- numbering the surviving rows
    # instead would shift every event below any blank row.
    _stub_worksheet(monkeypatch, [
        sheet_row(name="TEMPLATE"),
        sheet_row(name=""),               # row 3, blank
        sheet_row(name="C&E Retreat"),    # row 4, excluded
        sheet_row(name="GBM 1"),          # row 5
    ])

    events = fetch_sheet_events()

    assert [(e["title"], e["sheet_row"]) for e in events] == [("GBM 1", 5)]

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


# --- rule 1: upsert by (sheet_row, Central date) ---

def test_sync_creates_new_events(session, monkeypatch):
    _stub_fetch(monkeypatch, [
        fake_sheet_event(sheet_row=3, title="GBM 1"),
        fake_sheet_event(sheet_row=9, title="GBM 2", start_time=LATER),
    ])

    created, updated = sync_events(session)

    assert (created, updated) == (2, 0)
    assert {e.title for e in session.exec(select(Event)).all()} == {"GBM 1", "GBM 2"}

def test_resyncing_identical_rows_updates_instead_of_duplicating(session, monkeypatch):
    for _ in range(2):
        _stub_fetch(monkeypatch, [
            fake_sheet_event(sheet_row=3, title="GBM 1"),
            fake_sheet_event(sheet_row=9, title="GBM 2", start_time=LATER),
        ])
        created, updated = sync_events(session)

    assert (created, updated) == (0, 2)
    assert len(session.exec(select(Event)).all()) == 2

def test_renaming_a_row_updates_in_place_instead_of_duplicating(session, monkeypatch):
    # THE bug this design exists to fix. The old identity was
    # "<date>|<title>", so renaming an event minted a fresh key, inserted a
    # second event and stranded the first on the calendar forever. The row
    # number doesn't move when a chair retypes the name, so this is an edit.
    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=12, title="Study Night")])
    sync_events(session)
    original_id = only_event(session, sheet_row=12).id

    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=12, title="Resume Workshop")])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 1)
    event = only_event(session, sheet_row=12)     # .one() -- no duplicate
    assert event.id == original_id
    assert event.title == "Resume Workshop"

def test_in_place_edit_keeps_the_same_event(session, monkeypatch):
    _stub_fetch(monkeypatch, [fake_sheet_event(location="PGH 232")])
    sync_events(session)
    original_id = only_event(session, sheet_row=3).id

    _stub_fetch(monkeypatch, [fake_sheet_event(location="PGH 240")])
    sync_events(session)

    event = only_event(session, sheet_row=3)
    assert event.id == original_id
    assert event.location == "PGH 240"

def test_a_time_change_on_the_same_day_updates_in_place(session, monkeypatch):
    # Identity pairs the row with the row's DATE, not its full timestamp, so
    # moving an event from 6 PM to 7 PM is an edit, not a new event.
    _stub_fetch(monkeypatch, [fake_sheet_event(start_time=FUTURE)])
    sync_events(session)
    original_id = only_event(session, sheet_row=3).id

    later_same_day = FUTURE + timedelta(hours=1)
    assert local_date(later_same_day) == local_date(FUTURE)
    _stub_fetch(monkeypatch, [fake_sheet_event(start_time=later_same_day)])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 1)
    event = only_event(session, sheet_row=3)
    assert event.id == original_id
    assert event.start_time == later_same_day

def test_points_value_survives_an_update(session, monkeypatch):
    # points_value isn't in the sheet at all -- an update must not clobber it.
    synced_event(session, points_value=50)

    _stub_fetch(monkeypatch, [fake_sheet_event(location="New Location")])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 1)
    event = only_event(session, sheet_row=3)
    assert event.location == "New Location"
    assert event.points_value == 50

def test_event_type_is_overwritten_from_the_sheet(session, monkeypatch):
    # Unlike points_value, event_type IS sheet-derived -- parse_row always
    # returns it, so an update must overwrite whatever was there before.
    synced_event(session, event_type="Workshop")

    _stub_fetch(monkeypatch, [fake_sheet_event(event_type="social")])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 1)
    assert only_event(session, sheet_row=3).event_type == "social"

def test_sync_backfills_event_type_on_an_existing_event(session, monkeypatch):
    synced_event(session, event_type=None)

    _stub_fetch(monkeypatch, [fake_sheet_event(event_type="social")])
    sync_events(session)

    assert only_event(session, sheet_row=3).event_type == "social"

def test_attendance_and_hosts_survive_a_rename(session, monkeypatch):
    # The whole point of keeping Event.id stable: an in-place edit must not
    # strand the roster, the reminders or the QR codes.
    social = make_committee(session)
    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=12, title="Study Night",
                                               host_roles=[Role.social_chair])])
    sync_events(session)
    event = only_event(session, sheet_row=12)
    event.sign_in_code = "code-that-must-survive"
    session.add(event)
    user = make_user(session)
    session.add(EventReminder(user_id=user.id, event_id=event.id, remind_at=FUTURE))
    session.commit()

    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=12, title="Resume Workshop",
                                               host_roles=[Role.social_chair])])
    sync_events(session)

    after = only_event(session, sheet_row=12)
    assert after.id == event.id
    assert after.sign_in_code == "code-that-must-survive"
    assert session.exec(select(EventReminder).where(EventReminder.event_id == event.id)).one()
    assert session.exec(
        select(EventHost.committee_id).where(EventHost.event_id == event.id)
    ).all() == [social.id]

def test_a_same_day_time_change_moves_unsent_reminders(session, monkeypatch):
    # remind_at is computed once when the member sets the reminder and never
    # revisited, so a chair correcting an event's start time would otherwise
    # leave the reminder firing on the old schedule -- and the email body
    # reads start_time live, so it would show the corrected time and land as
    # an unexplained early nudge.
    _stub_fetch(monkeypatch, [fake_sheet_event(start_time=FUTURE)])
    sync_events(session)
    event = only_event(session, sheet_row=3)
    user = make_user(session)
    reminder = EventReminder(user_id=user.id, event_id=event.id,
                             remind_at=FUTURE - timedelta(hours=24))
    session.add(reminder)
    session.commit()

    moved = FUTURE + timedelta(hours=2)
    assert local_date(moved) == local_date(FUTURE)      # same row, same day
    _stub_fetch(monkeypatch, [fake_sheet_event(start_time=moved)])
    sync_events(session)

    session.refresh(reminder)
    assert reminder.remind_at == moved - timedelta(hours=24)

def test_changing_a_rows_date_replaces_the_event_instead_of_duplicating(session, monkeypatch):
    # The date is half the identity, so editing it is a reschedule, not an
    # edit: the old event is swept and a new one created. That costs a new
    # Event.id -- accepted, because a rescheduled event is always in the
    # future, so no attendance exists and no QR code is live. What matters is
    # that exactly one event remains visible, which is what the old
    # "<date>|<title>" key got wrong.
    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=12, start_time=FUTURE)])
    sync_events(session)
    original_id = only_event(session, sheet_row=12).id

    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=12, start_time=LATER)])
    created, updated = sync_events(session)

    assert (created, updated) == (1, 0)
    visible = session.exec(
        select(Event).where(Event.sheet_row == 12, Event.deleted_at == None)  # noqa: E711
    ).all()
    assert len(visible) == 1
    assert visible[0].start_time == LATER
    assert session.get(Event, original_id).deleted_at is not None


# --- rule 2: sweep (soft delete) ---

def test_a_cleared_row_soft_deletes_its_future_event(session, monkeypatch):
    _stub_fetch(monkeypatch, [
        fake_sheet_event(sheet_row=3, title="GBM 1"),
        fake_sheet_event(sheet_row=9, title="Study Night", start_time=LATER),
    ])
    sync_events(session)

    # Row 9 blanked in the sheet -- it simply isn't in the next pull.
    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=3, title="GBM 1")])
    sync_events(session)

    swept = only_event(session, sheet_row=9)
    assert swept.deleted_at is not None
    assert only_event(session, sheet_row=3).deleted_at is None

def test_a_swept_event_is_hidden_from_the_public_calendar(session, client, monkeypatch):
    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=9, title="Study Night")])
    sync_events(session)
    assert [e["title"] for e in client.get("/events").json()] == ["Study Night"]

    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=3, title="GBM 1")])
    sync_events(session)

    assert [e["title"] for e in client.get("/events").json()] == ["GBM 1"]

def test_sweeping_deletes_unsent_reminders(session, monkeypatch):
    # Nothing should email a member about an event that's off the calendar,
    # and a leftover reminder row would resurface pointing at whatever event
    # later occupies that row.
    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=9, title="Study Night")])
    sync_events(session)
    event = only_event(session, sheet_row=9)
    user = make_user(session)
    session.add(EventReminder(user_id=user.id, event_id=event.id, remind_at=FUTURE))
    session.commit()

    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=3, title="GBM 1")])
    sync_events(session)

    assert session.exec(select(EventReminder)).all() == []

def test_re_adding_a_cleared_row_undeletes_the_same_event(session, monkeypatch):
    # A chair who blanks a row by mistake and re-fills it gets their event
    # back with the same Event.id -- not a second row beside the hidden one.
    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=9, title="Study Night")])
    sync_events(session)
    original_id = only_event(session, sheet_row=9).id

    _stub_fetch(monkeypatch, [])
    sync_events(session)   # nothing fetched -> see the empty-pull test; sweep is skipped
    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=3, title="GBM 1")])
    sync_events(session)
    assert only_event(session, sheet_row=9).deleted_at is not None

    _stub_fetch(monkeypatch, [
        fake_sheet_event(sheet_row=3, title="GBM 1"),
        fake_sheet_event(sheet_row=9, title="Study Night"),
    ])
    sync_events(session)

    restored = only_event(session, sheet_row=9)
    assert restored.id == original_id
    assert restored.deleted_at is None

def test_an_empty_pull_sweeps_nothing(session, monkeypatch):
    # fetch_sheet_events() returns [] for BOTH an unconfigured instance and a
    # failed fetch, so an empty pull must never be read as "the sheet is
    # empty, hide everything".
    _stub_fetch(monkeypatch, [fake_sheet_event()])
    sync_events(session)

    _stub_fetch(monkeypatch, [])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 0)
    assert only_event(session, sheet_row=3).deleted_at is None

def test_sync_never_sweeps_a_hand_added_event(session, monkeypatch):
    manual_event = make_event(session, sheet_row=None, title="Hand-Added Social")

    _stub_fetch(monkeypatch, [fake_sheet_event()])
    sync_events(session)

    session.refresh(manual_event)
    assert manual_event.title == "Hand-Added Social"
    assert manual_event.sheet_row is None
    assert manual_event.deleted_at is None


# --- rule 3: past events are frozen ---

def test_a_past_event_is_never_modified(session, monkeypatch):
    # Protects attendance history: the only way row identity can go wrong is
    # if someone inserts a row and shifts everything below, and freezing past
    # events means that can never rewrite a roster.
    past = make_event(session, sheet_row=3, title="Old GBM", start_time=PAST)

    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=3, title="Something Else",
                                               start_time=PAST)])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 0)
    session.refresh(past)
    assert past.title == "Old GBM"

def test_a_past_event_is_never_swept(session, monkeypatch):
    past = make_event(session, sheet_row=9, title="Old GBM", start_time=PAST)

    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=3, title="GBM 1")])
    sync_events(session)

    session.refresh(past)
    assert past.deleted_at is None

def test_a_reused_row_creates_a_new_event_beside_the_frozen_one(session, monkeypatch):
    # Next semester's tracker reuses row 40 for a different date. Pairing the
    # row with its date is what lets the new event be created at all -- keyed
    # on the row alone, the frozen fall event would block it forever.
    old = make_event(session, sheet_row=40, title="Fall Social", start_time=PAST)

    _stub_fetch(monkeypatch, [fake_sheet_event(sheet_row=40, title="Spring Social",
                                               start_time=FUTURE)])
    created, updated = sync_events(session)

    assert (created, updated) == (1, 0)
    session.refresh(old)
    assert old.title == "Fall Social" and old.deleted_at is None
    assert len(session.exec(select(Event).where(Event.sheet_row == 40)).all()) == 2


# --- dev mode ---

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

def test_two_rows_sharing_one_identity_in_one_sync_yield_one_db_row(session, monkeypatch):
    # fetch_sheet_events can't actually produce this (enumerate hands out
    # distinct row numbers), but the reconciliation must still be safe if it
    # ever did: the first row is session.add()-ed and still pending; the
    # second row's lookup SELECT triggers SQLAlchemy's autoflush, which writes
    # the first INSERT before the query runs -- so the second row finds it and
    # updates in place. No IntegrityError, no duplicate.
    _stub_fetch(monkeypatch, [
        fake_sheet_event(description="first"),
        fake_sheet_event(description="second"),
    ])

    created, updated = sync_events(session)

    assert (created, updated) == (1, 1)
    assert only_event(session, sheet_row=3).description == "second"

def test_resyncing_unchanged_sheet_does_not_raise(session, monkeypatch):
    _stub_fetch(monkeypatch, [fake_sheet_event()])
    sync_events(session)

    _stub_fetch(monkeypatch, [fake_sheet_event()])
    created, updated = sync_events(session)

    assert (created, updated) == (0, 1)


# --- EventHost reconciliation ---

def test_sync_creates_one_host_for_owner_only(session, monkeypatch):
    make_committee(session, name="Social", chair_role=Role.social_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])

    sync_events(session)

    event = only_event(session, sheet_row=3)
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 1

def test_sync_creates_two_hosts_for_owner_plus_committee_collab(session, monkeypatch):
    make_committee(session, name="Social", chair_role=Role.social_chair)
    make_committee(session, name="EEC", chair_role=Role.eec_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair, Role.eec_chair])])

    sync_events(session)

    event = only_event(session, sheet_row=3)
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 2

def test_sync_ignores_an_outside_org_collab(session, monkeypatch):
    # An outside-org collab (e.g. "NSBE") never resolves to a Role --
    # resolve_committee already dropped it by the time parse_row built
    # host_roles, so sync_events only ever sees the owner's role here.
    make_committee(session, name="Social", chair_role=Role.social_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])

    sync_events(session)

    event = only_event(session, sheet_row=3)
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 1

def test_resyncing_does_not_duplicate_hosts_or_raise(session, monkeypatch):
    # The landmine this reconciliation exists to defuse: sync_events has no
    # per-row try/except (that isolation lives in fetch_sheet_events), so a
    # blind session.add(EventHost(...)) on the second sync would raise
    # IntegrityError on the composite PK at commit and kill the ENTIRE sync.
    #
    # Re-stub with a FRESH fake_sheet_event() call for the second sync rather
    # than reusing the first list: sync_events pops "host_roles" off the dict
    # it's handed, which mutates that dict in place.
    make_committee(session, name="Social", chair_role=Role.social_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])
    sync_events(session)

    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])
    sync_events(session)   # would raise IntegrityError if hosts were re-added blindly

    event = only_event(session, sheet_row=3)
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 1

def test_sync_removes_a_host_dropped_from_the_sheet(session, monkeypatch):
    # Host reconciliation deletes stale rows -- a deliberate, narrow
    # exception to this file's no-hard-delete rule (EventHost has no
    # dependents). Without this, a collab pulled from the sheet would keep
    # that chair able to see and mint QR codes for an event they no longer run.
    social = make_committee(session, name="Social", chair_role=Role.social_chair)
    make_committee(session, name="EEC", chair_role=Role.eec_chair)
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair, Role.eec_chair])])
    sync_events(session)

    # EEC collab removed from the sheet on the next pull.
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])
    sync_events(session)

    event = only_event(session, sheet_row=3)
    hosts = session.exec(select(EventHost.committee_id).where(EventHost.event_id == event.id)).all()
    assert hosts == [social.id]

def test_sync_creates_host_for_bare_eboard_owner_via_generic_committee(session, monkeypatch):
    # The bare "eboard" sheet value resolves to None (not "no match"), which
    # must reconcile against a Committee row whose chair_role is genuinely
    # None (seed.py's generic "E-Board" committee) rather than being dropped
    # like a real non-match (blank cell, outside-org collab).
    make_committee(session, name="E-Board", chair_role=None)
    _stub_fetch(monkeypatch, [fake_sheet_event(event_type="eboard", host_roles=[None])])

    sync_events(session)

    event = only_event(session, sheet_row=3)
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert len(hosts) == 1

def test_sync_eboard_event_has_no_hosts(session, monkeypatch):
    _stub_fetch(monkeypatch, [fake_sheet_event(event_type="eboard", host_roles=[])])

    sync_events(session)

    event = only_event(session, sheet_row=3)
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
    event = only_event(session, sheet_row=3)
    hosts = session.exec(select(EventHost).where(EventHost.event_id == event.id)).all()
    assert hosts == []
    assert caplog.records


# --- host_roles must never reach the Event model ---

def test_host_roles_never_reaches_the_event_model_on_create(session, monkeypatch):
    # host_roles is a different table (EventHost) -- Event has no such
    # column, so it must be popped off before Event(**data).
    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])

    sync_events(session)   # must not raise

    assert not hasattr(only_event(session, sheet_row=3), "host_roles")

def test_host_roles_never_reaches_the_event_model_on_update(session, monkeypatch):
    # This is the branch that actually proves the pop is load-bearing:
    # setattr(existing, "host_roles", ...) raises ValueError on a SQLModel
    # instance -- unlike the Event(**data) constructor exercised above, which
    # silently drops an unrecognized kwarg.
    synced_event(session)

    _stub_fetch(monkeypatch, [fake_sheet_event(host_roles=[Role.social_chair])])
    sync_events(session)   # must not raise ValueError

    assert not hasattr(only_event(session, sheet_row=3), "host_roles")
