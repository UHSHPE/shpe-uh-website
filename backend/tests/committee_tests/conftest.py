import pytest
from sqlmodel import select

from models.notification import Notification

# Reuse rather than redefine -- these already exist and are the established
# cross-directory import (event_tests/conftest.py imports make_president from
# admin_tests/conftest.py the same way).
from tests.event_tests.conftest import make_chair, make_committee  # noqa: F401


@pytest.fixture
def committee(session):
    return make_committee(session)


@pytest.fixture
def co_chairs(session, committee):
    """Two co-chairs on one committee -- the amplification F9 exploits.

    Every unique column varies per chair: cougarnet_email, personal_email and
    psid are all unique, and make_user's defaults are the same literals on
    every call, so overriding only the email dies on ix_user_personal_email
    with an IntegrityError naming a field the test never mentioned.
    """
    return [
        make_chair(
            session,
            committee,
            cougarnet_email=f"chair{n}@cougarnet.uh.edu",
            personal_email=f"chair{n}@gmail.com",
            psid=f"900000{n}",
        )
        for n in (1, 2)
    ]


def notifications_for(session, user_id):
    """Every notification row addressed to one user."""
    return session.exec(
        select(Notification).where(Notification.user_id == user_id)
    ).all()
