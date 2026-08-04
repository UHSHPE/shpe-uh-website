import os

from dotenv import load_dotenv
from slowapi import Limiter
from starlette.requests import Request

load_dotenv()


def _trust_proxy_headers() -> bool:
    # Read at call time (same pattern as square_services / drive_services) so
    # tests can flip it with monkeypatch.setenv without re-importing.
    raw = os.getenv("TRUST_PROXY_IP_HEADERS", "").strip().lower()
    return raw in ("1", "true", "yes")


def _proxy_hops() -> int:
    try:
        return max(1, int(os.getenv("TRUSTED_PROXY_HOPS", "1")))
    except ValueError:
        return 1


def client_ip(request: Request) -> str:
    """The real visitor IP, for rate-limit bucketing.

    slowapi's get_remote_address reads request.client.host. Behind any proxy
    that is the *proxy's* address — identical for every visitor — which
    silently collapses all four rate limits into one global bucket (i.e.
    five signups per hour for the whole chapter). Read X-Forwarded-For instead.

    We take the RIGHTMOST entry, not the leftmost. Each proxy appends the
    peer it received from, so the last entry is the one our own edge saw;
    the leftmost is whatever the client sent and is trivially spoofable.
    Rightmost is correct whether the platform appends or replaces the header.

    Off by default: local dev and the test suite have no trusted proxy in front,
    so they keep using the socket peer address and behave exactly as before.
    """
    if _trust_proxy_headers():
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            parts = [p.strip() for p in forwarded.split(",") if p.strip()]
            if parts:
                # -1 is the nearest proxy; a deeper chain (e.g. a CDN in front
                # of the platform edge) sets TRUSTED_PROXY_HOPS accordingly.
                return parts[-min(_proxy_hops(), len(parts))]
    return request.client.host if request.client else "127.0.0.1"


# Shared limiter instance. Lives here (not main.py) so route modules can
# import it without a circular import; main.py attaches it to app.state.
limiter = Limiter(key_func=client_ip)


# Per-IP limits, tunable without a code change.
#
# These are sized for a chapter event, not for a single user: at a GBM most
# attendees share one public IP behind campus NAT, so a limit tuned for one
# person starves the whole room (5/hour signup = five new members per hour
# for everyone on UH wifi combined). The controls that actually stop abuse
# are per-ACCOUNT and unaffected by NAT — email verification, the HIBP
# breached-password check, and the 10-attempt login lockout in auth_routes.
#
# Read at import because slowapi evaluates the decorator argument once.
LOGIN_LIMIT = os.getenv("RATE_LIMIT_LOGIN", "60/minute")
SIGNUP_LIMIT = os.getenv("RATE_LIMIT_SIGNUP", "60/hour")
ORDER_LIMIT = os.getenv("RATE_LIMIT_ORDER", "60/minute")
PASSWORD_RESET_LIMIT = os.getenv("RATE_LIMIT_PASSWORD_RESET", "20/hour")

# QR check-in is the extreme case of the NAT problem above: the whole point is
# that ~300 people scan within a couple of minutes, in one room, on one wifi
# network — i.e. every request arrives from a single IP. A per-person limit
# here doesn't throttle an attacker, it throttles the event.
#
# These can be generous because the endpoint's real guards are per-account and
# unaffected by NAT: /events/attend requires a valid JWT, and EventAttendance
# is keyed (user_id, event_id), so a repeat scan returns "already recorded"
# and awards no extra points (attendance_services.record_sign_in, which also
# catches the IntegrityError from two simultaneous scans racing). What's left
# for the limit to stop is a runaway client loop, so size it for a room.
ATTEND_LIMIT = os.getenv("RATE_LIMIT_ATTEND", "600/minute")
CODE_PREVIEW_LIMIT = os.getenv("RATE_LIMIT_CODE_PREVIEW", "600/minute")


def limit_count(limit: str) -> int:
    """The request count out of a "N/period" limit string, for tests."""
    return int(limit.split("/")[0])
