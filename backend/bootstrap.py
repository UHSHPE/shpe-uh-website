"""Populate a PRODUCTION database with chapter structure — and nothing else.

seed.py refuses to run under ENVIRONMENT=production, and correctly so: it
creates ~30 accounts all sharing password123. But it is also the only thing
that creates committees, so without this script a production deploy comes up
with empty tables and is unusable:

  * no president  -> nobody can reach /admin/* -> no role can ever be assigned
  * no committees -> sync_events can't resolve Role -> Committee.id, so no
                     EventHost rows are written and QR check-in silently does
                     nothing for everyone
  * no dues product -> verify-email's dues redirect finds nothing by name and
                     drops the new member on the home page

SAFETY PROPERTY, and the reason this file has no ENVIRONMENT guard: it never
imports create_user and contains no password string. It cannot create an
account, however it is run. Keep it that way — if you ever need it to make a
user, you want a different script with a different set of guarantees.

Usage
-----
    python bootstrap.py
    python bootstrap.py --president first.last@cougarnet.uh.edu
    python bootstrap.py --president <email> --vpe <email> --vpi <email>

Structure creation always runs (it's idempotent); promotions are opt-in.
On Railway prefer `railway ssh` over `railway run`, so this executes inside the
container where /data exists and the environment matches the app exactly.
"""
from __future__ import annotations

import argparse
import sys

from fastapi import HTTPException
from sqlalchemy.exc import ProgrammingError
from sqlmodel import Session, select

from chapter_data import (
    COMMITTEE_ROSTER,
    DEFAULT_REPORTS,
    DUES_PRODUCT,
    EBOARD_COMMITTEES,
)
from database import engine
from models.committee import Committee
from models.role_report import RoleReport
from models.shop.product import Product
from models.user.user import User
from models.user.user_enums import Role
from services import shop_services, user_services
from validators.email import normalize_email

# The three seats this script may fill, and only these. Everything below the
# top tier is assigned by the president through /members.
SEATS: dict[str, tuple[Role, str]] = {
    "president": (Role.president, "President"),
    "vpe": (Role.vpe, "VP External"),
    "vpi": (Role.vpi, "VP Internal"),
}


# --- structure ---------------------------------------------------------

def ensure_committees(session: Session) -> None:
    """The 14 real committees. Chair NAMES in the roster are dev-seed data and
    are ignored here — production chairs sign up and are promoted via /members."""
    for name, description, chair_role, _chair_names in COMMITTEE_ROSTER:
        if session.exec(select(Committee).where(Committee.name == name)).first():
            print(f"  skipped committee — {name} already exists.")
            continue
        session.add(Committee(name=name, description=description, chair_role=chair_role))
        print(f"  created committee: {name}")
    session.commit()


def ensure_eboard_committees(session: Session) -> None:
    """Not joinable and not real committees — they exist so EventHost has an
    officer position (or the sheet's bare "eboard" value) to point at."""
    for name, chair_role in EBOARD_COMMITTEES:
        if session.exec(select(Committee).where(Committee.name == name)).first():
            print(f"  skipped E-Board committee — {name} already exists.")
            continue
        session.add(Committee(
            name=name,
            description=f"E-Board — {name}. Not a real committee; exists so events can be linked to it.",
            chair_role=chair_role,
            joinable=False,
        ))
        print(f"  created E-Board committee: {name}")
    session.commit()


def ensure_structure(session: Session) -> None:
    """The org chart. Purely organizational — grants no permissions anywhere.

    Skips wholesale once any link exists (same rule as seed_structure), so
    re-running this never stomps edits made on the Members > Structure tab.
    """
    if session.exec(select(RoleReport)).first():
        print("  skipped reporting structure — already populated.")
        return
    for role, supervisor_role in DEFAULT_REPORTS.items():
        session.add(RoleReport(role=role, supervisor_role=supervisor_role))
    session.commit()
    print(f"  created reporting structure ({len(DEFAULT_REPORTS)} links).")


def ensure_shop_settings(session: Session) -> None:
    shop_services.get_shop_settings(session)   # creates the singleton on first access
    print("  ensured shop settings row.")


def ensure_dues_product(session: Session) -> None:
    """Only the dues product. Real merch is added through Shop Manager — this
    script deliberately does not seed the demo catalogue."""
    name = DUES_PRODUCT["name"]
    if session.exec(select(Product).where(Product.name == name)).first():
        print(f"  skipped product — {name} already exists.")
        return
    session.add(Product(**DUES_PRODUCT))
    session.commit()
    print(f"  created product: {name}")


def bootstrap_structure(session: Session) -> None:
    print("Chapter structure:")
    ensure_committees(session)
    ensure_eboard_committees(session)
    ensure_structure(session)
    ensure_shop_settings(session)
    ensure_dues_product(session)


# --- officer seats -----------------------------------------------------

def promote(session: Session, raw_email: str, role: Role, label: str, assume_yes: bool = False) -> bool:
    """Install one existing, verified account into one top-tier seat.

    Returns True on success (including the already-holds no-op), False on any
    refusal. Refusals print and never raise, so one bad flag doesn't abort the
    other seats.

    The seat is ONE-SHOT: if anyone already holds it, this refuses with no
    override. That is the whole safety model of this command. It is not
    protection against someone with server access — they already have
    DATABASE_URL and SECRET_KEY, and a forged token beats this script while
    leaving no database trace at all. What it buys is that once a seat is
    filled, every later change has to go through /members, where
    _assert_may_assign stops even a VP from moving a top-tier seat. Break-glass
    recovery is deliberate raw SQL: impossible to mistake for routine.
    """
    try:
        email = normalize_email(raw_email)
    except HTTPException:
        print(f"  [{label}] refused: {raw_email!r} is not a valid email address.")
        return False

    user = user_services.get_user_by_email(session, email)
    if user is None:
        print(f"  [{label}] refused: no account with cougarnet email {email}.")
        print("             They need to sign up on the site first.")
        return False

    if not user.email_verified:
        print(f"  [{label}] refused: {email} has not verified their email yet.")
        print("             They need to click the link in their verification email first.")
        return False

    holder = session.exec(select(User).where(User.role == role)).first()
    if holder is not None:
        if holder.id == user.id:
            print(f"  [{label}] {user.first_name} {user.last_name} already holds this seat — nothing to do.")
            return True
        print(f"  [{label}] refused: already held by {holder.first_name} {holder.last_name} ({holder.cougarnet_email}).")
        print("             This seat is one-shot. Change it from /members instead.")
        return False

    print(f"  [{label}] {user.first_name} {user.last_name} <{email}>, currently {user.role.value}")
    if not assume_yes:
        answer = input(f"          Make them {label}? [y/N] ").strip().lower()
        if answer != "y":
            print(f"  [{label}] cancelled.")
            return False

    # Imported here rather than at module scope: it pulls the whole route
    # module (and FastAPI) in, which the structure-only path has no use for.
    from routes.admin_routes import _sync_chair_memberships

    old_role = user.role
    user.role = role
    session.add(user)
    # Chair permissions need BOTH the role and an is_chair row. Redundant for
    # the president (who bypasses every chair check) but it leaves the database
    # in exactly the state /members would have produced, rather than a variant
    # only this script can create.
    _sync_chair_memberships(session, user, old_role, role)
    session.commit()
    session.refresh(user)

    user_services.notify_role_change(session, user, old_role, role, "bootstrap.py")
    print(f"  [{label}] done — {user.first_name} {user.last_name} is now {role.value}.")
    return True


# --- cli ---------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Populate a production database with chapter structure, and optionally fill the three top-tier seats.",
        epilog="Structure creation always runs and is idempotent. Each seat can only be filled once.",
    )
    parser.add_argument("--president", metavar="EMAIL", help="cougarnet email to install as President")
    parser.add_argument("--vpe", metavar="EMAIL", help="cougarnet email to install as VP External")
    parser.add_argument("--vpi", metavar="EMAIL", help="cougarnet email to install as VP Internal")
    parser.add_argument("--yes", action="store_true", help="skip the confirmation prompt (non-interactive runs)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    failures = 0
    with Session(engine) as session:
        try:
            bootstrap_structure(session)

            requested = [(flag, getattr(args, flag)) for flag in SEATS if getattr(args, flag)]
            if requested:
                print("\nOfficer seats:")
                for flag, email in requested:
                    role, label = SEATS[flag]
                    if not promote(session, email, role, label, assume_yes=args.yes):
                        failures += 1
        except ProgrammingError:
            session.rollback()
            # stderr is unbuffered and stdout isn't, so without this flush the
            # error prints above the progress lines it's supposed to follow.
            sys.stdout.flush()
            print(
                "\nERROR: the database tables don't exist yet.\n"
                "Deploy and start the backend once — it creates them on boot — then re-run this.",
                file=sys.stderr,
            )
            return 1

    if failures:
        print(f"\nDone, with {failures} seat(s) not filled. Fix the cause above and re-run just those flags.")
        return 1

    print("\nDone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
