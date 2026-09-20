"""The f7a2d5c8b613 backfill, which seeds has_paid_dues from the old sources.

The suite builds its schema with SQLModel.metadata rather than Alembic, so
these exercise the migration's UPDATE against a live database directly. That
statement is the only thing carrying existing members across the cutover — get
it wrong and the whole chapter reads as unpaid the morning after deploy.
"""

import importlib.util
from datetime import timedelta
from pathlib import Path

from sqlmodel import select

from models.dues_import import ImportedDues
from models.shop.order import Order, OrderItem, OrderStatus
from models.shop.product import Product, ProductType
from models.user.user import User
from services.shop_services import DUES_PRODUCT_NAME, current_dues_period_start
from tests.conftest import make_user

# Loaded by path: "alembic" on sys.path is the installed package, not this
# project's migrations directory.
_spec = importlib.util.spec_from_file_location(
    "dues_backfill_migration",
    Path(__file__).resolve().parents[2] / "alembic/versions/f7a2d5c8b613_stored_dues_flag.py",
)
migration = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migration)
PERIOD = current_dues_period_start()


def member(session, n, **overrides):
    return make_user(
        session,
        cougarnet_email=f"m{n}@cougarnet.uh.edu",
        personal_email=f"m{n}@gmail.com",
        psid=f"900000{n}",
        has_paid_dues=False,
        **overrides,
    )


def dues_product(session):
    product = Product(
        name=DUES_PRODUCT_NAME,
        description="Chapter dues",
        price_cents=2000,
        product_type=ProductType.apparel,
        sizes=["S", "M", "L"],
    )
    session.add(product)
    session.commit()
    session.refresh(product)
    return product


def dues_order(session, user, created_at, status=OrderStatus.paid):
    product = dues_product(session)
    order = Order(
        order_code=f"BF-{user.id}",
        buyer_name="Test User",
        buyer_email=user.personal_email,
        user_id=user.id,
        total_cents=2000,
        created_at=created_at,
        status=status,
    )
    session.add(order)
    session.commit()
    session.refresh(order)
    session.add(OrderItem(
        order_id=order.id, product_id=product.id, product_name=DUES_PRODUCT_NAME,
        quantity=1, unit_price_cents=2000, size="M",
    ))
    session.commit()


def claim(session, psid, period_start, verified=True):
    session.add(ImportedDues(
        psid=psid, period_start=period_start, verified=verified,
        source_title="2026-2027 SHPE UH Membership",
    ))
    session.commit()


def run_backfill(session):
    session.execute(
        migration.BACKFILL,
        {"dues_product": DUES_PRODUCT_NAME, "period": PERIOD},
    )
    session.commit()


def test_backfill_reproduces_what_the_old_derivation_answered(session):
    by_order = member(session, 1)
    by_claim = member(session, 2)
    cancelled = member(session, 3)
    stale_order = member(session, 4)
    stale_claim = member(session, 5)
    unverified = member(session, 6)
    nobody = member(session, 7)

    dues_order(session, by_order, PERIOD + timedelta(days=1))
    claim(session, by_claim.psid, PERIOD)
    dues_order(session, cancelled, PERIOD + timedelta(days=1), status=OrderStatus.cancelled)
    dues_order(session, stale_order, PERIOD - timedelta(days=1))
    claim(session, stale_claim.psid, PERIOD.replace(year=PERIOD.year - 1))
    claim(session, unverified.psid, PERIOD, verified=False)

    run_backfill(session)

    paid = {u.id for u in session.exec(select(User).where(User.has_paid_dues == True)).all()}  # noqa: E712
    assert paid == {by_order.id, by_claim.id}
    for stays_unpaid in (cancelled, stale_order, stale_claim, unverified, nobody):
        assert stays_unpaid.id not in paid


def test_backfill_is_safe_to_rerun(session):
    paid_member = member(session, 1)
    dues_order(session, paid_member, PERIOD + timedelta(days=1))

    run_backfill(session)
    run_backfill(session)

    session.refresh(paid_member)
    assert paid_member.has_paid_dues is True


def test_period_helper_matches_the_service(session, monkeypatch):
    # The migration reimplements the May 30 floor because it must not import
    # services — the two have to agree or the backfill picks the wrong year.
    assert migration.current_period_start() == current_dues_period_start()
