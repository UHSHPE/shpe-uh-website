import logging
import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via SMTP. Without SMTP_HOST configured (dev mode),
    prints the email to the console instead. Returns True on success.

    Every failure is logged. It used to return False silently, which was
    indistinguishable from dev mode from the outside: signup discarded the
    result and told the member to check an inbox nothing was ever sent to.
    The log line is the only place a misconfigured relay becomes visible.
    """
    host = os.getenv("SMTP_HOST")

    if not host:
        print(f"[email dev mode] To: {to} | Subject: {subject}\n{body}")
        return True

    port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("EMAIL_FROM", smtp_user)

    # Falling back to SMTP_USER only works when that happens to BE an address,
    # which is true for Gmail and false for API-key relays: Resend's SMTP
    # username is the literal string "resend". Without this check the From
    # header is that bare word, the relay rejects the message, and the only
    # symptom is mail that never arrives. Checked before connecting so the
    # error names the cause instead of surfacing as a generic SMTP failure.
    if not sender or "@" not in sender:
        logger.error(
            "Refusing to send: From address %r is not an email address. Set "
            "EMAIL_FROM explicitly — it defaults to SMTP_USER, which is not "
            "an address for API-key relays such as Resend.",
            sender,
        )
        return False

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    # Without an explicit timeout the socket blocks forever, so one
    # unresponsive SMTP host hangs the request that triggered it — and, if
    # that request is on the event loop, the whole server with it.
    timeout = float(os.getenv("SMTP_TIMEOUT", "10"))

    try:
        with smtplib.SMTP(host, port, timeout=timeout) as smtp:
            smtp.starttls()
            if smtp_user and smtp_password:
                smtp.login(smtp_user, smtp_password)
            smtp.send_message(msg)
        return True
    except (smtplib.SMTPException, OSError):
        # exception() so the traceback reaches the platform logs — with an
        # API-key relay the useful detail (bad key, unverified sender domain,
        # wrong port) is in the server's reply, not in anything we can infer.
        logger.exception(
            "SMTP send failed: host=%s port=%s from=%s to=%s", host, port, sender, to
        )
        return False
