"""Chapter point values and how an event's sign-in is scored.

Category comes from the points sheet's Special Event Type when it names one,
else from the host committee's event_type slug. Titles are never consulted.
"""

POINT_VALUES: dict[str, int] = {
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

# Only these hosts score above the committee_event floor. Professional means the
# Professional committee alone -- CFC and EEC are committee_event.
_HOST_POINT_TYPES = {
    "outreach": "outreach",
    "professional": "professional",
    "social": "srt_social",
}

# Special types that replace the host's category outright. "off campus" is
# deliberately absent: it is worth 2, the committee_event floor, so the host's
# own category is already the higher of the two.
_SPECIAL_POINT_TYPES = {
    "committee meeting": "committee_meeting",
    "gm": "gm",
    "study red": "srt_social",
}


def _normalize_special(raw: str | None) -> str:
    # Live dropdown has "Off-campus " -- hyphen and trailing space.
    return " ".join((raw or "").replace("-", " ").split()).lower()


def event_point_type(committee: str | None, special_type: str | None) -> str:
    """POINT_VALUES key for a sign-in; blank or unknown inputs fall back, never raise."""
    special = _SPECIAL_POINT_TYPES.get(_normalize_special(special_type))
    if special:
        return special
    return _HOST_POINT_TYPES.get(committee or "", "committee_event")


def sign_in_points(
    committee: str | None,
    special_type: str | None,
    *,
    brought_new_member: bool = False,
    wore_shirt: bool = False,
) -> int:
    point_type = event_point_type(committee, special_type)
    points = POINT_VALUES[point_type]
    if brought_new_member:
        points += POINT_VALUES["new_member"]
    if wore_shirt and point_type == "gm":  # a stray shirt answer elsewhere is ignored, not rejected
        points += POINT_VALUES["shirt"]
    return points
