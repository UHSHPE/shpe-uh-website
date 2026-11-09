# Integration tests for run_forms_import: the nightly reconcile of Google Form
# responses into FormPointAward and User.points. Google is faked at the two
# fetch functions; the database is real.

import pytest
from sqlmodel import select

from models.form_point_award import FormPointAward
from services import forms_import_services as forms
from services.forms_import_services import IndexRow, ResponseSource, run_forms_import
from tests.conftest import make_user

SIGN_IN = ResponseSource("sheet-sign-in", 11)
SIGN_OUT = ResponseSource("sheet-sign-out", 22)
HEADER = ["Timestamp", "PSID", "Cougarnet Email", "Are you wearing a SHPE shirt?", "Did you bring a new member(s)"]


def response(psid="1234567", email="", shirt="", new_member=""):
    return ["11/8/2026 18:00:00", psid, email, shirt, new_member]


def index_row(row_number=2, committee="Social", special=None, sign_in=SIGN_IN, sign_out=SIGN_OUT):
    return IndexRow(row_number, "Game Night", committee, special, sign_in, sign_out)


class FakeSheets:
    """Stands in for Google: an index tab plus one response tab per source."""

    def __init__(self):
        self.index = [index_row()]
        self.tabs = {SIGN_IN: [HEADER, response()], SIGN_OUT: [HEADER, response()]}
        self.failing: set[ResponseSource] = set()
        self.index_error: Exception | None = None

    def fetch_index_rows(self, client):
        if self.index_error:
            raise self.index_error
        return self.index

    def fetch_responses(self, client, source):
        if source in self.failing:
            raise RuntimeError("simulated Google failure")
        return self.tabs[source]


@pytest.fixture
def sheets(monkeypatch):
    fake = FakeSheets()
    monkeypatch.setattr(forms, "get_client", lambda: object())
    monkeypatch.setattr(forms, "fetch_index_rows", fake.fetch_index_rows)
    monkeypatch.setattr(forms, "fetch_responses", fake.fetch_responses)
    return fake


def points_of(session, user):
    session.refresh(user)
    return user.points


def awards(session):
    return session.exec(select(FormPointAward)).all()


# --- basic awarding ---

def test_unconfigured_is_a_no_op(session, user):
    assert run_forms_import(session).status == "unconfigured"
    assert awards(session) == []


def test_sign_in_and_sign_out_are_awarded(session, user, sheets):
    result = run_forms_import(session)
    assert (result.status, result.awarded) == ("synced", 2)
    assert points_of(session, user) == 3 + 2   # Social sign-in + sign-out


def test_gm_bonuses_are_added_on_sign_in(session, user, sheets):
    sheets.index = [index_row(committee="EBoard", special="GM")]
    sheets.tabs[SIGN_IN] = [HEADER, response(shirt="Yes (I lob shpe!)", new_member="Yes!")]
    run_forms_import(session)
    assert points_of(session, user) == (3 + 2 + 2) + 2


def test_sign_out_counts_without_a_sign_in(session, user, sheets):
    sheets.tabs[SIGN_IN] = [HEADER]
    run_forms_import(session)
    assert points_of(session, user) == 2


def test_member_matched_by_cougarnet_email(session, sheets):
    member = make_user(session, psid="7654321", cougarnet_email="ana@cougarnet.uh.edu",
                       personal_email="ana@gmail.com")
    tab = [["Timestamp", "Cougarnet Email"], ["11/8/2026", "Ana@CougarNet.UH.edu"]]
    sheets.tabs = {SIGN_IN: tab, SIGN_OUT: [HEADER]}
    run_forms_import(session)
    assert points_of(session, member) == 3


def test_existing_points_are_kept(session, sheets):
    member = make_user(session, points=10)
    run_forms_import(session)
    assert points_of(session, member) == 15


# --- never double-award ---

def test_rerun_does_not_double_award(session, user, sheets):
    run_forms_import(session)
    result = run_forms_import(session)
    assert (result.awarded, result.adjusted, result.revoked) == (0, 0, 0)
    assert points_of(session, user) == 5


def test_submitting_twice_counts_once(session, user, sheets):
    sheets.tabs[SIGN_IN] = [HEADER, response(), response()]
    run_forms_import(session)
    assert points_of(session, user) == 5


def test_psid_and_email_submissions_by_one_member_count_once(session, user, sheets):
    """Second submission has a typo'd PSID, so it falls back to email -- same account."""
    sheets.tabs[SIGN_IN] = [HEADER, response(), response(psid="12345", email=user.cougarnet_email)]
    run_forms_import(session)
    assert points_of(session, user) == 5
    assert len(awards(session)) == 2


def test_best_of_several_submissions_wins(session, user, sheets):
    sheets.index = [index_row(committee="EBoard", special="GM")]
    sheets.tabs[SIGN_IN] = [HEADER, response(shirt="Nope"), response(shirt="Yes (I lob shpe!)")]
    run_forms_import(session)
    assert points_of(session, user) == (3 + 2) + 2


# --- adjusting and taking back ---

def test_marking_a_row_gm_later_adjusts_by_the_difference(session, user, sheets):
    sheets.index = [index_row(committee="EBoard")]
    run_forms_import(session)
    assert points_of(session, user) == 2 + 2

    sheets.index = [index_row(committee="EBoard", special="GM")]
    result = run_forms_import(session)
    assert result.adjusted == 1
    assert points_of(session, user) == 3 + 2


def test_deleted_index_row_takes_points_back(session, sheets):
    member = make_user(session, points=10)
    other = index_row(row_number=3, sign_in=ResponseSource("other", 0), sign_out=None)
    sheets.index = [index_row(), other]
    sheets.tabs[ResponseSource("other", 0)] = [HEADER, response()]
    run_forms_import(session)
    assert points_of(session, member) == 10 + 5 + 3

    sheets.index = [other]
    result = run_forms_import(session)
    assert result.revoked == 2
    assert points_of(session, member) == 10 + 3


def test_deleted_response_takes_only_that_award_back(session, user, sheets):
    run_forms_import(session)
    sheets.tabs[SIGN_OUT] = [HEADER]
    run_forms_import(session)
    assert points_of(session, user) == 3


def test_row_numbers_shifting_does_not_move_awards(session, user, sheets):
    """Deleting a row above renumbers everything below; awards key on the sheet, not the row."""
    run_forms_import(session)
    sheets.index = [index_row(row_number=40)]
    result = run_forms_import(session)
    assert (result.awarded, result.revoked) == (0, 0)
    assert points_of(session, user) == 5
    assert {a.index_row for a in awards(session)} == {40}


def test_take_back_never_goes_below_zero(session, user, sheets):
    """Points reset by hand after an award must not turn negative on revoke."""
    run_forms_import(session)
    user.points = 0
    session.add(user)
    session.commit()
    sheets.tabs[SIGN_OUT] = [HEADER]
    run_forms_import(session)
    assert points_of(session, user) == 0


# --- failures must not look like deletions ---

def test_failed_response_sheet_keeps_its_awards(session, user, sheets):
    run_forms_import(session)
    sheets.failing = {SIGN_IN}
    result = run_forms_import(session)
    assert (result.sources_failed, result.revoked) == (1, 0)
    assert points_of(session, user) == 5


def test_failed_sheet_does_not_block_the_others(session, user, sheets):
    sheets.failing = {SIGN_IN}
    run_forms_import(session)
    assert points_of(session, user) == 2


def test_invalid_index_sheet_changes_nothing(session, user, sheets):
    run_forms_import(session)
    sheets.index_error = ValueError("Points sheet is missing required column(s): sign in")
    assert run_forms_import(session).status == "invalid_sheet"
    assert points_of(session, user) == 5
    assert len(awards(session)) == 2


def test_empty_index_sheet_refuses_to_revoke_everything(session, user, sheets):
    run_forms_import(session)
    sheets.index = []
    assert run_forms_import(session).status == "invalid_sheet"
    assert points_of(session, user) == 5


def test_unparseable_response_sheet_is_a_failed_source(session, user, sheets):
    """A tab with no PSID or UH email column raises in parse_responses."""
    sheets.tabs[SIGN_IN] = [["Timestamp", "Full Name"], ["11/8/2026", "Ana"]]
    result = run_forms_import(session)
    assert result.sources_failed == 1
    assert points_of(session, user) == 2


def test_blank_response_tab_keeps_its_awards(session, user, sheets):
    run_forms_import(session)
    sheets.tabs[SIGN_IN] = []
    result = run_forms_import(session)
    assert (result.sources_failed, result.revoked) == (1, 0)
    assert points_of(session, user) == 5
    assert len(awards(session)) == 2


def test_unusable_link_drops_points_until_fixed_without_doubling(session, user, sheets):
    """A Form link pasted over a response-sheet link parses as no link; fixing it restores the points once."""
    run_forms_import(session)
    sheets.index = [index_row(sign_in=None)]
    run_forms_import(session)
    assert points_of(session, user) == 2

    sheets.index = [index_row()]
    run_forms_import(session)
    run_forms_import(session)
    assert points_of(session, user) == 5


# --- pending until a verified account exists ---

def test_unmatched_response_waits_then_credits_once(session, sheets):
    sheets.tabs = {SIGN_IN: [HEADER, response(psid="7654321")], SIGN_OUT: [HEADER]}
    result = run_forms_import(session)
    assert (result.awarded, result.pending) == (0, 1)

    member = make_user(session, psid="7654321", cougarnet_email="new@cougarnet.uh.edu",
                       personal_email="new@gmail.com")
    result = run_forms_import(session)
    assert (result.awarded, result.pending) == (1, 0)
    assert points_of(session, member) == 3

    run_forms_import(session)
    assert points_of(session, member) == 3


def test_mistyped_psid_falls_back_to_a_matching_email(session, user, sheets):
    sheets.tabs = {SIGN_IN: [HEADER, response(psid="7654321", email=user.cougarnet_email)], SIGN_OUT: [HEADER]}
    result = run_forms_import(session)
    assert (result.awarded, result.pending) == (1, 0)
    assert points_of(session, user) == 3


def test_matching_psid_with_unknown_email_credits_the_psid(session, user, sheets):
    sheets.tabs = {SIGN_IN: [HEADER, response(email="nobody@cougarnet.uh.edu")], SIGN_OUT: [HEADER]}
    run_forms_import(session)
    assert points_of(session, user) == 3


def test_psid_wins_when_psid_and_email_name_different_accounts(session, user, sheets, caplog):
    other = make_user(session, psid="7654321", cougarnet_email="other@cougarnet.uh.edu",
                      personal_email="other@gmail.com")
    sheets.tabs = {SIGN_IN: [HEADER, response(email=other.cougarnet_email)], SIGN_OUT: [HEADER]}
    with caplog.at_level("WARNING"):
        run_forms_import(session)
    assert (points_of(session, user), points_of(session, other)) == (3, 0)
    assert "row 2" in caplog.text
    assert "1234567" not in caplog.text and "other@" not in caplog.text   # no PII in logs


def test_award_stuck_pending_on_a_typo_is_credited_once(session, user, sheets):
    """Before email fallback, a typo'd PSID left a pending award; the next run must move it to the account."""
    session.add(FormPointAward(spreadsheet_id=SIGN_IN.spreadsheet_id, gid=SIGN_IN.gid, member_key="psid:7654321",
                               kind="sign_in", points=3, index_row=2, event_name="Game Night"))
    session.commit()
    sheets.tabs = {SIGN_IN: [HEADER, response(psid="7654321", email=user.cougarnet_email)], SIGN_OUT: [HEADER]}
    result = run_forms_import(session)
    assert (result.awarded, result.pending) == (1, 0)
    run_forms_import(session)
    assert points_of(session, user) == 3
    assert [a.member_key for a in awards(session)] == [f"user:{user.id}"]


def test_unverified_account_is_not_credited(session, sheets):
    member = make_user(session, psid="7654321", cougarnet_email="new@cougarnet.uh.edu",
                       personal_email="new@gmail.com", email_verified=False)
    sheets.tabs = {SIGN_IN: [HEADER, response(psid="7654321")], SIGN_OUT: [HEADER]}
    result = run_forms_import(session)
    assert result.pending == 1
    assert points_of(session, member) == 0
    assert awards(session)[0].user_id is None


# --- concurrency ---

def test_overlapping_run_is_refused(session, user, sheets):
    assert forms._import_lock.acquire(blocking=False)
    try:
        assert run_forms_import(session).status == "busy"
    finally:
        forms._import_lock.release()
    assert points_of(session, user) == 0
