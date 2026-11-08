# Unit tests for services/points.py -- the chapter point system, shared by QR
# attendance and the Google Forms import. Pure functions only: no DB, no
# endpoints. QR-specific behaviour lives in event_tests/.

from datetime import datetime

import pytest

from models.event import Event
from services.points import POINT_VALUES, event_point_type, sign_in_points


def event(title="Event", event_type=None):
    return Event(title=title, start_time=datetime(2026, 8, 5), event_type=event_type)


# --- the table ---

def test_point_values_match_the_membershpe_chart():
    """One table feeds both QR and the Forms dropdown, so a drifted number
    would silently award different points depending on how a member checked in."""
    assert POINT_VALUES == {
        "outreach": 4,
        "professional": 3,
        "srt_social": 3,
        "gm": 3,
        "committee_event": 2,
        "committee_meeting": 2,
        "sign_out": 2,
        "new_member": 2,
        "shirt": 2,
    }


# --- committee categories (owner committee = event_type) ---

def test_outreach_awards_four():
    ev = event("Noche de Ciencias", "outreach")
    assert event_point_type(ev) == "outreach"
    assert sign_in_points(ev) == 4


def test_professional_awards_three():
    ev = event("Resume Workshop", "professional")
    assert event_point_type(ev) == "professional"
    assert sign_in_points(ev) == 3


@pytest.mark.parametrize("slug", ["career_fair", "eec"])
def test_professional_adjacent_committees_are_not_professional(slug):
    """Only the Professional committee scores 3 -- not CFC or EEC."""
    ev = event("Industry Night", slug)
    assert event_point_type(ev) == "committee_event"
    assert sign_in_points(ev) == 2


def test_social_awards_three():
    ev = event("Game Night", "social")
    assert event_point_type(ev) == "srt_social"
    assert sign_in_points(ev) == 3


@pytest.mark.parametrize("slug", ["shpetina", "athletic", "shpe_jr", "mentorshpe", "academic", "marketing"])
def test_other_committees_award_committee_event_points(slug):
    ev = event("Committee Event", slug)
    assert event_point_type(ev) == "committee_event"
    assert sign_in_points(ev) == 2


@pytest.mark.parametrize("slug", [None, "", "brand_new_thing"])
def test_missing_or_unknown_type_falls_back_to_committee_event(slug):
    """A new tracker-sheet dropdown option must score, not raise mid-scan."""
    ev = event("Mystery Event", slug)
    assert event_point_type(ev) == "committee_event"
    assert sign_in_points(ev) == 2


# --- Study Red (SRT) ---

@pytest.mark.parametrize("title", ["Study Red Tuesday", "Study Red Monday", "STUDY RED", "study red thursday"])
def test_study_red_titles_score_as_srt_social(title):
    """Matched on 'study red' alone -- it runs on more than one weekday."""
    ev = event(title, "academic")
    assert event_point_type(ev) == "srt_social"
    assert sign_in_points(ev) == 3


def test_study_red_matches_on_title_regardless_of_host():
    ev = event("Study Red Tuesday", "mentorshpe")
    assert sign_in_points(ev) == 3


def test_plain_academic_event_is_not_srt():
    ev = event("Study Night", "academic")
    assert event_point_type(ev) == "committee_event"
    assert sign_in_points(ev) == 2


# --- GBM detection ---

def test_eboard_gm_awards_three():
    ev = event("1ST GM LYB", "eboard")
    assert event_point_type(ev) == "gm"
    assert sign_in_points(ev) == 3


def test_gm_detection_is_case_sensitive():
    """'Segment' contains a lowercase 'gm' -- must NOT score as a GBM."""
    ev = event("Segment Kickoff", "eboard")
    assert event_point_type(ev) == "committee_event"
    assert sign_in_points(ev) == 2


def test_eboard_event_without_gm_is_not_a_gbm():
    ev = event("Cat's Back Day 1", "eboard")
    assert sign_in_points(ev) == 2


def test_gm_title_outside_eboard_is_not_a_gbm():
    """SHPE JR 1ST GM is a real live row: a GM title on a shpe_jr event."""
    ev = event("SHPE JR 1ST GM", "shpe_jr")
    assert event_point_type(ev) == "committee_event"
    assert sign_in_points(ev) == 2


# --- bonuses ---

def test_new_member_bonus_adds_two():
    assert sign_in_points(event("Committee Event", "shpetina"), brought_new_member=True) == 4


def test_new_member_bonus_applies_on_a_gm_too():
    assert sign_in_points(event("1ST GM LYB", "eboard"), brought_new_member=True) == 5


def test_shirt_bonus_adds_two_on_a_gm():
    assert sign_in_points(event("1ST GM LYB", "eboard"), wore_shirt=True) == 5


def test_both_bonuses_stack_on_a_gm():
    ev = event("1ST GM LYB", "eboard")
    assert sign_in_points(ev, brought_new_member=True, wore_shirt=True) == 7


@pytest.mark.parametrize(
    ("title", "slug", "base"),
    [
        ("Noche de Ciencias", "outreach", 4),
        ("Resume Workshop", "professional", 3),
        ("Game Night", "social", 3),
        ("Study Red Tuesday", "academic", 3),
        ("Committee Event", "shpetina", 2),
        ("Cat's Back Day 1", "eboard", 2),
    ],
)
def test_shirt_bonus_is_gm_only(title, slug, base):
    """Ignored, not rejected -- a stray checkbox must not fail the sign-in."""
    assert sign_in_points(event(title, slug), wore_shirt=True) == base


def test_no_bonuses_by_default():
    assert sign_in_points(event("1ST GM LYB", "eboard")) == 3
