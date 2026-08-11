from pydantic import EmailStr, ValidationError, TypeAdapter
from fastapi import HTTPException, status

_email_adapter = TypeAdapter(EmailStr)

def normalize_email(value: str) -> str:
    try:
        # strip whitespace + lowercase + validate
        email: EmailStr = _email_adapter.validate_python(value.strip().lower())
        return str(email)
    except ValidationError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Invalid email format",
        )