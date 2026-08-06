import re
from sqlmodel import SQLModel, Field
from pydantic import EmailStr, field_validator, model_validator
from datetime import date, datetime
from .user_enums import Industry, ProfDev, RaceEthnicity, Role, Classification, Colleges, COTMajors, ExpGradDate, EngineerMajors, Gender, GPA, MembershipStatus, NSMMajors, ShirtSize

_SAFE_NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ' \-]{2,50}$")
_PSID_RE = re.compile(r"^\d{7}$")
_PHONE_RE = re.compile(r"^[\d\s\(\)\-\+\.]{7,20}$")

MIN_PASSWORD_LENGTH = 10
# NIST 800-63B: allow long passphrases; the cap only bounds Argon2 hashing cost.
MAX_PASSWORD_LENGTH = 128


def validate_password_strength(v: str) -> str:
    """Shared password rule — used by UserCreate and the password-reset confirm
    endpoint. Policy is length only (NIST 800-63B): no composition rules, no
    expiry. This validator must stay pure/sync (pydantic runs it during request
    parsing) — the breached-password check lives in the routes instead
    (services/hibp_services.py). The frontend length checks in signup.jsx
    and reset-password.jsx must stay in sync with MIN_PASSWORD_LENGTH."""
    if len(v) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"Password must be at least {MIN_PASSWORD_LENGTH} characters.")
    if len(v) > MAX_PASSWORD_LENGTH:
        raise ValueError(f"Password must be {MAX_PASSWORD_LENGTH} characters or fewer.")
    return v

class UserBase(SQLModel):
    first_name: str
    last_name: str

    cougarnet_email: EmailStr = Field(index=True, unique=True)
    personal_email: EmailStr = Field(index=True, unique=True)

    phone_num: str
    psid: str = Field(index=True, unique=True)
    birthday: date

    gender: Gender
    first_gen: bool

    college: Colleges
    major: str
    classification: Classification
    gpa: GPA | None = None
    exp_grad_date: ExpGradDate

    in_slack: bool
    is_returning: MembershipStatus
    is_national_member: bool

    shirt_size: ShirtSize

    @field_validator("first_name", "last_name", mode="before")
    @classmethod
    def validate_name(cls, v: str) -> str:
        v = str(v).strip()
        if not _SAFE_NAME_RE.match(v):
            raise ValueError("Name must be 2–50 letters and may only contain letters, hyphens, apostrophes, or spaces.")
        return v

    @field_validator("cougarnet_email", mode="before")
    @classmethod
    def validate_cougarnet_email(cls, v: str) -> str:
        v = str(v).lower()
        
        if not v.endswith("@cougarnet.uh.edu"):
            raise ValueError("CougarNet email must end with @cougarnet.uh.edu.")
        
        return v

    @field_validator("personal_email", mode="before")
    @classmethod
    def validate_personal_email(cls, v: str) -> str:
        v = str(v).lower()
        
        if v.endswith("@cougarnet.uh.edu") or v.endswith("@uh.edu"):
            raise ValueError("Personal email cannot be a CougarNet or UH email address.")
        
        return v

    @field_validator("psid", mode="before")
    @classmethod
    def validate_psid(cls, v: str) -> str:
        v = str(v).strip()
        if not _PSID_RE.match(v):
            raise ValueError("PSID must be exactly 7 digits.")
        return v

    @field_validator("phone_num", mode="before")
    @classmethod
    def validate_phone(cls, v: str) -> str:
        v = str(v).strip()
        if not v:
            raise ValueError("Phone number is required.")
        if not _PHONE_RE.match(v):
            raise ValueError("Phone number contains invalid characters.")
        # US numbers only. The character check above still lets through 7 or 20
        # digits, so count them: the signup form formats to (555) 555-5555 and
        # caps at 10, and this is what makes that a rule rather than a hint.
        digits = re.sub(r"\D", "", v)
        if digits.startswith("1") and len(digits) == 11:
            digits = digits[1:]          # tolerate a leading US country code
        if len(digits) != 10:
            raise ValueError("Phone number must be 10 digits.")
        return v

    @field_validator("major", mode="before")
    @classmethod
    def sanitize_major(cls, v: str) -> str:
        v = str(v).strip()
        if len(v) > 100:
            raise ValueError("Major name is too long.")
        return v

    @model_validator(mode="after")
    def check_major_matches_college(self):
        valid = {
            Colleges.engineering: EngineerMajors,
            Colleges.nsm: NSMMajors,
            Colleges.cot: COTMajors,
        }.get(self.college)

        if valid is None:
            if not self.major.strip():
                raise ValueError("Major is required.")
        elif self.major not in (m.value for m in valid):
            raise ValueError("Major doesn't match selected college.")

        return self


class UserMultiSelectedFields(SQLModel):
    country_origin: list[str]
    interested_industries: list[Industry]
    prof_dev: list[ProfDev]
    race_and_ethnicity: list[RaceEthnicity]

    @field_validator("country_origin", mode="before")
    @classmethod
    def sanitize_countries(cls, v: list) -> list:
        if not v:
            raise ValueError("Please enter one country of origin")
        
        cleaned = []
        for item in v:
            s = str(item).strip()[:100]
            if s:
                cleaned.append(s)
        return cleaned

    @field_validator("race_and_ethnicity", mode="before")
    @classmethod
    def require_race(cls, v: list) -> list:
        if not v:
            raise ValueError("Please select at least one race/ethnicity option.")
        return v

    @field_validator("interested_industries", mode="before")
    @classmethod
    def require_industries(cls, v: list) -> list:
        if not v:
            raise ValueError("Please select at least one interested industry.")
        return v

    @field_validator("prof_dev", mode="before")
    @classmethod
    def require_prof_dev(cls, v: list) -> list:
        if not v:
            raise ValueError("Please select at least one professional development interest.")
        return v


class UserCreate(UserBase, UserMultiSelectedFields):
    password: str

    @field_validator("password", mode="before")
    @classmethod
    def validate_password(cls, v: str) -> str:
        return validate_password_strength(str(v))


class UserOut(UserBase, UserMultiSelectedFields):
    id: int
    role: Role
    points: int
    resume_filename: str | None = None
    # Computed in /me (not a DB column): True when the user has a
    # non-cancelled order containing the dues product. Drives the frontend
    # dues banner and the product page's "already paid" state.
    has_paid_dues: bool = False


class AdminMemberOut(SQLModel):
    """Row in the president's member directory (/admin/members) — just the
    fields the members page lists and filters on, no multi-select rows."""
    id: int
    first_name: str
    last_name: str
    cougarnet_email: str
    personal_email: str
    phone_num: str
    psid: str
    role: Role
    points: int
    classification: Classification
    college: Colleges
    major: str
    shirt_size: ShirtSize
    is_national_member: bool
    has_paid_dues: bool = False


class AdminRoleUpdate(SQLModel):
    role: Role


class AdminStatsOut(SQLModel):
    """Chapter-wide numbers for the president's members page."""
    total_accounts: int
    dues_paid: int
    dues_unpaid: int
    national_members: int
    # Start of the current membership year (dues reset every May 30) — lets
    # the UI say what period the paid/unpaid split covers.
    dues_period_start: datetime
    classification_counts: dict[str, int]
    role_counts: dict[str, int]
    shirt_size_counts: dict[str, int]
