from pwdlib import PasswordHash

# Built once at import, not per call. PasswordHash.recommended() constructs a
# fresh argon2id hasher every time it runs, and login/signup are hot paths —
# at an event these are called hundreds of times in a burst. The hashing work
# itself is deliberately expensive (64 MiB, ~100 ms per verify); the setup
# around it should not be.
_password_hash = PasswordHash.recommended()

def get_password_hash(password: str):
    return _password_hash.hash(password)

def verify_password(password, hashed_password):
    return _password_hash.verify(password, hashed_password)
