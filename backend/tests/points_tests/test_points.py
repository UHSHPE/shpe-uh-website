# Unit tests for services/points.py -- scoring for the Google Forms import.
# Category comes from the points sheet's Committee + Special Event Type
# columns, never the event title. Pure functions only: no DB, no endpoints.

import pytest

from services.points import POINT_VALUES, event_point_type, sign_in_points


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


# --- regular events (blank special type -> host committee decides) ---

def test_outreach_awards_four():
    assert event_point_type("outreach", None) == "outreach"
    assert sign_in_points("outreach", None) == 4


def test_professional_awards_three():
    assert event_point_type("professional", None) == "professional"
    assert sign_in_points("professional", None) == 3


@pytest.mark.parametrize("slug", ["career_fair", "eec"])
def test_professional_adjacent_committees_are_not_professional(slug):
    """Only the Professional committee scores 3 -- not CFC or EEC."""
    assert event_point_type(slug, None) == "committee_event"
    assert sign_in_points(slug, None) == 2


def test_social_awards_three():
    assert event_point_type("social", None) == "srt_social"
    assert sign_in_points("social", None) == 3


@pytest.mark.parametrize("slug", ["shpetina", "athletic", "shpe_jr", "mentorshpe", "academic", "marketing", "eboard"])
def test_other_committees_award_committee_event_points(slug):
    assert event_point_type(slug, None) == "committee_event"
    assert sign_in_points(slug, None) == 2


@pytest.mark.parametrize("slug", [None, "", "brand_new_thing"])
def test_missing_or_unknown_committee_falls_back_to_committee_event(slug):
    """A new Committee option must score, not raise mid-import."""
    assert event_point_type(slug, None) == "committee_event"
    assert sign_in_points(slug, None) == 2


@pytest.mark.parametrize("special", [None, "", "   "])
def test_blank_special_type_is_a_regular_event(special):
    assert event_point_type("outreach", special) == "outreach"
    assert sign_in_points("outreach", special) == 4


def test_unknown_special_type_is_treated_as_a_regular_event():
    """A dropdown option added later must score, not raise mid-import."""
    assert event_point_type("outreach", "brand new type") == "outreach"
    assert sign_in_points("outreach", "brand new type") == 4


# --- special types ---

@pytest.mark.parametrize("special", ["study red", "Study Red", "STUDY RED", "  study red "])
def test_special_type_matches_ignoring_case_and_spacing(special):
    """Dropdown options are hand-typed; editing their casing must not change the score."""
    assert event_point_type("academic", special) == "srt_social"


@pytest.mark.parametrize(
    ("special", "slug", "point_type"),
    [
        ("Committee Meeting", "outreach", "committee_meeting"),
        ("GM", "eboard", "gm"),
        ("Off-campus ", "outreach", "outreach"),
        ("Off-campus ", "shpetina", "committee_event"),
        ("Study Red", "academic", "srt_social"),
    ],
)
def test_every_points_sheet_dropdown_option_is_recognized(special, slug, point_type):
    """Exact strings from the live dropdown -- hyphen and trailing space included."""
    assert event_point_type(slug, special) == point_type


@pytest.mark.parametrize("slug", ["academic", "mentorshpe", "outreach", None])
def test_study_red_awards_three_regardless_of_host(slug):
    assert event_point_type(slug, "study red") == "srt_social"
    assert sign_in_points(slug, "study red") == 3


@pytest.mark.parametrize("slug", ["eboard", "shpe_jr", "outreach", None])
def test_gm_awards_three_regardless_of_host(slug):
    assert event_point_type(slug, "gm") == "gm"
    assert sign_in_points(slug, "gm") == 3


@pytest.mark.parametrize("slug", ["outreach", "professional", "shpetina", None])
def test_committee_meeting_awards_two_regardless_of_host(slug):
    """A committee meeting is not an event, so host categories don't apply."""
    assert event_point_type(slug, "committee meeting") == "committee_meeting"
    assert sign_in_points(slug, "committee meeting") == 2


@pytest.mark.parametrize(
    ("slug", "point_type", "points"),
    [
        ("outreach", "outreach", 4),
        ("professional", "professional", 3),
        ("social", "srt_social", 3),
        ("shpetina", "committee_event", 2),
        (None, "committee_event", 2),
    ],
)
def test_off_campus_is_two_unless_the_host_is_worth_more(slug, point_type, points):
    assert event_point_type(slug, "off campus") == point_type
    assert sign_in_points(slug, "off campus") == points


# --- bonuses ---

def test_no_bonuses_by_default():
    assert sign_in_points("eboard", "gm") == 3


def test_new_member_bonus_adds_two():
    assert sign_in_points("shpetina", None, brought_new_member=True) == 4


def test_new_member_bonus_applies_on_a_gm_too():
    assert sign_in_points("eboard", "gm", brought_new_member=True) == 5


def test_shirt_bonus_adds_two_on_a_gm():
    assert sign_in_points("eboard", "gm", wore_shirt=True) == 5


def test_both_bonuses_stack_on_a_gm():
    assert sign_in_points("eboard", "gm", brought_new_member=True, wore_shirt=True) == 7


@pytest.mark.parametrize(
    ("slug", "special", "base"),
    [
        ("outreach", None, 4),
        ("professional", None, 3),
        ("social", None, 3),
        ("academic", "study red", 3),
        ("shpetina", None, 2),
        ("outreach", "committee meeting", 2),
        ("outreach", "off campus", 4),
    ],
)
def test_shirt_bonus_is_gm_only(slug, special, base):
    """Ignored, not rejected -- a stray checkbox must not fail the import."""
    assert sign_in_points(slug, special, wore_shirt=True) == base
