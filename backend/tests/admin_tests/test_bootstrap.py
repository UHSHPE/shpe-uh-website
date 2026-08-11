"""Tests for bootstrap.py — the production structure/seat installer.

bootstrap.py is the one script that runs against the live database, so the
behaviour pinned here is mostly about what it REFUSES to do.
"""
import itertools

import pytest
from sqlmodel import select

import bootstrap
from chapter_data import COMMITTEE_ROSTER, DEFAULT_REPORTS, DUES_PRODUCT, EBOARD_COMMITTEES
from models.committee import Committee, CommitteeMembership
from models.role_report import RoleReport
from models.shop.product import Product
from models.shop.shop_settings import ShopSettings
from models.user.user import User
from models.user.user_enums import Role
from tests.admin_tests.conftest import make_president
from tests.conftest import make_user


@pytest.fixture
def sent_emails(monkeypatch):
    """Capture role-change notices. user_services imports send_email by name,
    so patch it there rather than on email_services."""
    sent = []

    def fake_send(to, subject, body):
        sent.append({"to": to, "subject": subject, "body": body})
        return True

    monkeypatch.setattr("services.user_services.send_email", fake_send)
    return sent


_psids = itertools.count(5550001)


def member(session, local_part, **overrides):
    """A verified member with a unique cougarnet email, personal email, and
    PSID. make_user's defaults collide on all three, and any test here that
    creates two people trips the personal_email unique index otherwise."""
    fields = dict(
        cougarnet_email=f"{local_part}@cougarnet.uh.edu",
        personal_email=f"{local_part}@gmail.com",
        psid=str(next(_psids)),
    )
    fields.update(overrides)
    return make_user(session, **fields)


def counts(session):
    return {
        "committees": len(session.exec(select(Committee)).all()),
        "reports": len(session.exec(select(RoleReport)).all()),
        "products": len(session.exec(select(Product)).all()),
        "settings": len(session.exec(select(ShopSettings)).all()),
    }


# --- structure ---------------------------------------------------------

def test_bootstrap_creates_full_structure(session):
    bootstrap.bootstrap_structure(session)

    got = counts(session)
    assert got["committees"] == len(COMMITTEE_ROSTER) + len(EBOARD_COMMITTEES)
    assert got["reports"] == len(DEFAULT_REPORTS)
    assert got["products"] == 1
    assert got["settings"] == 1

    # The E-Board rows must not be joinable, or they'd show up on /committees.
    eboard_names = {name for name, _role in EBOARD_COMMITTEES}
    for committee in session.exec(select(Committee)).all():
        assert committee.joinable is (committee.name not in eboard_names)


def test_bootstrap_creates_only_the_dues_product(session):
    """Real merch is added through Shop Manager — the demo catalogue in seed.py
    must not reach production."""
    bootstrap.bootstrap_structure(session)

    products = session.exec(select(Product)).all()
    assert [p.name for p in products] == [DUES_PRODUCT["name"]]
    assert products[0].price_cents == DUES_PRODUCT["price_cents"]


def test_bootstrap_is_idempotent(session):
    bootstrap.bootstrap_structure(session)
    first = counts(session)

    bootstrap.bootstrap_structure(session)

    assert counts(session) == first


def test_bootstrap_creates_no_users(session):
    """The safety property: this script cannot mint an account."""
    bootstrap.bootstrap_structure(session)

    assert session.exec(select(User)).all() == []


def test_bootstrap_does_not_stomp_structure_edits(session):
    """seed_structure's rule: once any link exists, leave the tree alone, so a
    re-run never undoes an edit made on the Members > Structure tab."""
    bootstrap.bootstrap_structure(session)

    edited = session.get(RoleReport, Role.academic_chair)
    edited.supervisor_role = Role.vpe
    session.add(edited)
    session.commit()

    bootstrap.bootstrap_structure(session)

    assert session.get(RoleReport, Role.academic_chair).supervisor_role == Role.vpe


# --- promotion refusals ------------------------------------------------

def test_promote_rejects_unknown_email(session):
    bootstrap.bootstrap_structure(session)

    ok = bootstrap.promote(session, "nobody@cougarnet.uh.edu", Role.president, "President", assume_yes=True)

    assert ok is False
    assert session.exec(select(User).where(User.role == Role.president)).first() is None


def test_promote_rejects_malformed_email(session):
    ok = bootstrap.promote(session, "not-an-email", Role.president, "President", assume_yes=True)

    assert ok is False


def test_promote_rejects_unverified_account(session):
    """An unverified account may not be the person you think it is — signup
    reclaims unverified rows, so the email isn't proven yet."""
    bootstrap.bootstrap_structure(session)
    member(session, "pending", email_verified=False)

    ok = bootstrap.promote(session, "pending@cougarnet.uh.edu", Role.president, "President", assume_yes=True)

    assert ok is False
    assert session.exec(select(User).where(User.role == Role.president)).first() is None


@pytest.mark.parametrize("role,label", [
    (Role.president, "President"),
    (Role.vpe, "VP External"),
    (Role.vpi, "VP Internal"),
])
def test_promote_refuses_when_seat_is_taken(session, role, label):
    """Each seat is one-shot with no override — this is the whole safety model."""
    bootstrap.bootstrap_structure(session)
    member(session, "sitting", role=role)
    challenger = member(session, "challenger")

    ok = bootstrap.promote(session, "challenger@cougarnet.uh.edu", role, label, assume_yes=True)

    assert ok is False
    session.refresh(challenger)
    assert challenger.role == Role.member


def test_promote_is_a_noop_when_target_already_holds_the_seat(session):
    """Re-running the same command must not read as a failure."""
    bootstrap.bootstrap_structure(session)
    member(session, "daniel", role=Role.president)

    ok = bootstrap.promote(session, "daniel@cougarnet.uh.edu", Role.president, "President", assume_yes=True)

    assert ok is True


def test_filling_one_seat_does_not_block_another(session):
    """Refusal is per-seat: installing a VP must not lock out the presidency."""
    bootstrap.bootstrap_structure(session)
    member(session, "carlos")
    member(session, "daniel")

    assert bootstrap.promote(session, "carlos@cougarnet.uh.edu", Role.vpe, "VP External", assume_yes=True)
    assert bootstrap.promote(session, "daniel@cougarnet.uh.edu", Role.president, "President", assume_yes=True)

    assert session.exec(select(User).where(User.role == Role.vpe)).first().cougarnet_email == "carlos@cougarnet.uh.edu"
    assert session.exec(select(User).where(User.role == Role.president)).first().cougarnet_email == "daniel@cougarnet.uh.edu"


# --- promotion side effects -------------------------------------------

def test_promote_syncs_chair_membership(session):
    """Chair permissions need BOTH the role and an is_chair row — leave the DB
    in the same state /members would have produced."""
    bootstrap.bootstrap_structure(session)
    user = member(session, "daniel")

    bootstrap.promote(session, "daniel@cougarnet.uh.edu", Role.president, "President", assume_yes=True)

    committee = session.exec(select(Committee).where(Committee.chair_role == Role.president)).first()
    membership = session.get(CommitteeMembership, (user.id, committee.id))
    assert membership is not None
    assert membership.is_chair is True


def test_promote_notifies_sitting_top_tier(session, sent_emails):
    bootstrap.bootstrap_structure(session)
    president = make_president(session)
    member(session, "carlos")

    bootstrap.promote(session, "carlos@cougarnet.uh.edu", Role.vpe, "VP External", assume_yes=True)

    assert [e["to"] for e in sent_emails] == [president.personal_email]
    # The notice names the real role, not this script's CLI shorthand.
    assert Role.vpe.value in sent_emails[0]["body"]
    assert "carlos@cougarnet.uh.edu" in sent_emails[0]["body"]


def test_first_promotion_notifies_nobody(session, sent_emails):
    """No top-tier holders exist yet on the very first bootstrap — that's normal
    and must not raise."""
    bootstrap.bootstrap_structure(session)
    member(session, "daniel")

    ok = bootstrap.promote(session, "daniel@cougarnet.uh.edu", Role.president, "President", assume_yes=True)

    assert ok is True
    assert sent_emails == []


def test_notification_failure_does_not_break_promotion(session, monkeypatch):
    """Best-effort: a mail outage must not fail the role change."""
    bootstrap.bootstrap_structure(session)
    make_president(session)
    member(session, "carlos")

    def boom(*args, **kwargs):
        raise OSError("smtp is down")

    monkeypatch.setattr("services.user_services.send_email", boom)

    ok = bootstrap.promote(session, "carlos@cougarnet.uh.edu", Role.vpe, "VP External", assume_yes=True)

    assert ok is True
    assert session.exec(select(User).where(User.role == Role.vpe)).first() is not None


# --- the admin route shares the notifier -------------------------------

def test_assign_role_notifies_top_tier(session, president_client, president, sent_emails):
    """The path that keeps working after bootstrap is retired — every future
    chair and officer appointment goes through here."""
    target = member(session, "newmember")

    res = president_client.patch(
        f"/admin/members/{target.id}/role",
        json={"role": Role.academic_chair.value},
    )

    assert res.status_code == 200
    assert [e["to"] for e in sent_emails] == [president.personal_email]
    assert "Academic Chair" in sent_emails[0]["body"]


def test_assign_role_to_same_role_sends_nothing(session, president_client, sent_emails):
    """A no-op PATCH shouldn't page the whole E-Board."""
    target = member(session, "chair", role=Role.academic_chair)

    res = president_client.patch(
        f"/admin/members/{target.id}/role",
        json={"role": Role.academic_chair.value},
    )

    assert res.status_code == 200
    assert sent_emails == []
