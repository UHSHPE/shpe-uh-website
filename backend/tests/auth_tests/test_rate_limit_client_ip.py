"""client_ip() decides which bucket a rate-limited request counts against.

Behind a proxy, request.client.host is the proxy's address — the same for
every visitor — which silently turns all four per-IP limits into one global
bucket. These tests pin down the header parsing that avoids that, and the
default-off behavior that keeps local dev and the rest of the suite unchanged.
"""
from starlette.requests import Request

from services.rate_limit import client_ip


def make_request(headers=None, client_host="10.0.0.1"):
    raw = [
        (k.lower().encode(), v.encode())
        for k, v in (headers or {}).items()
    ]
    scope = {
        "type": "http",
        "headers": raw,
        "client": (client_host, 12345) if client_host else None,
    }
    return Request(scope)


def test_ignores_forwarded_header_by_default(monkeypatch):
    # Unset: no trusted proxy, so the socket peer wins. This is what keeps
    # local dev and every other test behaving exactly as before.
    monkeypatch.delenv("TRUST_PROXY_IP_HEADERS", raising=False)
    req = make_request({"X-Forwarded-For": "203.0.113.9"}, client_host="10.0.0.1")

    assert client_ip(req) == "10.0.0.1"


def test_uses_forwarded_header_when_trusted(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_IP_HEADERS", "1")
    req = make_request({"X-Forwarded-For": "203.0.113.9"}, client_host="10.0.0.1")

    assert client_ip(req) == "203.0.113.9"


def test_takes_rightmost_entry_not_leftmost(monkeypatch):
    """The security-critical case.

    A client can put anything in X-Forwarded-For; the proxy appends the peer
    it actually saw. Taking the leftmost entry would let an attacker mint a
    fresh rate-limit bucket per request by spoofing the header.
    """
    monkeypatch.setenv("TRUST_PROXY_IP_HEADERS", "1")
    spoofed = "1.2.3.4, 5.6.7.8, 198.51.100.7"
    req = make_request({"X-Forwarded-For": spoofed}, client_host="10.0.0.1")

    assert client_ip(req) == "198.51.100.7"


def test_deeper_proxy_chain_honours_hop_count(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_IP_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "2")
    req = make_request({"X-Forwarded-For": "1.2.3.4, 198.51.100.7, 10.0.0.2"})

    assert client_ip(req) == "198.51.100.7"


def test_hop_count_clamped_to_available_entries(monkeypatch):
    # A misconfigured hop count must not IndexError or fall off the front.
    monkeypatch.setenv("TRUST_PROXY_IP_HEADERS", "1")
    monkeypatch.setenv("TRUSTED_PROXY_HOPS", "9")
    req = make_request({"X-Forwarded-For": "203.0.113.9"})

    assert client_ip(req) == "203.0.113.9"


def test_falls_back_to_peer_when_header_absent(monkeypatch):
    monkeypatch.setenv("TRUST_PROXY_IP_HEADERS", "1")
    req = make_request({}, client_host="10.0.0.5")

    assert client_ip(req) == "10.0.0.5"


def test_survives_missing_client(monkeypatch):
    monkeypatch.delenv("TRUST_PROXY_IP_HEADERS", raising=False)
    req = make_request({}, client_host=None)

    assert client_ip(req) == "127.0.0.1"
