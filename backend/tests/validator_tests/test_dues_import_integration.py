"""Cover dues integration boundaries beyond the membership verification contract."""

import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock

import pytest
from sqlmodel import select

import main
from models.dues_import import DuesSyncResult, ImportedDues
from models.user.user_enums import Role
from services import dues_import_services, shop_services
from tests.admin_tests.conftest import president, president_client  # noqa: F401
from tests.admin_tests.conftest import make_dues_order
from tests.validator_tests.test_membershpe_verification import CURRENT_TITLE, FakeSheet, stub_sheet


@pytest.mark.parametrize("title", [
    "SHPE Membership", "2026-2028 Membership", "2026-2027 and 2027-2028 Membership",
])
def test_invalid_year_leaves_existing_dues_unchanged(session, monkeypatch, user, title):
    """Reject ambiguous academic years before changing any dues records."""
    stub_sheet(monkeypatch, CURRENT_TITLE, [user.psid])
    dues_import_services.sync_dues(session)
    stub_sheet(monkeypatch, title, ["7654321"])

    result = dues_import_services.sync_dues(session)

    assert result.status == "invalid_sheet"
    assert [record.psid for record in session.exec(select(ImportedDues)).all()] == [user.psid]


def test_sparse_aa_checkbox_does_not_read_intervening_columns():
    """Treat a missing AA cell as unchecked even if column G contains TRUE."""
    sheet = FakeSheet(CURRENT_TITLE, [("1234567", False), ("7654321", True)])
    values = sheet.sheet1.get_all_values()
    values[1][6] = "TRUE"
    values[1] = values[1][:7]

    claims, skipped = dues_import_services.parse_sheet_rows(values)

    assert values[0][5] == "Student PSID"
    assert values[0][26] == "Payment Verified?"
    assert claims == {"1234567": False, "7654321": True}
    assert skipped == 0


def test_duplicate_verification_header_is_rejected():
    """Reject duplicate headers instead of guessing which checkbox counts."""
    values = [["Student PSID", "Payment Verified?", "Payment Verified?"], ["1234567", "TRUE", "FALSE"]]
    with pytest.raises(ValueError):
        dues_import_services.parse_sheet_rows(values)


@pytest.mark.parametrize("setting", ["DUES_SHEET_ID", "DUES_TRACKER_CREDENTIALS"])
def test_missing_configuration_does_not_contact_google(monkeypatch, setting):
    """Require both dedicated settings before opening a Google connection."""
    monkeypatch.setenv(setting, "test-placeholder")
    authorize = Mock(side_effect=AssertionError("Google must not be contacted"))
    monkeypatch.setattr(dues_import_services.gspread, "authorize", authorize)

    assert dues_import_services.get_sheet() is None
    authorize.assert_not_called()


@pytest.mark.parametrize("inline", [False, True])
def test_reader_uses_dedicated_credentials_and_readonly_scope(monkeypatch, inline):
    """Use the configured dues identity with a read-only scope and bounded timeout."""
    credentials = '{"type": "service_account"}' if inline else "/test/dues.json"
    monkeypatch.setenv("DUES_TRACKER_CREDENTIALS", credentials)
    monkeypatch.setenv("DUES_SHEET_ID", "dues-sheet")
    factory = Mock()
    method = "from_service_account_info" if inline else "from_service_account_file"
    monkeypatch.setattr(dues_import_services.Credentials, method, factory)
    client = Mock()
    authorize = Mock(return_value=client)
    monkeypatch.setattr(dues_import_services.gspread, "authorize", authorize)

    assert dues_import_services.get_sheet() is client.open_by_key.return_value
    expected_credentials = {"type": "service_account"} if inline else credentials
    factory.assert_called_once_with(expected_credentials, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    authorize.assert_called_once_with(factory.return_value)
    client.open_by_key.assert_called_once_with("dues-sheet")
    client.set_timeout.assert_called_once_with(30)


@pytest.mark.parametrize("role", [Role.president, Role.vpi, Role.vpe])
def test_authorized_officer_can_sync_without_exposing_psids(president_client, president, session, monkeypatch, role):
    """Allow each member-admin role to sync and return aggregate counts."""
    president.role = role
    session.add(president)
    session.commit()
    stub_sheet(monkeypatch, CURRENT_TITLE, [(president.psid, True), ("1234567", False)])

    response = president_client.post("/admin/dues/sync")

    assert response.status_code == 200
    assert response.json()["processed"] == 2
    assert response.json()["verified"] == 1
    assert president.psid not in response.text
    assert "1234567" not in response.text


def test_member_cannot_trigger_sync(client, monkeypatch):
    """Reject ordinary members before calling the import service."""
    sync = Mock()
    monkeypatch.setattr(dues_import_services, "sync_dues", sync)

    assert client.post("/admin/dues/sync").status_code == 403
    sync.assert_not_called()


def test_anonymous_caller_cannot_trigger_sync(unauth_client, monkeypatch):
    """Require authentication before calling the import service."""
    sync = Mock()
    monkeypatch.setattr(dues_import_services, "sync_dues", sync)

    assert unauth_client.post("/admin/dues/sync").status_code == 401
    sync.assert_not_called()


@pytest.mark.parametrize("outcome, status_code", [("unconfigured", 503), ("invalid_sheet", 422), ("busy", 409)])
def test_sync_route_reports_non_success(president_client, monkeypatch, outcome, status_code):
    """Report skipped and invalid imports as actionable HTTP errors."""
    monkeypatch.setattr(dues_import_services, "sync_dues", lambda _: DuesSyncResult(status=outcome))
    assert president_client.post("/admin/dues/sync").status_code == status_code


def test_network_failure_does_not_leak_error_details(president_client, monkeypatch):
    """Return a generic failure and allow the next sync to acquire the lock."""
    monkeypatch.setattr(dues_import_services, "get_sheet", Mock(side_effect=ConnectionError("private upstream detail")))
    response = president_client.post("/admin/dues/sync")

    assert response.status_code == 503
    assert "private upstream detail" not in response.text
    monkeypatch.setattr(dues_import_services, "get_sheet", lambda: None)
    assert president_client.post("/admin/dues/sync").json()["detail"] == "Dues sheet integration is not configured."


def test_native_payment_survives_an_unchecked_sheet_claim(session, user, monkeypatch):
    """Keep qualifying website payments independent of unverified sheet entries."""
    make_dues_order(session, user)
    stub_sheet(monkeypatch, CURRENT_TITLE, [(user.psid, False)])
    dues_import_services.sync_dues(session)

    assert shop_services.has_paid_dues(session, user.id)
    assert user.id in shop_services.dues_paid_user_ids(session)


def test_overlapping_sync_is_skipped_and_lock_is_released(monkeypatch):
    """Run only one import at a time and release the lock on completion."""
    started, finish = Event(), Event()

    def slow_read():
        """Hold the first import open while a second request arrives."""
        started.set()
        assert finish.wait(timeout=5)
        return None

    monkeypatch.setattr(dues_import_services, "get_sheet", slow_read)
    with ThreadPoolExecutor(max_workers=1) as executor:
        first_sync = executor.submit(dues_import_services.sync_dues, Mock())
        try:
            assert started.wait(timeout=5)
            assert dues_import_services.sync_dues(Mock()).status == "busy"
        finally:
            finish.set()
        assert first_sync.result(timeout=5).status == "unconfigured"
    assert dues_import_services.sync_dues(Mock()).status == "unconfigured"


def test_background_loop_retries_failure_at_ten_minute_interval(monkeypatch):
    """Retry a failed background import on the next scheduled interval."""
    dispatch = Mock(side_effect=[ConnectionError("unavailable"), None])
    monkeypatch.setattr(main, "dispatch_dues_sync", dispatch)
    waits = []

    async def next_interval(seconds):
        """Stop the loop after two attempted imports."""
        waits.append(seconds)
        if len(waits) == 2:
            raise asyncio.CancelledError

    monkeypatch.setattr(main.asyncio, "sleep", next_interval)
    with pytest.raises(asyncio.CancelledError):
        asyncio.run(main.dues_sync_loop())
    assert dispatch.call_count == 2
    assert waits == [600, 600]
