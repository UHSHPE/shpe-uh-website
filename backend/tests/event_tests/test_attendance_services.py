# Unit tests for services/attendance_services.py -- code resolution, expiry,
# sign-in/out idempotency, and chair scoping.
# API-level behavior (status codes, response shapes) lives in
# test_attend_endpoint.py and test_chair_events_endpoints.py.

from datetime import datetime

import pytest

from models.event import Event
from models.user.user_enums import Role
from services import attendance_services
from services.attendance_services import (
    host_scoped_events,
    is_expired,
    record_sign_in,
    record_sign_out,
    resolve_code,
)
from services.time_services import utcnow
from tests.conftest import make_event, make_user
from tests.event_tests.conftest import link_host, make_chair, make_committee


# --- resolve_code ---

def test_resolve_code_sign_in(session):
    event = make_event(session, sign_in_code="in-abc", sign_out_code="out-abc")
    resolved = resolve_code(session, "in-abc")
    assert resolved == (event, "in")


def test_resolve_code_sign_out(session):
    event = make_event(session, sign_in_code="in-abc", sign_out_code="out-abc")
    resolved = resolve_code(session, "out-abc")
    assert resolved == (event, "out")


def test_resolve_code_unknown_returns_none(session):
    make_event(session, sign_in_code="in-abc", sign_out_code="out-abc")
    assert resolve_code(session, "not-a-real-code") is None


# --- is_expired ---
#
# August is Central Daylight Time (UTC-5). start_time = Aug 5 23:00 UTC ==
# 6:00 PM Central Aug 5. With no end_time, the deadline is end of the
# CENTRAL day (Aug 5), which is Aug 6 04:59:59.999999 UTC -- NOT UTC
# midnight (Aug 6 00:00 UTC). The two now= values below straddle exactly
# that boundary, so this test would fail if is_expired ever regressed to
# using UTC midnight instead.

def test_is_expired_no_end_time_valid_until_end_of_central_day():
    event = Event(title="GBM 1", start_time=datetime(2026, 8, 5, 23, 0), end_time=None)
    still_within_central_day = datetime(2026, 8, 6, 4, 0)   # after UTC midnight, before the real deadline
    assert is_expired(event, now=still_within_central_day) is False


def test_is_expired_no_end_time_expires_after_end_of_central_day():
    event = Event(title="GBM 1", start_time=datetime(2026, 8, 5, 23, 0), end_time=None)
    past_central_midnight = datetime(2026, 8, 6, 5, 0)
    assert is_expired(event, now=past_central_midnight) is True


def test_is_expired_stays_open_past_end_time_until_central_midnight():
    # Ends 7:00 PM Central, but codes stay open until midnight Central (05:00 UTC).
    event = Event(
        title="GBM 1",
        start_time=datetime(2026, 8, 5, 23, 0),
        end_time=datetime(2026, 8, 6, 0, 0),
    )
    assert is_expired(event, now=datetime(2026, 8, 6, 0, 30)) is False   # 7:30 PM Central
    assert is_expired(event, now=datetime(2026, 8, 6, 4, 30)) is False   # 11:30 PM Central
    assert is_expired(event, now=datetime(2026, 8, 6, 5, 30)) is True


# --- record_sign_in / record_sign_out ---

def test_record_sign_in_creates_row_and_awards_points(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    attendance, points = record_sign_in(session, user, event)

    assert points == 3
    assert attendance.user_id == user.id
    assert attendance.points_awarded == 3
    session.refresh(user)
    assert user.points == 3


def test_double_sign_in_awards_nothing_the_second_time(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    record_sign_in(session, user, event)

    attendance, points = record_sign_in(session, user, event)

    assert points == 0
    session.refresh(user)
    assert user.points == 3   # unchanged by the second call


def test_new_member_bonus_applies_once(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    attendance, points = record_sign_in(
        session, user, event, brought_new_member=True, new_member_name="Jane Doe",
    )

    assert points == 3 + attendance_services.NEW_MEMBER_BONUS
    assert attendance.brought_new_member is True
    assert attendance.new_member_name == "Jane Doe"

    # A second sign-in scan (already signed in) must not re-award the bonus.
    _, points_again = record_sign_in(
        session, user, event, brought_new_member=True, new_member_name="Jane Doe",
    )
    assert points_again == 0
    session.refresh(user)
    assert user.points == 3 + attendance_services.NEW_MEMBER_BONUS


def test_non_gm_sign_in_ignores_a_new_member_claim(session, user):
    # The new-member question is GM-only; a claim anywhere else is dropped, not stored.
    event = make_event(session, title="Resume Workshop", event_type="professional")
    attendance, points = record_sign_in(
        session, user, event, brought_new_member=True, new_member_name="Jane Doe",
    )

    assert points == 3
    assert attendance.brought_new_member is False
    assert attendance.new_member_name is None


def test_sign_in_gbm_awards_three_points(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    _, points = record_sign_in(session, user, event)
    assert points == 3


def test_gm_sign_in_with_shirt_awards_bonus(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    attendance, points = record_sign_in(session, user, event, wore_shirt=True)

    assert points == 5
    assert attendance.wore_shirt is True
    session.refresh(user)
    assert user.points == 5


def test_gm_sign_in_without_shirt_records_false(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    attendance, points = record_sign_in(session, user, event, wore_shirt=False)

    assert points == 3
    assert attendance.wore_shirt is False


def test_gm_sign_in_awards_new_member_bonus_without_shirt(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    attendance, points = record_sign_in(
        session, user, event, wore_shirt=False, brought_new_member=True, new_member_name="Jane Doe",
    )

    assert points == 5
    assert attendance.wore_shirt is False
    assert attendance.brought_new_member is True


def test_gm_sign_in_awards_both_bonuses(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    attendance, points = record_sign_in(
        session, user, event, wore_shirt=True, brought_new_member=True, new_member_name="Jane Doe",
    )

    assert points == 7
    assert attendance.wore_shirt is True
    assert attendance.points_awarded == 7
    session.refresh(user)
    assert user.points == 7


def test_gm_rescan_with_a_different_shirt_answer_changes_nothing(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    record_sign_in(session, user, event, wore_shirt=False)

    attendance, points = record_sign_in(session, user, event, wore_shirt=True)

    assert points == 0
    assert attendance.wore_shirt is False
    assert attendance.points_awarded == 3
    session.refresh(user)
    assert user.points == 3


def test_non_gm_sign_in_leaves_wore_shirt_null(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    attendance, points = record_sign_in(session, user, event)

    assert points == 3
    assert attendance.wore_shirt is None


def test_gm_sign_out_preserves_shirt_response_and_bonus(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    record_sign_in(session, user, event, wore_shirt=True)

    attendance, points = record_sign_out(session, user, event)

    assert points == 2
    assert attendance.wore_shirt is True
    assert attendance.points_awarded == 7


# --- default_points (QR scoring from services/points.py) ---

@pytest.mark.parametrize("title, event_type, sign_in", [
    ("Park Cleanup", "outreach", 4),
    ("Resume Workshop", "professional", 3),
    ("Bowling Night", "social", 3),
    ("Study Red", "academic", 3),
    ("1ST GM LYB", "eboard", 3),
    ("Cat's Back Day", "eboard", 2),     # E-Board, but not a GM
    ("Segment Review", "eboard", 2),     # lowercase "gm" is not a GM
    ("SHPE JR 1ST GM", "shpe_jr", 2),    # GM title, but not E-Board
    ("Lonestar Practice", "projects", 2),
    ("Hand-added", None, 2),
])
def test_default_points_by_category(title, event_type, sign_in):
    event = Event(title=title, event_type=event_type, start_time=datetime(2026, 8, 5, 23, 0))
    assert attendance_services.default_points(event) == (sign_in, 2)


def test_sign_in_race_falls_back_to_already_signed_in(session, user, monkeypatch):
    # The scenario the plan calls out as "the part that must not be wrong":
    # two simultaneous scans race past the .get() existence check. Simulate
    # the race by pre-inserting the row (as the "winning" request would have)
    # and monkeypatching session.get to miss it once, forcing record_sign_in's
    # own INSERT to collide at commit -- it must catch the IntegrityError,
    # roll back, and report "already signed in" instead of raising or
    # double-awarding points.
    from models.event_attendance import EventAttendance

    event = make_event(session, title="Resume Workshop", event_type="professional")
    session.add(EventAttendance(user_id=user.id, event_id=event.id, signed_in_at=utcnow(), points_awarded=2))
    user.points = 2
    session.add(user)
    session.commit()

    original_get = session.get
    seen = {"n": 0}

    def fake_get(model, pk):
        if model is EventAttendance and seen["n"] == 0:
            seen["n"] += 1
            return None   # the TOCTOU miss
        return original_get(model, pk)

    monkeypatch.setattr(session, "get", fake_get)

    attendance, points = record_sign_in(session, user, event)

    assert points == 0
    assert attendance is not None
    session.refresh(user)
    assert user.points == 2   # not double-awarded


def test_record_sign_out_awards_separately(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    record_sign_in(session, user, event)

    attendance, points = record_sign_out(session, user, event)

    assert points == 2
    assert attendance.signed_out_at is not None
    session.refresh(user)
    assert user.points == 5   # 3 sign-in + 2 sign-out


def test_double_sign_out_awards_nothing_the_second_time(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    record_sign_in(session, user, event)
    record_sign_out(session, user, event)

    attendance, points = record_sign_out(session, user, event)

    assert points == 0
    session.refresh(user)
    assert user.points == 5


def test_sign_out_without_sign_in_awards_sign_out_points(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")

    attendance, points = record_sign_out(session, user, event)

    assert points == 2
    assert attendance.signed_in_at is None
    assert attendance.signed_out_at is not None
    assert attendance.points_awarded == 2
    assert attendance.wore_shirt is None
    session.refresh(user)
    assert user.points == 2


def test_repeat_sign_out_without_sign_in_awards_nothing(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    record_sign_out(session, user, event)

    _, points = record_sign_out(session, user, event)

    assert points == 0
    session.refresh(user)
    assert user.points == 2


def test_late_gm_sign_in_after_sign_out_awards_sign_in_points(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    record_sign_out(session, user, event)

    attendance, points = record_sign_in(session, user, event, wore_shirt=True)

    assert points == 5   # 3 GM sign-in + 2 shirt
    assert attendance.signed_in_at is not None
    assert attendance.signed_out_at is not None
    assert attendance.wore_shirt is True
    assert attendance.points_awarded == 7   # 2 sign-out + 5 sign-in
    session.refresh(user)
    assert user.points == 7

    _, points_again = record_sign_in(session, user, event, wore_shirt=True)
    assert points_again == 0
    session.refresh(user)
    assert user.points == 7


# --- host_scoped_events ---

def test_host_scoped_events_chair_sees_only_their_committees_events(session):
    social = make_committee(session, name="Social", chair_role=Role.social_chair)
    eec = make_committee(session, name="EEC", chair_role=Role.eec_chair)
    social_chair = make_chair(session, social)

    social_event = make_event(session, title="Mixer")
    eec_event = make_event(session, title="Robotics Night")
    link_host(session, social_event, social)
    link_host(session, eec_event, eec)

    events = host_scoped_events(session, social_chair)

    assert [e.id for e in events] == [social_event.id]


def test_host_scoped_events_eboard_role_sees_every_eboard_committee(session):
    # An E-Board member sees every E-Board (joinable=False) committee's
    # events, not just a personally-chaired one -- "officers run GBMs
    # collectively" per the plan.
    eboard_committee = make_committee(session, name="E-Board", chair_role=None, joinable=False)
    vpe_committee = make_committee(session, name="Vice President External", chair_role=Role.vpe, joinable=False)
    regular_committee = make_committee(session, name="Social", chair_role=Role.social_chair, joinable=True)

    gbm = make_event(session, title="1ST GM")
    vpe_event = make_event(session, title="VPE Planning")
    social_event = make_event(session, title="Mixer")
    link_host(session, gbm, eboard_committee)
    link_host(session, vpe_event, vpe_committee)
    link_host(session, social_event, regular_committee)

    vpi_user = make_user(
        session,
        cougarnet_email="vpi@cougarnet.uh.edu",
        personal_email="vpi@gmail.com",
        psid="6666666",
        role=Role.vpi,
    )

    events = host_scoped_events(session, vpi_user)

    # Sees both E-Board committees' events (generic + VPE), even though this
    # user holds VPI, not VPE -- but not the unrelated regular committee.
    assert {e.id for e in events} == {gbm.id, vpe_event.id}


def test_host_scoped_events_president_sees_everything(session):
    social = make_committee(session, name="Social", chair_role=Role.social_chair)
    social_event = make_event(session, title="Mixer")
    unhosted_event = make_event(session, title="No Host Yet")
    link_host(session, social_event, social)

    president = make_user(
        session,
        cougarnet_email="president@cougarnet.uh.edu",
        personal_email="president@gmail.com",
        psid="7777770",
        role=Role.president,
    )

    events = host_scoped_events(session, president)

    assert {e.id for e in events} == {social_event.id, unhosted_event.id}


def test_host_scoped_events_regular_member_sees_nothing(session, user):
    social = make_committee(session, name="Social", chair_role=Role.social_chair)
    event = make_event(session, title="Mixer")
    link_host(session, event, social)

    assert host_scoped_events(session, user) == []


# --- soft-deleted events are invisible everywhere ---

def test_resolve_code_ignores_a_soft_deleted_event(session):
    # An event pulled from the tracker sheet is off the calendar, so its QR
    # must stop awarding points -- otherwise a code already printed on a
    # flyer keeps working for an event that no longer exists.
    event = make_event(session, sign_in_code="in-abc", sign_out_code="out-abc")
    event.deleted_at = utcnow()
    session.add(event)
    session.commit()

    assert attendance_services.resolve_code(session, "in-abc") is None
    assert attendance_services.resolve_code(session, "out-abc") is None

def test_host_scoped_events_hides_a_soft_deleted_event_from_its_chair(session):
    social = make_committee(session, name="Social", chair_role=Role.social_chair)
    social_chair = make_chair(session, social)
    live = make_event(session, title="Mixer")
    hidden = make_event(session, title="Cancelled Mixer", deleted_at=utcnow())
    link_host(session, live, social)
    link_host(session, hidden, social)

    events = host_scoped_events(session, social_chair)

    assert [e.id for e in events] == [live.id]

def test_host_scoped_events_hides_a_soft_deleted_event_from_the_president(session):
    # The president's branch is a separate query (full access, no EventHost
    # join), so it needs the filter of its own.
    president = make_user(session, role=Role.president)
    live = make_event(session, title="Mixer")
    make_event(session, title="Cancelled Mixer", deleted_at=utcnow())

    events = host_scoped_events(session, president)

    assert [e.id for e in events] == [live.id]


# --- committee meetings ---

def test_events_default_to_not_a_committee_meeting(session):
    event = make_event(session)
    session.refresh(event)
    assert event.is_committee_meeting is False


@pytest.mark.parametrize("host", ["outreach", "professional", "social", "academic", "eboard", "projects", None])
def test_committee_meeting_sign_in_is_two_points_for_every_host(session, user, host):
    # The host's category (outreach 4, professional/social 3) must not leak into a meeting.
    meeting = make_event(
        session, title="1ST GM Study Red Meeting", event_type=host,
        sign_out_code=None, is_committee_meeting=True,
    )
    attendance, points = record_sign_in(session, user, meeting)

    assert points == 2
    assert attendance.points_awarded == 2
    session.refresh(user)
    assert user.points == 2


def test_committee_meeting_default_points_has_no_sign_out():
    meeting = Event(
        title="Social Meeting", event_type="social",
        start_time=datetime(2026, 12, 4, 1, 0), is_committee_meeting=True,
    )
    assert attendance_services.default_points(meeting) == (2, 0)


def test_committee_meeting_ignores_gm_only_answers(session, user):
    meeting = make_event(
        session, title="Social Meeting", event_type="social",
        sign_out_code=None, is_committee_meeting=True,
    )
    attendance, points = record_sign_in(
        session, user, meeting,
        brought_new_member=True, new_member_name="Jane Doe", wore_shirt=True,
    )

    assert points == 2
    assert attendance.brought_new_member is False
    assert attendance.new_member_name is None
    assert attendance.wore_shirt is None


def test_committee_meeting_repeat_sign_in_awards_nothing(session, user):
    meeting = make_event(
        session, title="Social Meeting", event_type="social",
        sign_out_code=None, is_committee_meeting=True,
    )
    record_sign_in(session, user, meeting)

    _, points = record_sign_in(session, user, meeting)

    assert points == 0
    session.refresh(user)
    assert user.points == 2


def test_ensure_event_codes_never_mints_a_meeting_sign_out_code(session):
    meeting = make_event(
        session, title="Social Meeting", event_type="social",
        sign_in_code=None, sign_out_code=None, is_committee_meeting=True,
    )

    attendance_services.ensure_event_codes(session, [meeting])

    session.refresh(meeting)
    assert meeting.sign_in_code
    assert meeting.sign_out_code is None


# Chair picks 7:00 PM Central on Dec 3 (CST, UTC-6) -> stored as Dec 4 01:00 UTC.
# No end_time, so the window is 60 min before start until midnight Central.

@pytest.mark.parametrize("now, not_started", [
    (datetime(2026, 12, 4, 0, 30), False),   # 6:30 PM Central, inside the grace window
    (datetime(2026, 12, 3, 23, 30), True),   # 5:30 PM Central, too early
])
def test_committee_meeting_opens_an_hour_before_its_start(now, not_started):
    meeting = Event(title="Social Meeting", start_time=datetime(2026, 12, 4, 1, 0), is_committee_meeting=True)
    assert attendance_services.is_not_started(meeting, now=now) is not_started


@pytest.mark.parametrize("now, expired", [
    (datetime(2026, 12, 4, 5, 30), False),   # 11:30 PM Central Dec 3
    (datetime(2026, 12, 4, 6, 30), True),    # 12:30 AM Central Dec 4
])
def test_committee_meeting_closes_at_central_midnight(now, expired):
    meeting = Event(title="Social Meeting", start_time=datetime(2026, 12, 4, 1, 0), is_committee_meeting=True)
    assert is_expired(meeting, now=now) is expired
