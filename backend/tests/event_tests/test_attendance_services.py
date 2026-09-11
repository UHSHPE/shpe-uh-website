# Unit tests for services/attendance_services.py -- points rule, code
# resolution, expiry, sign-in/out idempotency, and chair scoping.
# API-level behavior (status codes, response shapes) lives in
# test_attend_endpoint.py and test_chair_events_endpoints.py.

from datetime import datetime

import pytest

from models.event import Event
from models.user.user_enums import Role
from services import attendance_services
from services.attendance_services import (
    default_points,
    host_scoped_events,
    is_expired,
    record_sign_in,
    record_sign_out,
    resolve_code,
)
from services.pillars import NO_PILLAR_POINTS, PILLAR_KEYS
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


# --- pillar-driven points (the membershpe chart) ---

class TestPillarPoints:
    """default_points reads Event.pillars, sourced from the tracker sheet's
    PILLAR(S) column. Table lives in services/pillars.py."""

    def test_community_outreach_awards_four_on_sign_in(self):
        """The chart's only 4 ('+4 Assist Outreach events')."""
        ev = Event(title="Noche de Ciencias", event_type="outreach", pillars="community")
        assert default_points(ev) == (4, 2)

    @pytest.mark.parametrize("key", ["chapter", "academic", "professional", "leadership"])
    def test_other_named_pillars_award_three_on_sign_in(self, key):
        assert default_points(Event(title="Event", event_type="social", pillars=key)) == (3, 2)

    def test_no_pillar_falls_to_the_least_points(self):
        """40 of 108 named rows in the live sheet have a blank PILLAR(S)."""
        assert default_points(Event(title="Study Night", event_type="academic", pillars=None)) == (2, 2)

    def test_unrecognized_pillar_falls_to_the_least_points(self):
        """A hand-edited or newly-added value must not raise inside a scan."""
        assert default_points(Event(title="Thing", event_type="social", pillars="bogus")) == (2, 2)

    def test_multi_pillar_takes_the_highest_not_the_sum(self):
        """Summing would make one live row (all five pillars) worth 14 on a
        single sign-in, and would tie points to how thoroughly a chair filled
        in a dropdown."""
        ev = Event(title="Serve Day", event_type="outreach", pillars="community,leadership")
        assert default_points(ev) == (4, 2)

    def test_all_five_pillars_still_only_awards_the_best_one(self):
        ev = Event(
            title="Everything Event",
            event_type="eboard",
            pillars="chapter,academic,community,professional,leadership",
        )
        assert default_points(ev) == (4, 2)

    def test_gbm_is_a_floor_so_a_blank_pillar_still_awards_three(self):
        """Preserves the pre-pillar GBM behaviour instead of dropping GBMs to 2."""
        assert default_points(Event(title="GM #3", event_type="eboard", pillars=None)) == (3, 2)

    def test_gbm_does_not_cap_a_higher_pillar(self):
        """Floor, not override -- a GBM also tagged Community Outreach keeps 4."""
        assert default_points(Event(title="GM #4", event_type="eboard", pillars="community")) == (4, 2)

    def test_gbm_detection_is_still_case_sensitive(self):
        """'GM' not '.lower()' -- a case-insensitive check also matches
        ordinary words containing 'gm', e.g. 'Segment'."""
        assert default_points(Event(title="Segment Workshop", event_type="eboard", pillars=None)) == (2, 2)

    def test_non_eboard_gm_title_is_not_a_gbm(self):
        """SHPE JR 1ST GM is a real live row: a GM title on a shpe_jr event."""
        assert default_points(Event(title="SHPE JR 1ST GM", event_type="shpe_jr", pillars=None)) == (2, 2)

    def test_every_pillar_awards_at_least_the_no_pillar_minimum(self):
        """Tagging a pillar must never make an event worth less than leaving
        the cell blank, or chairs are rewarded for not filling it in."""
        for key in PILLAR_KEYS:
            assert default_points(Event(title="E", event_type="x", pillars=key)) >= NO_PILLAR_POINTS
