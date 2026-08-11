import pytest
from fastapi import HTTPException

from validators.email import normalize_email

def test_canary():
    assert True

def test_valid_email_is_returned_unchanged():
    assert normalize_email("abc@gmail.com") == "abc@gmail.com"

def test_uppercase_email_is_lowercased():
    assert normalize_email("TEST@GMAIL.COM") == "test@gmail.com"

def test_mixed_case_email_is_lowercased():
    assert normalize_email("Test@Cougarnet.UH.edu") == "test@cougarnet.uh.edu"

def test_surrounding_whitespace_is_stripped():
    assert normalize_email("  abc@gmail.com  ") == "abc@gmail.com"

def test_whitespace_and_uppercase_are_both_normalized():
    assert normalize_email("  TEST@GMAIL.COM  ") == "test@gmail.com"

def test_subdomain_email_is_valid():
    assert normalize_email("a@cougarnet.uh.edu") == "a@cougarnet.uh.edu"

def test_plus_tag_and_dots_in_local_part_are_valid():
    assert normalize_email("first.last+tag@gmail.com") == "first.last+tag@gmail.com"

def test_invalid_email_raises_422_with_detail():
    with pytest.raises(HTTPException) as exc_info:
        normalize_email("abc")

    assert exc_info.value.status_code == 422
    assert exc_info.value.detail == "Invalid email format"

def test_email_missing_domain_raises_error():
    with pytest.raises(HTTPException):
        normalize_email("abc@")

def test_email_missing_local_part_raises_error():
    with pytest.raises(HTTPException):
        normalize_email("@gmail.com")

def test_email_missing_tld_raises_error():
    with pytest.raises(HTTPException):
        normalize_email("abc@gmail")

def test_email_with_inner_space_raises_error():
    with pytest.raises(HTTPException):
        normalize_email("a b@gmail.com")

def test_empty_string_raises_error():
    with pytest.raises(HTTPException):
        normalize_email("")

def test_whitespace_only_string_raises_error():
    with pytest.raises(HTTPException):
        normalize_email("   ")

def test_email_with_double_at_raises_error():
    with pytest.raises(HTTPException):
        normalize_email("a@@gmail.com")
