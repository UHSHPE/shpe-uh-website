"""The chapter's 5 Core Pillars: canonical keys, sheet parsing, and the
points each pillar awards on a QR scan.

Single source of truth, imported by three places that would otherwise each
grow their own copy: event_tracker_services (parses the sheet's PILLAR(S)
column), attendance_services (turns pillars into points), and
leaderboard_services (labels the breakdown columns).
"""

# Canonical keys, in the order the About page presents the pillars.
# `label` is member-facing and matches About; `short` is for table headers.
PILLARS = [
    {"key": "chapter", "label": "Chapter Development", "short": "Chapter"},
    {"key": "academic", "label": "Academic Development", "short": "Academic"},
    {"key": "community", "label": "Community Development", "short": "Community"},
    {"key": "professional", "label": "Professional Development", "short": "Professional"},
    {"key": "leadership", "label": "Leadership Development", "short": "Leadership"},
]

PILLAR_KEYS = [p["key"] for p in PILLARS]

# What the tracker sheet's PILLAR(S) dropdown actually contains, normalized
# (lowercased, whitespace-collapsed) -> canonical key.
#
# Note "community outreach": that is the sheet's wording and the only spelling
# seen in the live data, while the About page brands the same pillar
# "Community Development". Both are accepted so neither side has to change,
# and `label` above stays the About wording because that is what members read.
SHEET_LABEL_TO_KEY = {
    "chapter development": "chapter",
    "academic development": "academic",
    "community outreach": "community",
    "community development": "community",
    "professional development": "professional",
    "leadership development": "leadership",
}

# (sign_in, sign_out) awarded for an event carrying this pillar.
# Sourced from the point-system chart on pages/membershpe.jsx: Outreach is
# the chart's only 4, every other named pillar sits at 3 on sign-in.
PILLAR_POINTS = {
    "chapter": (3, 2),
    "academic": (3, 2),
    "community": (4, 2),
    "professional": (3, 2),
    "leadership": (3, 2),
}

# Events whose PILLAR(S) cell is blank or unrecognized -- 40 of 108 named rows
# in the live sheet, so this is the COMMON case, not an edge case. The least
# an event can award, per the chapter's instruction.
NO_PILLAR_POINTS = (2, 2)

# A general meeting awards this regardless of its pillar cell. Kept as a
# floor rather than an override so it composes with the highest-wins rule
# below: a GBM with a blank pillar still gets 3 instead of falling to 2, and
# a GBM also tagged Community Outreach still gets that pillar's 4.
GBM_POINTS = (3, 2)


def parse_pillars(cell: str | None) -> list[str]:
    """Canonical pillar keys from one PILLAR(S) cell.

    The column is genuinely multi-value -- comma-separated, and one live row
    lists all five. Unrecognized entries are dropped rather than guessed at;
    an event left with no recognized pillar simply scores NO_PILLAR_POINTS,
    which is the same outcome as a blank cell and needs no special case.

    Order is not preserved as meaningful (nobody chose it), but duplicates are
    collapsed so a cell listing a pillar twice can't affect anything.
    """
    if not cell:
        return []
    out: list[str] = []
    for part in str(cell).split(","):
        key = SHEET_LABEL_TO_KEY.get(" ".join(part.split()).lower())
        if key and key not in out:
            out.append(key)
    return out


def serialize_pillars(keys: list[str]) -> str | None:
    """Storage form for Event.pillars: comma-joined canonical keys, or NULL.

    A plain string rather than a JSON column because the values are a short,
    fixed vocabulary and nothing queries inside it -- the points rule and the
    leaderboard both just read the whole list back.
    """
    return ",".join(keys) if keys else None


def deserialize_pillars(stored: str | None) -> list[str]:
    """Read Event.pillars back. Tolerates unknown keys left by an older row
    or a hand-edited value by dropping them, so a bad value degrades to
    'no pillar' instead of raising inside a points calculation."""
    if not stored:
        return []
    return [k for k in (p.strip() for p in stored.split(",")) if k in PILLAR_POINTS]
