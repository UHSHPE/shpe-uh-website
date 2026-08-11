import os
import smtplib
from email.message import EmailMessage

from dotenv import load_dotenv

load_dotenv()


def send_email(to: str, subject: str, body: str) -> bool:
    """Send an email via SMTP. Without SMTP_HOST configured (dev mode),
    prints the email to the console instead. Returns True on success."""
    host = os.getenv("SMTP_HOST")

    if not host:
        print(f"[email dev mode] To: {to} | Subject: {subject}\n{body}")
        return True

    port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_password = os.getenv("SMTP_PASSWORD")
    sender = os.getenv("EMAIL_FROM", smtp_user)

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
        return False
