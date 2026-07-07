import secrets, hashlib

def hash_reset_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def generate_reset_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_reset_token(raw)
