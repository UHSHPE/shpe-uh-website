# Unit tests for the pure parsing half of services/forms_import_services.py.
# Inputs mirror what the Sheets API returns; no Google, no DB.

import logging

import pytest

from services.event_tracker_services import get_event_type
from services.forms_import_services import (
    FormResponse,
    ResponseSource,
    find_email_column,
    find_new_member_column,
    find_psid_column,
    find_shirt_column,
    parse_index_rows,
    parse_responses,
    parse_psid,
    parse_response_link,
    parse_yes_no,
    response_identity,
)

SHEET_A = "1AbCdEfGhIjKlMnOpQrStUvWxYz0123456789_-abcd"
SHEET_B = "1ZyXwVuTsRqPoNmLkJiHgFeDcBa9876543210-_wxyz"
FORM_ID = "1QwErTyUiOpAsDfGhJkLzXcVbNm0123456789_-qwer"


def link(sheet_id=SHEET_A, gid=0):
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit?gid={gid}"


def cell(text="", url=None):
    """One cell as the Sheets API returns it: display text plus an optional hyperlink."""
    c = {"formattedValue": text} if text else {}
    if url:
        c["hyperlink"] = url
    return c


# Real header row, trailing spaces and unlabeled column A included.
HEADER = ["", "Event Name ", "Sign in ", "Sign out ", "Committee", "Special Event Type"]


def index(*rows, header=HEADER):
    return [{"values": [cell(h) for h in header]}] + [{"values": r} for r in rows]


def event_row(name="Game Night", sign_in=None, sign_out=None, committee="Social", special="", week="Week 3 - Monday"):
    return [
        cell(week),
        cell(name),
        cell("Sign in", sign_in) if sign_in else cell(),
        cell("Sign out", sign_out) if sign_out else cell(),
        cell(committee),
        cell(special),
    ]


# --- index sheet -> event rows ---

def test_parses_a_full_row():
    [row] = parse_index_rows(index(event_row(sign_in=link(SHEET_A, 11), sign_out=link(SHEET_B, 22), special="gm")))
    assert row.row_number == 2
    assert row.event_name == "Game Night"
    assert row.committee == "Social"
    assert row.special_type == "gm"
    assert row.sign_in == ResponseSource(SHEET_A, 11)
    assert row.sign_out == ResponseSource(SHEET_B, 22)


def test_headers_match_ignoring_case_and_spacing():
    header = ["", "  EVENT NAME", "sign IN", "Sign Out", " committee ", "special event type  "]
    [row] = parse_index_rows(index(event_row(sign_in=link()), header=header))
    assert row.sign_in == ResponseSource(SHEET_A, 0)


def test_columns_are_found_by_header_not_position():
    """A chair inserting or reordering a column must not shift every field."""
    header = ["Committee", "Sign out ", "", "Special Event Type", "Sign in ", "Event Name "]
    values = [cell("Social"), cell("Sign out", link(SHEET_B)), cell("Week 1"), cell(""),
              cell("Sign in", link(SHEET_A)), cell("Game Night")]
    [row] = parse_index_rows(index(values, header=header))
    assert (row.event_name, row.committee) == ("Game Night", "Social")
    assert row.sign_in == ResponseSource(SHEET_A, 0)
    assert row.sign_out == ResponseSource(SHEET_B, 0)


@pytest.mark.parametrize("missing", ["Event Name ", "Sign in ", "Sign out ", "Committee", "Special Event Type"])
def test_missing_required_header_raises(missing):
    """Silently importing nothing is worse than failing loudly."""
    header = [h for h in HEADER if h != missing]
    with pytest.raises(ValueError):
        parse_index_rows(index(header=header))


def test_rows_without_any_link_are_skipped():
    rows = parse_index_rows(index(
        [cell("Week 4")],                          # week label row
        [],                                        # empty row
        event_row(name="Planned Event"),           # event with no forms yet
        event_row(name="Linked", sign_in=link()),
    ))
    assert [r.event_name for r in rows] == ["Linked"]


def test_row_numbers_are_sheet_rows_after_skipped_rows():
    """Warnings cite the row a chair sees in the sheet, so skips must not renumber."""
    rows = parse_index_rows(index([cell("Week 1")], [], event_row(sign_in=link())))
    assert rows[0].row_number == 4


@pytest.mark.parametrize("text", ["no sign out ", "N/A", "none"])
def test_text_without_a_link_means_no_sign_out(text):
    values = event_row(sign_in=link())
    values[3] = cell(text)
    [row] = parse_index_rows(index(values))
    assert row.sign_out is None


def test_sign_out_only_row_is_kept():
    [row] = parse_index_rows(index(event_row(sign_out=link(SHEET_B))))
    assert row.sign_in is None
    assert row.sign_out == ResponseSource(SHEET_B, 0)


def test_committee_and_special_type_are_stripped():
    [row] = parse_index_rows(index(event_row(sign_in=link(), committee="  SHPEtina ", special=" study red ")))
    assert (row.committee, row.special_type) == ("SHPEtina", "study red")


def test_blank_special_type_is_none():
    [row] = parse_index_rows(index(event_row(sign_in=link(), special="   ")))
    assert row.special_type is None


def test_form_link_instead_of_response_sheet_is_dropped_with_a_warning(caplog):
    form = f"https://docs.google.com/forms/d/{FORM_ID}/edit"
    with caplog.at_level(logging.WARNING):
        [row] = parse_index_rows(index(event_row(sign_in=form, sign_out=link(SHEET_B))))
    assert row.sign_in is None
    assert row.sign_out == ResponseSource(SHEET_B, 0)
    assert "row 2" in caplog.text


def test_row_whose_only_link_is_unusable_is_skipped(caplog):
    form = f"https://docs.google.com/forms/d/{FORM_ID}/edit"
    with caplog.at_level(logging.WARNING):
        rows = parse_index_rows(index(event_row(sign_in=form)))
    assert rows == []
    assert "row 2" in caplog.text


# --- link -> (spreadsheet, tab) ---

def test_link_with_gid_in_query():
    assert parse_response_link(link(SHEET_A, 123456)) == ResponseSource(SHEET_A, 123456)


def test_resourcekey_is_ignored():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_A}/edit?gid=42&resourcekey=0-AbCdEf123"
    assert parse_response_link(url) == ResponseSource(SHEET_A, 42)


def test_gid_in_fragment():
    url = f"https://docs.google.com/spreadsheets/d/{SHEET_A}/edit#gid=77"
    assert parse_response_link(url) == ResponseSource(SHEET_A, 77)


def test_missing_gid_means_first_tab():
    assert parse_response_link(f"https://docs.google.com/spreadsheets/d/{SHEET_A}/edit") == ResponseSource(SHEET_A, 0)


@pytest.mark.parametrize(
    "url",
    [
        f"https://docs.google.com/forms/d/{FORM_ID}/edit",
        f"https://docs.google.com/forms/d/e/{FORM_ID}/viewform",
        "https://forms.gle/AbC123xYz",
        f"https://docs.google.com/document/d/{SHEET_A}/edit",
        "https://example.com/spreadsheets/d/abc",
        "",
        "not a url",
    ],
)
def test_anything_but_a_response_sheet_is_none(url):
    assert parse_response_link(url) is None


# --- PSID column ---

@pytest.mark.parametrize(
    "title",
    [
        "PSID", "PSID #", "PSID (#######)", "PSID number", "PSID Number", "PSID NUMBER",
        "PeopleSoft ID", "PeopleSoft ID #", "PeopleSoft ID (7 Digit number)", "UH ID",
    ],
)
def test_psid_column_variants_are_found(title):
    assert find_psid_column(["Timestamp", "Full Name", title, "Cougarnet Email"]) == 2


def test_no_psid_column_is_none():
    assert find_psid_column(["Timestamp", "Full Name", "Cougarnet Email", "Did u have fun?"]) is None


# --- email column ---

@pytest.mark.parametrize(
    "title",
    [
        "Cougarnet Email", "Cougarnet email (user@cougarnet.uh.edu)", "Courgarnet Email (user@cougarnet.uh.edu)",
        "Couagarnet Email", "Cougar Net Email", "Cougarnet (user@cougarnet.uh.edu)",
        "UH Email Address", "UH E-mail Address", "UH Cougarnet Email (@cougarnet.uh.edu)",
        "Email (user@cougarnet.uh.edu)",
    ],
)
def test_uh_email_column_variants_are_found(title):
    assert find_email_column(["Timestamp", "Full Name", title]) == 2


def test_personal_email_is_never_picked():
    header = ["Timestamp", "Personal Email *Headshot photos will be sent to this email !!!"]
    assert find_email_column(header) is None


def test_cougarnet_column_wins_over_personal_email():
    header = ["Timestamp", "Personal Email *Headshot photos will be sent to this email !!!", "Cougarnet Email"]
    assert find_email_column(header) == 2


@pytest.mark.parametrize("title", ["Email Address", "Email", "E-mail"])
def test_generic_email_column_is_never_picked(title):
    """Only the UH email is tracked; a generic one may be a personal account."""
    assert find_email_column(["Timestamp", "Full Name", title]) is None


def test_cougarnet_column_is_picked_over_a_generic_email_column():
    assert find_email_column(["Timestamp", "Email Address", "Full Name", "Cougarnet Email"]) == 3


def test_no_email_column_is_none():
    assert find_email_column(["Timestamp", "Full Name", "PSID"]) is None


# --- PSID values ---

@pytest.mark.parametrize("raw", ["1234567", " 1234567 ", "#1234567"])
def test_valid_psids(raw):
    assert parse_psid(raw) == "1234567"


def test_leading_zeros_are_kept():
    assert parse_psid("0012345") == "0012345"


@pytest.mark.parametrize("raw", ["", "   ", "123456", "12345678", "123-4567", "abcdefg", "1234567a", None])
def test_invalid_psids_are_none(raw):
    assert parse_psid(raw) is None


# --- member identity for one response row ---

def test_valid_psid_identifies_the_member():
    row = ["11/8/2026 18:00:00", "Ana Lopez", "1234567", "ana@cougarnet.uh.edu"]
    assert response_identity(row, psid_col=2, email_col=3) == ("1234567", "ana@cougarnet.uh.edu")


def test_no_psid_column_falls_back_to_cougarnet_email():
    row = ["11/8/2026 18:00:00", "Ana Lopez", "  Ana@CougarNet.UH.edu "]
    assert response_identity(row, psid_col=None, email_col=2) == (None, "ana@cougarnet.uh.edu")


@pytest.mark.parametrize("bad_psid", ["", "123456", "12345678", "N/A"])
def test_malformed_psid_is_dropped_but_email_kept(bad_psid):
    row = ["11/8/2026 18:00:00", "Ana Lopez", bad_psid, "ana@cougarnet.uh.edu"]
    assert response_identity(row, psid_col=2, email_col=3) == (None, "ana@cougarnet.uh.edu")


def test_valid_psid_with_malformed_email_keeps_the_psid():
    row = ["11/8/2026 18:00:00", "Ana Lopez", "1234567", "not an email"]
    assert response_identity(row, psid_col=2, email_col=3) == ("1234567", None)


def test_invalid_psid_and_invalid_email_is_none():
    row = ["11/8/2026 18:00:00", "Ana Lopez", "123", "not an email"]
    assert response_identity(row, psid_col=2, email_col=3) is None


def test_short_row_missing_trailing_cells_is_none():
    """The Sheets API drops trailing empty cells, so a row can be shorter than the header."""
    assert response_identity(["11/8/2026 18:00:00", "Ana Lopez"], psid_col=2, email_col=3) is None


def test_blank_response_row_is_none():
    assert response_identity(["", "", "", ""], psid_col=2, email_col=3) is None


# --- GM bonus questions ---

# Real GM sign-in header: "member" and "new member" both appear in columns
# that are NOT the bring-a-new-member question.
GM_SIGN_IN_HEADER = [
    "Timestamp", "First Name", "Last Name", "Cougarnet Email", "PSID",
    "Are you a paid member? (Locally and Nationally)",
    "Are you wearing a SHPE shirt?",
    "Did you bring a new member(s)",
    "What is the new member's name?",
    "Did you apply to a position for LYB?",
]
GM_SIGN_OUT_HEADER = ["Timestamp", "First Name", "Last Name", "Cougarnet Email", "PSID", "Did you have fun today?"]


def test_shirt_column_is_found():
    assert find_shirt_column(GM_SIGN_IN_HEADER) == 6


def test_new_member_column_is_the_bring_question():
    assert find_new_member_column(GM_SIGN_IN_HEADER) == 7


def test_new_member_name_column_is_never_picked():
    """Reading typed names as answers would award the bonus to everyone who filled it in."""
    header = ["Timestamp", "PSID", "What is the new member's name?"]
    assert find_new_member_column(header) is None


def test_paid_member_column_is_never_picked():
    header = ["Timestamp", "PSID", "Are you a paid member? (Locally and Nationally)"]
    assert find_new_member_column(header) is None


def test_bonus_columns_match_ignoring_case_and_spacing():
    header = ["Timestamp", "  ARE YOU WEARING A SHPE SHIRT? ", "did you   bring a NEW MEMBER(S)"]
    assert (find_shirt_column(header), find_new_member_column(header)) == (1, 2)


def test_forms_without_bonus_questions_have_no_bonus_columns():
    assert find_shirt_column(GM_SIGN_OUT_HEADER) is None
    assert find_new_member_column(GM_SIGN_OUT_HEADER) is None


# --- yes / no answers ---

@pytest.mark.parametrize("raw", ["Yes (I lob shpe!)", "Yes!", "yes", "  YES  "])
def test_yes_answers(raw):
    assert parse_yes_no(raw) is True


@pytest.mark.parametrize("raw", ["Nope (waiting for this year's shirt!!)", "No", "no", "  NOPE "])
def test_no_answers(raw):
    assert parse_yes_no(raw) is False


@pytest.mark.parametrize("raw", ["", "   ", None, "Maybe", "idk"])
def test_blank_or_unrecognized_answers_are_none(raw):
    """None, not False, so the importer can tell a missing answer from a real 'no'."""
    assert parse_yes_no(raw) is None


def test_answer_is_matched_on_the_leading_word_not_anywhere():
    """'Nope' contains 'no', and free text could contain 'yes' mid-sentence."""
    assert parse_yes_no("Nope, not yes") is False
    assert parse_yes_no("Notably yes") is None


# --- Committee dropdown -> event_type slug ---

@pytest.mark.parametrize(
    ("committee", "slug"),
    [
        ("Academic", "academic"),
        ("Athletics", "athletic"),
        ("CFC", "career_fair"),
        ("EBoard", "eboard"),
        ("EEC", "eec"),
        ("MentorSHPE", "mentorshpe"),
        ("Outreach", "outreach"),
        ("Professional", "professional"),
        ("Projects", "projects"),
        ("SHPE Jr", "shpe_jr"),
        ("SHPEtina", "shpetina"),
        ("Social", "social"),
    ],
)
def test_every_points_sheet_committee_option_maps_to_its_slug(committee, slug):
    """The points sheet reuses the tracker's mapping; an unmapped option would
    silently score as eboard instead of its real committee."""
    assert get_event_type(committee) == slug


def test_unknown_committee_falls_back_to_eboard():
    assert get_event_type("Brand New Committee") == "eboard"


# --- one response tab -> FormResponse list ---

def test_parses_gm_responses_with_bonuses():
    values = [
        GM_SIGN_IN_HEADER,
        ["11/8/2026 18:00:00", "Ana", "Lopez", "ana@cougarnet.uh.edu", "1234567", "Yes",
         "Yes (I lob shpe!)", "Yes!", "Luis", "No"],
        ["11/8/2026 18:01:00", "Ben", "Cruz", "ben@cougarnet.uh.edu", "7654321", "No",
         "Nope (waiting for this year's shirt!!)", "No", "", "No"],
    ]
    assert parse_responses(values) == [
        FormResponse(row_number=2, psid="1234567", email="ana@cougarnet.uh.edu",
                     wore_shirt=True, brought_new_member=True),
        FormResponse(row_number=3, psid="7654321", email="ben@cougarnet.uh.edu",
                     wore_shirt=False, brought_new_member=False),
    ]


def test_forms_without_bonus_questions_record_no_bonuses():
    values = [GM_SIGN_OUT_HEADER, ["11/8/2026 20:00:00", "Ana", "Lopez", "ana@cougarnet.uh.edu", "1234567", "yes"]]
    [resp] = parse_responses(values)
    assert (resp.wore_shirt, resp.brought_new_member) == (False, False)


def test_unanswered_bonus_question_is_no_bonus():
    row = ["11/8/2026 18:00:00", "Ana", "Lopez", "ana@cougarnet.uh.edu", "1234567", "Yes", "", "Maybe"]
    [resp] = parse_responses([GM_SIGN_IN_HEADER, row])
    assert (resp.wore_shirt, resp.brought_new_member) == (False, False)


def test_email_only_form_identifies_by_cougarnet_email():
    values = [["Timestamp", "Full Name", "Cougarnet Email"], ["11/8/2026 18:00:00", "Ana Lopez", "Ana@CougarNet.uh.edu"]]
    [resp] = parse_responses(values)
    assert (resp.psid, resp.email) == (None, "ana@cougarnet.uh.edu")


def test_blank_and_unidentifiable_rows_are_skipped_and_unidentifiable_ones_warned(caplog):
    values = [
        ["Timestamp", "Full Name", "PSID", "Cougarnet Email"],
        ["", "", "", ""],
        ["11/8/2026 18:00:00", "Ana Lopez", "123", "not an email"],
        ["11/8/2026 18:01:00", "Ben Cruz", "7654321"],
    ]
    with caplog.at_level(logging.WARNING):
        responses = parse_responses(values)
    assert [r.row_number for r in responses] == [4]
    assert "row 3" in caplog.text
    assert "row 2" not in caplog.text
    assert "Ana" not in caplog.text and "123" not in caplog.text   # no PII in logs


def test_form_with_no_identifier_column_raises():
    """Better to fail one source loudly than to award nobody silently."""
    with pytest.raises(ValueError):
        parse_responses([["Timestamp", "Full Name", "Email Address"], ["11/8/2026", "Ana", "ana@gmail.com"]])


def test_empty_tab_raises():
    """Even a form with no responses has a header row; a fully blank tab was wiped, not emptied."""
    with pytest.raises(ValueError):
        parse_responses([])


def test_header_only_tab_has_no_responses():
    assert parse_responses([["Timestamp", "PSID"]]) == []
