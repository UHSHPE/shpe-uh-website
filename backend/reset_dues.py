"""Clear every member's dues flag at the start of a new membership year.

Chapter dues reset every May 30. `has_paid_dues` is a plain boolean with no
record of which year it was earned in, so this script is what retires last
year's payments — run it by cron on May 30. Running it twice is harmless;
running it late leaves members showing as paid until it does run.

Deliberately not guarded by assert_local_database(): unlike seed.py, this is
meant to run against production.

    python reset_dues.py
"""

from sqlmodel import Session, select, update

from database import engine
from models.user.user import User


def reset_dues(session: Session) -> int:
    """Clear the dues flag chapter-wide.

    Args:
        session: Database session; this function owns the commit.
    Returns:
        How many members were still marked paid.
    """
    cleared = len(session.exec(select(User.id).where(User.has_paid_dues == True)).all())  # noqa: E712
    session.execute(update(User).where(User.has_paid_dues == True).values(has_paid_dues=False))  # noqa: E712
    session.commit()
    return cleared


if __name__ == "__main__":
    with Session(engine) as session:
        print(f"Cleared dues for {reset_dues(session)} member(s).")
