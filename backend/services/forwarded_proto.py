"""Restores the original request scheme from X-Forwarded-Proto.

Behind Railway (or any TLS-terminating proxy) the connection uvicorn actually
accepts is plain http, so scope["scheme"] is "http" and every absolute URL the
app builds comes out as http:// — most visibly FastAPI's trailing-slash
redirects. A browser on an https:// page blocks that redirect as mixed content
*before the request is sent*, so the frontend sees an opaque network error
rather than a redirect it can follow. That is invisible to curl (no
mixed-content rule) and to the test suite (no proxy, no TLS), which is what
let it reach production.

Why not uvicorn's --forwarded-allow-ips=*, which also fixes the scheme:
it additionally rewrites scope["client"] from the LEFTMOST X-Forwarded-For
entry, which is client-supplied and trivially spoofed. rate_limit.client_ip
deliberately ignores scope["client"] and parses the header itself from the
RIGHTMOST entry for exactly that reason -- but it still falls back to
scope["client"] when the trust flag is off or the header is absent. Enabling
uvicorn's version would turn that fallback from "every visitor shares the
proxy's bucket" (too strict, fails closed) into "the caller names their own
bucket by sending a header" (no limit at all, fails open). Fixing only the
scheme here leaves client_ip the single authority on IPs.
"""

from starlette.datastructures import Headers

from services.rate_limit import trust_proxy_headers

# A scheme we would ever want to adopt. Anything else (a typo, an injected
# value) is ignored rather than written into scope, where it would silently
# corrupt every generated URL.
_VALID_SCHEMES = ("http", "https")


class ForwardedProtoMiddleware:
    """Pure ASGI middleware -- it only edits the scope and never reads or
    writes the body, so there is nothing to gain from BaseHTTPMiddleware
    (which would buffer the request for no reason).

    Gated on the same TRUST_PROXY_IP_HEADERS flag as client_ip, because it
    answers the same question: is there a proxy in front whose forwarded
    headers we may believe? Off by default, so local dev and the test suite
    keep the real socket scheme and behave exactly as before.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and trust_proxy_headers():
            forwarded = Headers(scope=scope).get("x-forwarded-proto")
            if forwarded:
                # Rightmost = the value our own edge set, same reasoning as
                # client_ip's rightmost X-Forwarded-For entry. Anything to the
                # left of it was supplied further out and may be the client's.
                parts = [p.strip().lower() for p in forwarded.split(",")]
                candidate = next((p for p in reversed(parts) if p), "")
                if candidate in _VALID_SCHEMES:
                    scope["scheme"] = candidate
        await self.app(scope, receive, send)
