from sqlmodel import Field, SQLModel

from models.user.user_enums import Role


class RoleReport(SQLModel, table=True):
    """Which role each role reports to — one row per managed role.

    Keyed by role, so "one supervisor per role" holds by construction and a
    re-parent is an upsert rather than an insert. This is the chapter's org
    chart and nothing more: it grants no permissions anywhere (see
    services/structure_services.py).

    Deliberately role-to-role, not person-to-person, so the tree survives
    elections and chair handovers untouched — the same reason
    Committee.chair_role maps a role onto a committee instead of a user.
    """

    role: Role = Field(primary_key=True)
    supervisor_role: Role


class RoleReportUpdate(SQLModel):
    supervisor_role: Role


class RoleHolderOut(SQLModel):
    """Whoever currently holds a role — usually one person, two for co-chairs,
    none when the seat is vacant."""

    id: int
    first_name: str
    last_name: str


class RoleNodeOut(SQLModel):
    role: Role
    tier: str                     # "president" | "vp" | "officer" | "chair"
    supervisor_role: Role | None  # null = not yet assigned
    holders: list[RoleHolderOut] = []
