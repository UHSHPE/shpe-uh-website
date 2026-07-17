import logging
import os
import uuid
from typing import NamedTuple

from dotenv import load_dotenv

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

# Buyer-fixable decline codes → messages safe to show at checkout. Anything
# else gets a generic message (and a logged traceback for the managers).
_DECLINE_MESSAGES = {
    "CARD_DECLINED": "Your card was declined. Try another card.",
    "GENERIC_DECLINE": "Your card was declined. Try another card.",
    "INSUFFICIENT_FUNDS": "The card was declined for insufficient funds.",
    "CVV_FAILURE": "The security code (CVC) didn't match. Check it and try again.",
    "ADDRESS_VERIFICATION_FAILURE": "The ZIP code didn't match the card. Check it and try again.",
    "INVALID_CARD": "The card number is invalid. Check it and try again.",
    "INVALID_EXPIRATION": "The card's expiration date is invalid.",
    "EXPIRATION_FAILURE": "The card's expiration date is invalid or past.",
}

_GENERIC_MESSAGE = "Payment could not be completed. Please try again."


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
        if os.getenv("SQUARE_ENVIRONMENT", "sandbox").strip().lower() == "production"
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
            raise PaymentError(_GENERIC_MESSAGE)
        return ChargeResult(payment.id, getattr(payment, "receipt_url", None))
    except PaymentError:
        raise
    except ApiError as exc:
        code = _first_error_code(exc)
        message = _DECLINE_MESSAGES.get(code)
        if message is None:
            logging.exception("Square charge failed (code=%s) for %s", code, buyer_email)
            message = _GENERIC_MESSAGE
        raise PaymentError(message) from exc
    except Exception as exc:
        logging.exception("Square charge failed for %s", buyer_email)
        raise PaymentError(_GENERIC_MESSAGE) from exc
