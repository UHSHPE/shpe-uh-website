"""Breached-password check via the Have I Been Pwned range API (k-anonymity).

Only the first 5 chars of the password's SHA-1 hash leave the server — HIBP
returns every known suffix for that prefix and the match happens locally, so
the password itself (and even its full hash) is never sent anywhere.

FAIL OPEN by design: any network/HTTP error is logged and treated as
"not pwned" — an HIBP outage must never block signups or password resets.

Called from the two password-setting routes (POST /signup and
POST /password-reset/confirm) via asyncio.to_thread (httpx's sync client
would otherwise block the event loop). Routes reference it as a module
attribute (hibp_services.is_password_pwned) so tests can monkeypatch it —
the conftest autouse fixture disable_hibp_check stubs it to False so the
suite never hits the network.
"""
import hashlib
import logging

import httpx

HIBP_RANGE_URL = "https://api.pwnedpasswords.com/range/"
REQUEST_TIMEOUT_SECONDS = 3.0

logger = logging.getLogger(__name__)


def is_password_pwned(password: str) -> bool:
    """True if the password appears in HIBP's breached-password corpus."""
    sha1 = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = sha1[:5], sha1[5:]
    try:
        response = httpx.get(
            f"{HIBP_RANGE_URL}{prefix}",
            headers={
                "User-Agent": "shpe-uh-website",
                # Pads responses with count-0 dummy entries so response size
                # can't leak which prefix was queried.
                "Add-Padding": "true",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        for line in response.text.splitlines():
            found_suffix, _, count = line.partition(":")
            if found_suffix.strip() == suffix:
                try:
                    return int(count.strip()) > 0  # count 0 = padding entry
                except ValueError:
                    return False
        return False
    except Exception:
        # Fail open: HIBP being down must never block a signup/reset.
        logger.exception("HIBP breached-password check failed — allowing password")
        return False
