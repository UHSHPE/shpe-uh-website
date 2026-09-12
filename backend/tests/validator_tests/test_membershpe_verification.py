"""Membership verification: dues imported from the chapter's Google Sheet.

One test per row of the agreed table — each asserts only the thing its row
names, so a failure points at exactly one rule.

Two columns carry the whole import. PSID says WHO paid; the "Payment Verified?"
checkbox says whether the treasurer has confirmed the money actually arrived.
A row is imported either way — an unchecked box records the claim without
granting anything, so the treasurer can see who is waiting on review — but only
a checked box counts toward has_paid_dues.

Nothing here reaches the network: the autouse disable_dues_import_sync fixture
in tests/conftest.py clears DUES_SHEET_ID, so an unstubbed get_sheet() returns
None on its own.

THE IMPLEMENTATION DOES NOT EXIST YET. This file is the specification for it;
the names below are the contract. See the "Membership-sheet dues import"
section of CLAUDE.md.
"""

from datetime import timedelta

import pytest
from sqlmodel import select

import services.dues_import_services as dues_import_services
import services.shop_services as shop_services
from main import app
from models.dues_import import ImportedDues
from models.shop.order import Order
from services.dependencies import get_optional_user
from services.dues_import_services import sync_dues
from services.shop_services import current_dues_period_start
from tests.admin_tests.conftest import president, president_client  # noqa: F401
from tests.conftest import make_user
from tests.shop_tests.conftest import make_product, order_payload, sent_emails  # noqa: F401

# The sheet has no date column — the academic year lives in the TITLE and
# nowhere else, which is what pins an imported row to a membership period.
PERIOD = current_dues_period_start()
CURRENT_TITLE = f"{PERIOD.year}-{PERIOD.year + 1} SHPE UH Membership"
PRIOR_TITLE = f"{PERIOD.year - 1}-{PERIOD.year} SHPE UH Membership"

# Exact header text of the checkbox column, as spelled in the live sheet.
VERIFIED_HEADER = "Payment Verified?"


# --- helpers ----------------------------------------------------------------

class FakeSheet:
    """A gspread Spreadsheet. PSID sits in column F on the real sheet, so the
    grid pads five columns in front of it — the import finds both columns by
    header text, not by index.

    Each entry in `rows` is either a bare PSID (the box is checked) or a
    (psid, checked) pair. `checked` may be a bool or the raw cell string, so a
    test can feed whatever Sheets actually put in the cell. gspread renders a
    checkbox as the string "TRUE" or "FALSE" through get_all_values().
    """

    def __init__(self, title, rows, header="Student PSID", verified_header=VERIFIED_HEADER):
        self.title = title
        grid = [["Timestamp", "Name", "Email", "Payment", "Amount", header] + [""] * 20 + [verified_header]]
        for row in rows:
            psid, checked = row if isinstance(row, tuple) else (row, True)
            if checked is True:
                cell = "TRUE"
            elif checked is False:
                cell = "FALSE"
            else:
                cell = checked
            grid.append(["", "", "", "", "", psid] + [""] * 20 + [cell])
        self.sheet1 = type(
            "FakeWorksheet", (), {"get_all_values": lambda _self: grid},
        )()


def stub_sheet(monkeypatch, title, rows, header="Student PSID", verified_header=VERIFIED_HEADER):
    monkeypatch.setattr(
        dues_import_services,
        "get_sheet",
        lambda: FakeSheet(title, rows, header, verified_header),
    )


def records(session, psid=None):
    query = select(ImportedDues)
    if psid is not None:
        query = query.where(ImportedDues.psid == psid)
    return session.exec(query).all()


def seed_multi_selects(session, user):
    """UserOut requires >=1 entry per multi-select list and a bare make_user has
    none — the minimum needed for /me to serialize."""
    from models.user.multi_selections.user_country_origin import UserCountryOrigin
    from models.user.multi_selections.user_interested_industries import UserInterestedIndustries
    from models.user.multi_selections.user_prof_dev import UserProfDev
    from models.user.multi_selections.user_race_ethnicity import UserRaceEthnicity
    from models.user.user_enums import Industry, ProfDev, RaceEthnicity

    session.add_all([
        UserRaceEthnicity(user_id=user.id, race_and_ethnicity=RaceEthnicity.hispanic),
        UserInterestedIndustries(user_id=user.id, interested_industry=Industry.electronics),
        UserProfDev(user_id=user.id, prof_dev=ProfDev.internships),
        UserCountryOrigin(user_id=user.id, country_origin="Mexico"),
    ])
    session.commit()


# --- the cases --------------------------------------------------------------

def test_valid_verified_psid_for_the_current_year_marks_the_member_paid(session, monkeypatch, user):
    """Valid PSID, box checked, current academic year — the member is paid."""
    stub_sheet(monkeypatch, CURRENT_TITLE, [user.psid])
    sync_dues(session)

    assert records(session, user.psid)[0].verified is True
    assert shop_services.has_paid_dues(session, user.id) is True


def test_unverified_row_is_recorded_but_grants_no_dues(session, monkeypatch, user):
    """An unchecked box records the claim and grants nothing.

    The row is kept rather than skipped so the treasurer can tell "paid, not yet
    reviewed" from "never appeared in the sheet" — and so checking the box later
    updates a row instead of racing to create one.
    """
    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, False)])
    sync_dues(session)

    record = records(session, user.psid)[0]
    assert record.verified is False
    assert record.period_start == PERIOD          # still pinned to the sheet's year
    assert shop_services.has_paid_dues(session, user.id) is False


def test_checking_the_box_later_upgrades_the_existing_record(session, monkeypatch, user):
    """Verification arriving on a later sync flips the row already there."""
    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, False)])
    sync_dues(session)
    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, True)])
    sync_dues(session)

    assert len(records(session, user.psid)) == 1   # upgraded, not re-inserted
    assert records(session, user.psid)[0].verified is True
    assert shop_services.has_paid_dues(session, user.id) is True


def test_unchecking_the_box_does_not_revoke_dues(session, monkeypatch, user):
    """Verification is a one-way latch, matching the no-sweep rule below.

    A box unchecked by accident must not silently un-pay a member mid-semester;
    a genuine reversal is undone by hand in the database.
    """
    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, True)])
    sync_dues(session)
    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, False)])
    sync_dues(session)

    assert records(session, user.psid)[0].verified is True
    assert shop_services.has_paid_dues(session, user.id) is True


@pytest.mark.parametrize(
    "cell, paid",
    [("TRUE", True), ("true", True), ("FALSE", False), ("", False), ("yes", False)],
    ids=["TRUE", "lowercase-true", "FALSE", "blank", "yes"],
)
def test_only_a_true_checkbox_counts_as_verified(session, monkeypatch, user, cell, paid):
    """Cell parsing fails closed.

    Sheets writes "TRUE"/"FALSE" for a real checkbox, so those two are the only
    values that matter — but a cell converted from free text can hold anything,
    and anything unrecognized must read as unverified rather than as paid.
    """
    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, cell)])
    sync_dues(session)

    assert records(session, user.psid)[0].verified is paid
    assert shop_services.has_paid_dues(session, user.id) is paid


def test_leading_zeros_are_preserved_through_import_and_matching(session, monkeypatch):
    """Leading zeros in PSID are preserved during import and matching.

    This is why the import must read get_all_values() rather than
    get_all_records(), which numericises the cell into the int 123456.
    """
    member = make_user(
        session,
        cougarnet_email="zero@cougarnet.uh.edu",
        personal_email="zero@gmail.com",
        psid="0123456",
    )
    stub_sheet(monkeypatch, CURRENT_TITLE, ["0123456"])
    sync_dues(session)

    assert records(session)[0].psid == "0123456"
    assert shop_services.has_paid_dues(session, member.id) is True


def test_blank_and_malformed_psids_are_skipped_and_reported(session, monkeypatch, caplog):
    """Blank or malformed PSID is skipped and reported, however the box reads.

    "123456" is the real-world case — someone dropped a digit. It is never
    zero-padded, because that would invent a PSID belonging to someone else.
    """
    stub_sheet(monkeypatch, CURRENT_TITLE, ["1234567", "", "123456", "abcdefg"])
    with caplog.at_level("WARNING"):
        sync_dues(session)

    assert [r.psid for r in records(session)] == ["1234567"]
    assert "123456" in caplog.text and "abcdefg" in caplog.text


def test_duplicate_and_reordered_rows_create_no_duplicate_records(session, monkeypatch):
    """Duplicate PSIDs or reordered rows produce no duplicate dues records."""
    stub_sheet(monkeypatch, CURRENT_TITLE, ["1111111", "1111111", "2222222"])
    sync_dues(session)
    stub_sheet(monkeypatch, CURRENT_TITLE, ["2222222", "1111111"])
    sync_dues(session)

    assert len(records(session)) == 2
    assert len(records(session, "1111111")) == 1


def test_duplicate_rows_disagreeing_on_verification_resolve_to_verified(session, monkeypatch, user):
    """One PSID entered twice, checked once — the member is paid.

    A duplicate entry is the same payment typed twice, so the checked row is the
    reviewed one whichever order the pair arrives in. Without this the result
    depends on which row the loop happens to see last.
    """
    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, False), (user.psid, True)])
    sync_dues(session)
    assert records(session, user.psid)[0].verified is True

    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, True), (user.psid, False)])
    sync_dues(session)
    assert len(records(session, user.psid)) == 1
    assert records(session, user.psid)[0].verified is True


def test_repeated_import_keeps_payment_status_consistent(session, monkeypatch, user):
    """The same sheet imported repeatedly leaves payment status unchanged."""
    stub_sheet(monkeypatch, CURRENT_TITLE, [user.psid])
    for _ in range(4):
        sync_dues(session)

    assert len(records(session, user.psid)) == 1
    assert shop_services.has_paid_dues(session, user.id) is True


def test_psid_imported_before_the_account_exists_is_honored_after_signup(session, monkeypatch):
    """A PSID imported before account creation is recognized once the member
    registers and verifies — which is why ImportedDues carries no user id."""
    stub_sheet(monkeypatch, CURRENT_TITLE, ["5550001"])
    sync_dues(session)
    assert shop_services.dues_paid_user_ids(session) == set()

    member = make_user(
        session,
        cougarnet_email="late@cougarnet.uh.edu",
        personal_email="late@gmail.com",
        psid="5550001",
        email_verified=True,
    )

    assert shop_services.has_paid_dues(session, member.id) is True


def test_an_unverified_row_waiting_on_an_account_still_grants_nothing(session, monkeypatch):
    """The two "not paid yet" conditions compose rather than cancelling out.

    An unchecked row for a PSID with no account must not become paid the moment
    the account appears — the box is what clears it, not the signup.
    """
    stub_sheet(monkeypatch, CURRENT_TITLE, [("5550002", False)])
    sync_dues(session)

    member = make_user(
        session,
        cougarnet_email="pending@cougarnet.uh.edu",
        personal_email="pending@gmail.com",
        psid="5550002",
        email_verified=True,
    )

    assert shop_services.has_paid_dues(session, member.id) is False
    assert shop_services.dues_paid_user_ids(session) == set()


def test_previous_academic_years_psid_does_not_grant_current_dues(session, monkeypatch, user):
    """A previous academic year's PSID does not grant current-year dues. The
    record is still created — it just belongs to the period its sheet names."""
    stub_sheet(monkeypatch, PRIOR_TITLE, [user.psid])
    sync_dues(session)

    assert records(session, user.psid)[0].period_start.year == PERIOD.year - 1
    assert shop_services.has_paid_dues(session, user.id) is False


def test_the_same_psid_can_be_verified_in_two_periods_independently(session, monkeypatch, user):
    """Period is part of a record's identity, so last year's checked box neither
    satisfies nor blocks this year's — two rows, verified separately."""
    stub_sheet(monkeypatch, PRIOR_TITLE, [(user.psid, True)])
    sync_dues(session)
    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, False)])
    sync_dues(session)

    assert len(records(session, user.psid)) == 2
    assert shop_services.has_paid_dues(session, user.id) is False

    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, True)])
    sync_dues(session)

    assert len(records(session, user.psid)) == 2
    assert shop_services.has_paid_dues(session, user.id) is True


def test_imported_dues_expire_at_the_may_30_boundary(session, monkeypatch, user):
    """Imported dues expire correctly across the membership-period boundary."""
    stub_sheet(monkeypatch, CURRENT_TITLE, [user.psid])
    sync_dues(session)
    next_reset = PERIOD.replace(year=PERIOD.year + 1)

    monkeypatch.setattr(shop_services, "utcnow", lambda: next_reset - timedelta(days=1))
    assert shop_services.has_paid_dues(session, user.id) is True

    monkeypatch.setattr(shop_services, "utcnow", lambda: next_reset)
    assert shop_services.has_paid_dues(session, user.id) is False


def test_a_failed_import_leaves_existing_records_intact(session, monkeypatch, user):
    """Google unavailable, a missing PSID header, a missing verification header,
    or any failed import leaves existing dues records intact — every abort
    returns before the first write.

    The verification header is the one that must fail CLOSED rather than
    defaulting: treating a renamed column as "everybody is checked" would mark
    the whole sheet paid with no money confirmed.
    """
    stub_sheet(monkeypatch, CURRENT_TITLE, [user.psid])
    sync_dues(session)

    # Missing PSID header.
    stub_sheet(monkeypatch, CURRENT_TITLE, ["7654321"], header="Name")
    sync_dues(session)
    # Missing verification header.
    stub_sheet(monkeypatch, CURRENT_TITLE, ["7654321"], verified_header="Notes")
    sync_dues(session)
    # Google unreachable.
    monkeypatch.setattr(
        dues_import_services, "get_sheet",
        lambda: (_ for _ in ()).throw(ConnectionError("Google is down")),
    )
    with pytest.raises(ConnectionError):
        sync_dues(session)

    assert [r.psid for r in records(session)] == [user.psid]
    assert shop_services.has_paid_dues(session, user.id) is True


def test_a_psid_removed_from_the_sheet_is_not_revoked(session, monkeypatch, user):
    """A sheet entry disappearing revokes nothing — there is no sweep pass."""
    stub_sheet(monkeypatch, CURRENT_TITLE, [user.psid])
    sync_dues(session)

    stub_sheet(monkeypatch, CURRENT_TITLE, [])
    sync_dues(session)

    assert len(records(session, user.psid)) == 1
    assert shop_services.has_paid_dues(session, user.id) is True


def test_me_directory_stats_and_checkout_all_recognize_imported_dues(
    president_client, unauth_client, session, president, monkeypatch, sent_emails
):
    """/me, the member directory, the statistics tiles and checkout all
    recognize verified imported dues — they share one source of truth in
    shop_services.

    One authenticated client only: president_client and `client` both override
    get_current_user on the same app, so the president is the imported member
    here. unauth_client overrides only get_session, so it composes safely.
    """
    seed_multi_selects(session, president)
    stub_sheet(monkeypatch, CURRENT_TITLE, [president.psid])
    sync_dues(session)

    assert president_client.get("/me").json()["has_paid_dues"] is True

    directory = president_client.get("/admin/members").json()
    assert {row["psid"]: row["has_paid_dues"] for row in directory}[president.psid] is True
    assert president_client.get("/admin/stats").json()["dues_paid"] == 1

    # Checkout refuses a second dues purchase, and no order row is created.
    app.dependency_overrides[get_optional_user] = lambda: president
    dues = make_product(session, name=shop_services.DUES_PRODUCT_NAME, price_cents=2000)
    res = unauth_client.post("/shop/orders", json=order_payload(dues))
    assert res.status_code == 400
    assert session.exec(select(Order)).first() is None


def test_an_unverified_member_can_still_buy_dues_at_checkout(
    president_client, unauth_client, session, president, monkeypatch, sent_emails
):
    """The mirror of the case above: an unchecked row must not block checkout.

    Someone whose sheet entry is still awaiting review has not paid as far as
    the app is concerned, so the dues guard has nothing to refuse — otherwise a
    pending row would lock them out of paying at all.
    """
    seed_multi_selects(session, president)
    stub_sheet(monkeypatch, CURRENT_TITLE, [(president.psid, False)])
    sync_dues(session)

    assert president_client.get("/me").json()["has_paid_dues"] is False
    assert president_client.get("/admin/stats").json()["dues_paid"] == 0

    app.dependency_overrides[get_optional_user] = lambda: president
    dues = make_product(session, name=shop_services.DUES_PRODUCT_NAME, price_cents=2000)
    res = unauth_client.post("/shop/orders", json=order_payload(dues))
    assert res.status_code == 201


def test_paid_status_refreshes_so_the_dues_banner_disappears(client, session, monkeypatch, user):
    """Paid status refreshes in the browser and the dues banner disappears.

    The banner's entire condition is `user.has_paid_dues` from /me
    (components/DuesBanner.jsx), so this is that flag flipping without the
    member touching checkout. An unchecked box leaves it up: the banner clears
    when the treasurer verifies, not when the member fills in the form. The
    render itself is verified by hand — there is no frontend test framework in
    this repo.
    """
    seed_multi_selects(session, user)
    assert client.get("/me").json()["has_paid_dues"] is False   # banner showing

    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, False)])
    sync_dues(session)
    assert client.get("/me").json()["has_paid_dues"] is False   # still showing

    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, True)])
    sync_dues(session)
    assert client.get("/me").json()["has_paid_dues"] is True    # banner gone
