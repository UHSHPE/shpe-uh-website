import os

import limits
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

# The two upload routes (POST /me/resume, POST /shop/products/{id}/image).
# Generous for the same NAT reason as the rest: a resume workshop puts a room
# of members behind one campus IP. It can afford to be generous because it is
# no longer the primary control on upload size — BodyLimitMiddleware
# (services/body_limit.py) rejects an oversized body at the ASGI edge before
# the form parser runs. What's left for this limit to do is cap how many
# uploads one IP can have in flight at once, since each in-flight request
# holds a temp file until it completes.
UPLOAD_LIMIT = os.getenv("RATE_LIMIT_UPLOAD", "60/minute")


# Failed card charges only, checked and spent by POST /shop/orders.
#
# Separate from ORDER_LIMIT, and much tighter, because the two limits defend
# against different things. ORDER_LIMIT is sized for the NAT problem above (a
# dues drive is hundreds of members on one campus IP) and at 60/minute it is
# no obstacle at all to a card-testing loop: /shop/orders is anonymous, so
# anyone can tokenize a stolen card with the app id in our public frontend
# bundle and probe it against the chapter's live merchant account. What that
# costs us is per-chargeback fees and a fraud ratio that gets a small
# merchant's Square account frozen — i.e. no dues collection and no merch.
#
# This one can be tight *because a successful purchase never spends it* —
# only a decline does. A real buyer fumbling their card a couple of times
# never comes close, and even a NAT'd dues drive would need ten separate
# failed cards in ten minutes from one IP before anyone is turned away.
# Still env-tunable, so an event can loosen it without a deploy.
FAILED_CHARGE_LIMIT = os.getenv("RATE_LIMIT_FAILED_CHARGE", "10/10 minutes")
_failed_charge_item = limits.parse(FAILED_CHARGE_LIMIT)
_FAILED_CHARGE_KEY = "failed-charge"


def failed_charge_budget_exhausted(request: Request) -> bool:
    """True when this IP has already burned its failed-charge budget.

    Built on the limiter's own strategy object rather than a @limiter.limit
    decorator because that decorator counts *every* request to the route, and
    slowapi has no deduct_when. test() checks without consuming; only
    record_failed_charge() spends. Sharing the limiter's storage also means
    conftest's autouse limiter.reset() already isolates this between tests.
    """
    return not limiter.limiter.test(
        _failed_charge_item, _FAILED_CHARGE_KEY, client_ip(request)
    )


def record_failed_charge(request: Request) -> None:
    """Spend one unit of this IP's failed-charge budget."""
    limiter.limiter.hit(_failed_charge_item, _FAILED_CHARGE_KEY, client_ip(request))


def limit_count(limit: str) -> int:
    """The request count out of a "N/period" limit string, for tests."""
    return int(limit.split("/")[0])
