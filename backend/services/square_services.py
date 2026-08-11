import logging
import os
import uuid
from typing import NamedTuple

from dotenv import load_dotenv

from config import is_production, square_is_production

load_dotenv()


class ChargeResult(NamedTuple):
    """A successful Square charge: the payment id we store on the order, and
    Square's hosted receipt link (emailed to the buyer; can be None)."""

    payment_id: str
    receipt_url: str | None


# Square card payments for the shop. Requires both env vars:
#
#   SQUARE_ACCESS_TOKEN   (secret — from developer.squareup.com)
#   SQUARE_LOCATION_ID
#
# plus optional SQUARE_ENVIRONMENT ("sandbox" | "production", default sandbox).
#
# The frontend tokenizes the card with the Square Web Payments SDK (card data
# never touches this server) and sends the one-time token; charge_card() turns
# that token into a real charge via the Payments API. The charge response is
# synchronous — no webhooks needed.
#
# Without config (dev mode), charge_card is a console-printing no-op — same
# pattern as email_services.py — so local dev and tests never hit the network
# and checkout behaves like the old simulated flow.

# Codes meaning Square processed the card and refused. This is a SET, not a
# code→message map, and that is the whole point: membership picks one of two
# messages, and every member picks the same one, so the 402 body carries no
# per-code signal. POST /shop/orders is anonymous by design, so a map that
# distinguished "card number is invalid" from "CVC didn't match" from "ZIP
# didn't match" let anyone sort a stolen-card list against the chapter's live
# merchant account — see the F4 note in CLAUDE.md before changing this.
#
# Anything outside this set is our problem rather than the card's (a Square
# outage, an UNAUTHORIZED token) and gets _GENERIC_MESSAGE plus a traceback.
# Kept to exactly the codes that used to have their own message — every other
# code already fell through to the generic one. If a log shows a real decline
# landing in the generic bucket (CARD_EXPIRED, PAN_FAILURE, CARD_TOKEN_EXPIRED)
# add it here; it costs nothing, since they all read the same to the buyer.
_DECLINE_CODES = frozenset({
    "CARD_DECLINED",
    "GENERIC_DECLINE",
    "INSUFFICIENT_FUNDS",
    "CVV_FAILURE",
    "ADDRESS_VERIFICATION_FAILURE",
    "INVALID_CARD",
    "INVALID_EXPIRATION",
    "EXPIRATION_FAILURE",
})

_DECLINED_MESSAGE = "Your card was declined, check your details and try again."
_GENERIC_MESSAGE = "Payment could not be completed. Please try again."


def _buyer_message(code: str | None) -> str:
    """The 402 body for a Square error code. Two outcomes only — see
    _DECLINE_CODES for why this must never grow a third."""
    return _DECLINED_MESSAGE if code in _DECLINE_CODES else _GENERIC_MESSAGE


class PaymentError(Exception):
    """Charge was declined or failed — str(exc) is safe to show the buyer.
    The caller must NOT create the order when this is raised."""


def is_configured() -> bool:
    """True when Square credentials are set (read at call time, like GDRIVE_*)."""
    return bool(os.getenv("SQUARE_ACCESS_TOKEN") and os.getenv("SQUARE_LOCATION_ID"))


def _square_client():
    """Return (client, location_id), or None when Square is unconfigured."""
    token = os.getenv("SQUARE_ACCESS_TOKEN")
    location_id = os.getenv("SQUARE_LOCATION_ID")
    if not (token and location_id):
        return None

    # Imported lazily so dev mode works even without the squareup package.
    from square import Square
    from square.environment import SquareEnvironment

    environment = (
        SquareEnvironment.PRODUCTION
        if square_is_production()
        else SquareEnvironment.SANDBOX
    )
    return Square(token=token, environment=environment), location_id


def _first_error_code(exc) -> str | None:
    """Pull the first Square error code out of an ApiError body, defensively."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        errors = body.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            return errors[0].get("code")
    return None


def _create_itemized_order(client, location_id: str, line_items: list[dict]) -> str | None:
    """Create a Square order carrying our line items so the charge shows up
    itemized in the Square Dashboard ("2× Quarter-Zip (M)"), and item names
    flow into Square's sales reports. Best-effort: itemization is reporting
    sugar — on failure we log and charge un-itemized rather than block the
    buyer. Each item dict: {"name", "quantity", "unit_price_cents"}."""
    try:
        result = client.orders.create(
            order={
                "location_id": location_id,
                "line_items": [
                    {
                        "name": item["name"],
                        "quantity": str(item["quantity"]),  # Orders API wants a string
                        "base_price_money": {
                            "amount": item["unit_price_cents"],
                            "currency": "USD",
                        },
                    }
                    for item in line_items
                ],
            },
            idempotency_key=str(uuid.uuid4()),
        )
        return result.order.id
    except Exception:
        logging.exception("Square itemized order failed — charging without itemization")
        return None


def charge_card(
    payment_token: str | None,
    amount_cents: int,
    buyer_email: str,
    note: str,
    line_items: list[dict] | None = None,
) -> ChargeResult | None:
    """Charge a card token from the Web Payments SDK; return a ChargeResult
    (payment id + hosted receipt link).

    When line_items is given, the payment is attached to an itemized Square
    order (see _create_itemized_order) — the line items must sum to
    amount_cents or Square rejects the payment. Dev mode (unconfigured)
    prints and returns None — the order proceeds as a simulated purchase.
    Raises PaymentError (buyer-safe message) when the charge is declined or
    fails; the idempotency key is fresh per attempt, so a retried request can
    never double-charge within one call."""
    config = _square_client()
    if config is None:
        if is_production():
            raise RuntimeError("ENVIRONMENT=production but Square is not configured "
                               "(SQUARE_ACCESS_TOKEN / SQUARE_LOCATION_ID missing) — refusing to simulate a charge.")
        summary = ", ".join(
            f"{i['quantity']}× {i['name']}" for i in (line_items or [])
        ) or "no items"
        print(f"[square dev mode] would charge {amount_cents} cents for {buyer_email} ({summary})")
        return None

    client, location_id = config
    from square.core.api_error import ApiError

    square_order_id = None
    if line_items:
        square_order_id = _create_itemized_order(client, location_id, line_items)

    try:
        result = client.payments.create(
            source_id=payment_token,
            idempotency_key=str(uuid.uuid4()),
            amount_money={"amount": amount_cents, "currency": "USD"},
            location_id=location_id,
            order_id=square_order_id,
            buyer_email_address=buyer_email,
            note=note,
        )
        payment = result.payment
        if payment is None or payment.id is None:
            logging.error("Square returned no payment object for %s", buyer_email)
            raise PaymentError(_GENERIC_MESSAGE)
        return ChargeResult(payment.id, getattr(payment, "receipt_url", None))
    except PaymentError:
        raise
    except ApiError as exc:
        # The buyer sees one string; the specific code lives here, so a member
        # who calls asking why their card failed can still be answered.
        code = _first_error_code(exc)
        if code in _DECLINE_CODES:
            # Routine — a traceback per declined card is noise, not signal.
            logging.warning("Square declined charge (code=%s) for %s", code, buyer_email)
        else:
            logging.exception("Square charge failed (code=%s) for %s", code, buyer_email)
        raise PaymentError(_buyer_message(code)) from exc
    except Exception as exc:
        logging.exception("Square charge failed for %s", buyer_email)
        raise PaymentError(_GENERIC_MESSAGE) from exc
