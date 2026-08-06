import pytest
from pydantic import ValidationError
from datetime import date

from models.user.user_schemas import UserCreate
from models.user.user_enums import *

def valid_user_data(**overrides):
    data = {
        "first_name": "John",
        "last_name": "Doe",
        
        "cougarnet_email": "abc@cougarnet.uh.edu",
        "personal_email": "abc@gmail.com",

        "phone_num": "1234562323",
        "psid": "1234567",
        "birthday": date(2000, 1, 1),
        
        "gender": Gender.male,
        "first_gen": True,
        
        "college": Colleges.nsm,
        "major": "Computer Science",
        "classification": Classification.senior,
        "gpa": GPA.gpa_350_400,
        "exp_grad_date": ExpGradDate.spring_2027,
        
        "in_slack": True,
        "is_returning": MembershipStatus.new,
        "is_national_member": True,
        
        "shirt_size": ShirtSize.m,
        
        "country_origin": ["Mexico"],
        "interested_industries": [Industry.electronics, Industry.cybersecurity],
        "prof_dev": [ProfDev.full_time, ProfDev.internships],
        "race_and_ethnicity": [RaceEthnicity.hispanic],
        
        "password": "TestPassword"
    }
    
    data.update(overrides)
    return data

def test_canary():
    assert True
    
def test_creates_valid_user():
    user = UserCreate(**valid_user_data())
    
    assert user.first_name == "John"
    assert user.last_name == "Doe"
    assert user.cougarnet_email == "abc@cougarnet.uh.edu"
    assert user.personal_email == "abc@gmail.com"
    assert user.birthday == date(2000, 1, 1)

def test_creates_user_with_invalid_personal_email():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            personal_email="abc"
        ))
        
def test_creates_user_with_invalid_cougarnet_email():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            cougarnet_email="abc"
        ))
        
def test_create_user_capitalized_email_are_normalized_and_lowered():
    user = UserCreate(**valid_user_data(
        cougarnet_email="TEST@COUGARNET.UH.EDU",
        personal_email="TEST@GMAIL.COM"
    ))
    
    assert user.cougarnet_email == "test@cougarnet.uh.edu"
    assert user.personal_email == "test@gmail.com"

def test_create_user_raises_error_when_non_uh_email_is_passed_cougarnet_email_field():
    with pytest.raises(ValidationError, match="CougarNet email must end with @cougarnet.uh.edu"):
        UserCreate(**valid_user_data(
            cougarnet_email="test@gmail.com"
        ))

def test_create_user_raises_error_when_cougarnet_email_is_passed_to_personal_email_field():
    with pytest.raises(ValidationError, match="Personal email cannot be a CougarNet or UH email address."):
        UserCreate(**valid_user_data(
            personal_email="test@cougarnet.uh.edu"
        ))
        
def test_create_user_raises_error_when_uh_email_is_passed_to_personal_email_field():
    with pytest.raises(ValidationError, match="Personal email cannot be a CougarNet or UH email address."):
        UserCreate(**valid_user_data(
            personal_email="test@uh.edu"
        ))
    
def test_create_user_does_not_allow_engineering_student_to_have_nsm_major():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            college=Colleges.engineering,
        ))

def test_create_user_does_not_allow_empty_major():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            college=Colleges.other,
            major=""
        ))

def test_create_user_allows_custom_major():
    user = UserCreate(**valid_user_data(
        college=Colleges.other,
        major="Graphic Design"
    ))
    
    assert user.college == Colleges.other
    assert user.major == "Graphic Design"

def test_create_user_allows_multiple_countries():
    user = UserCreate(**valid_user_data(
        country_origin = [
            "Mexico",
            "United States",
            "El Salvador"
        ]
    ))
    
    assert user.country_origin == [ "Mexico", "United States", "El Salvador" ]

def test_create_user_requires_one_country_origin():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            country_origin=[]
        ))

def test_create_user_requires_one_interested_industries():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            interested_industries=[]
        ))

def test_create_user_requires_one_prof_dev_option():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            prof_dev=[]
        ))

def test_create_user_requires_one_race_and_ethnicity_option():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            race_and_ethnicity=[]
        ))

def test_create_user_short_psid_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            psid="123"
        ))

def test_create_user_long_psid_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            psid="12345678"
        ))

def test_create_user_short_password_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            password="short"
        ))

def test_create_user_single_char_first_name_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            first_name="a"
        ))

def test_create_user_short_phone_num_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            phone_num="123"
        ))

def test_create_user_long_phone_num_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            phone_num="67676767676767676767676767676767676767676767676767676767"
        ))

def test_create_user_long_first_name_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            first_name="thisisareallylongnamewhichcontinuesforthelengthoftheentireuniverseidkhowmuchlongertotypethisfor"
        ))

def test_create_user_long_last_name_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            last_name="thisisareallylongnamewhichcontinuesforthelengthoftheentireuniverseidkhowmuchlongertotypethisfor"
        ))

def test_create_user_first_name_with_not_valid_char_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            first_name="John!"
        ))

def test_create_user_last_name_with_not_valid_char_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            first_name="Doe!"
        ))

def test_create_user_valid_first_names():
    user = UserCreate(**valid_user_data(first_name="Mary-Jane"))
    assert user.first_name == "Mary-Jane"

def test_create_user_first_name_with_apostrophe_is_valid():
    user = UserCreate(**valid_user_data(first_name="O'Brien"))
    assert user.first_name == "O'Brien"

def test_create_user_first_name_with_accent_is_valid():
    user = UserCreate(**valid_user_data(first_name="José"))
    assert user.first_name == "José"

def test_create_user_first_name_with_number_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(first_name="John2"))

def test_create_user_last_name_with_number_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(last_name="Doe2"))


def test_create_user_psid_with_letters_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(psid="123abc4"))

def test_create_user_valid_psid():
    user = UserCreate(**valid_user_data(psid="1234567"))
    assert user.psid == "1234567"


def test_create_user_phone_with_letters_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(phone_num="555-CALL"))

def test_create_user_phone_with_country_code_is_valid():
    user = UserCreate(**valid_user_data(phone_num="+1 (713) 555-1234"))
    assert user.phone_num == "+1 (713) 555-1234"

def test_create_user_phone_with_dashes_is_valid():
    user = UserCreate(**valid_user_data(phone_num="713-555-1234"))
    assert user.phone_num == "713-555-1234"

# US numbers only — the character check alone accepts 7-20 characters, so
# these pin the digit count. The signup form caps input at 10 digits; this is
# what makes that a rule rather than a client-side hint.

def test_create_user_phone_with_nine_digits_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(phone_num="713-555-123"))


def test_create_user_phone_with_eleven_digits_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(phone_num="713-555-12345"))


def test_create_user_phone_formatted_by_the_signup_form_is_valid():
    # Exactly what the frontend now submits.
    user = UserCreate(**valid_user_data(phone_num="(713) 555-1234"))
    assert user.phone_num == "(713) 555-1234"


def test_create_user_password_exactly_10_chars_is_valid():
    user = UserCreate(**valid_user_data(password="b7k2m9x4qz"))
    assert user.password == "b7k2m9x4qz"

def test_create_user_password_9_chars_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(password="b7k2m9x4q"))

def test_create_user_allows_engineering_major():
    user = UserCreate(**valid_user_data(
        college=Colleges.engineering,
        major="Computer Engineering"
    ))
    assert user.college == Colleges.engineering
    assert user.major == "Computer Engineering"

def test_create_user_allows_cot_major():
    user = UserCreate(**valid_user_data(
        college=Colleges.cot,
        major="Cybersecurity"
    ))
    assert user.college == Colleges.cot
    assert user.major == "Cybersecurity"

def test_create_user_cot_student_with_engineering_major_raises_error():
    with pytest.raises(ValidationError):
        UserCreate(**valid_user_data(
            college=Colleges.cot,
            major="Computer Engineering"
        ))