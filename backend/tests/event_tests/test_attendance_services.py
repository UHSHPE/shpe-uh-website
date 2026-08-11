# Unit tests for services/attendance_services.py -- points rule, code
# minting/resolution, expiry, sign-in/out idempotency, and chair scoping.
# API-level behavior (status codes, response shapes) lives in
# test_attend_endpoint.py and test_chair_events_endpoints.py.

from datetime import datetime

from models.event import Event
from models.user.user_enums import Role
from services import attendance_services
from services.attendance_services import (
    default_points,
    ensure_event_codes,
    host_scoped_events,
    is_expired,
    record_sign_in,
    record_sign_out,
    resolve_code,
)
from services.time_services import utcnow
from tests.conftest import make_event, make_user
from tests.event_tests.conftest import link_host, make_chair, make_committee


# --- default_points / GBM detection ---

def test_default_points_regular_event():
    event = Event(title="Resume Workshop", start_time=datetime(2026, 8, 5), event_type="professional")
    assert default_points(event) == (2, 2)


def test_default_points_gbm_scores_3_2():
    event = Event(title="1ST GM LYB", start_time=datetime(2026, 8, 5), event_type="eboard")
    assert default_points(event) == (3, 2)


def test_default_points_is_case_sensitive():
    # "Segment" contains a lowercase "gm" -- must NOT trigger GBM scoring.
    event = Event(title="Segment Kickoff", start_time=datetime(2026, 8, 5), event_type="eboard")
    assert default_points(event) == (2, 2)


def test_default_points_cats_back_is_eboard_but_not_a_gm():
    event = Event(title="Cat's Back Day 1", start_time=datetime(2026, 8, 5), event_type="eboard")
    assert default_points(event) == (2, 2)


def test_default_points_shpe_jr_gm_is_not_eboard():
    # Title contains "GM" but event_type is shpe_jr, not eboard -- both
    # conditions are required.
    event = Event(title="SHPE JR 1ST GM", start_time=datetime(2026, 8, 5), event_type="shpe_jr")
    assert default_points(event) == (2, 2)


# --- ensure_event_codes ---

def test_ensure_event_codes_mints_both_columns(session):
    event = make_event(session, sign_in_code=None, sign_out_code=None)
    ensure_event_codes(session, event)
    session.refresh(event)
    assert event.sign_in_code
    assert event.sign_out_code
    assert event.sign_in_code != event.sign_out_code


def test_ensure_event_codes_is_idempotent(session):
    event = make_event(session, sign_in_code=None, sign_out_code=None)
    ensure_event_codes(session, event)
    first_in, first_out = event.sign_in_code, event.sign_out_code

    ensure_event_codes(session, event)
    session.refresh(event)
    assert (event.sign_in_code, event.sign_out_code) == (first_in, first_out)


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


def test_is_expired_uses_end_time_when_present():
    event = Event(
        title="GBM 1",
        start_time=datetime(2026, 8, 5, 23, 0),
        end_time=datetime(2026, 8, 6, 0, 0),
    )
    assert is_expired(event, now=datetime(2026, 8, 5, 23, 30)) is False
    assert is_expired(event, now=datetime(2026, 8, 6, 0, 30)) is True


# --- record_sign_in / record_sign_out ---

def test_record_sign_in_creates_row_and_awards_points(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    attendance, points = record_sign_in(session, user, event)

    assert points == 2
    assert attendance.user_id == user.id
    assert attendance.points_awarded == 2
    session.refresh(user)
    assert user.points == 2


def test_double_sign_in_awards_nothing_the_second_time(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    record_sign_in(session, user, event)

    attendance, points = record_sign_in(session, user, event)

    assert points == 0
    session.refresh(user)
    assert user.points == 2   # unchanged by the second call


def test_new_member_bonus_applies_once(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    attendance, points = record_sign_in(
        session, user, event, brought_new_member=True, new_member_name="Jane Doe",
    )

    assert points == 2 + attendance_services.NEW_MEMBER_BONUS
    assert attendance.brought_new_member is True
    assert attendance.new_member_name == "Jane Doe"

    # A second sign-in scan (already signed in) must not re-award the bonus.
    _, points_again = record_sign_in(
        session, user, event, brought_new_member=True, new_member_name="Jane Doe",
    )
    assert points_again == 0
    session.refresh(user)
    assert user.points == 2 + attendance_services.NEW_MEMBER_BONUS


def test_sign_in_gbm_awards_three_points(session, user):
    event = make_event(session, title="1ST GM LYB", event_type="eboard")
    _, points = record_sign_in(session, user, event)
    assert points == 3


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
    assert user.points == 4   # 2 sign-in + 2 sign-out


def test_double_sign_out_awards_nothing_the_second_time(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    record_sign_in(session, user, event)
    record_sign_out(session, user, event)

    attendance, points = record_sign_out(session, user, event)

    assert points == 0
    session.refresh(user)
    assert user.points == 4


def test_sign_out_without_sign_in_returns_none(session, user):
    event = make_event(session, title="Resume Workshop", event_type="professional")
    attendance, points = record_sign_out(session, user, event)
    assert attendance is None
    assert points == 0


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
