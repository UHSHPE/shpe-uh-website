import smtplib

import services.email_services as email_services
from services.email_services import send_email


def test_canary():
    assert True


def _clear_smtp_env(monkeypatch):
    for var in (
        "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD",
        "EMAIL_FROM", "SMTP_TIMEOUT",
    ):
        monkeypatch.delenv(var, raising=False)


class FakeSMTP:
    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.tls_started = False
        self.logins = []
        self.sent_messages = []
        FakeSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.tls_started = True

    def login(self, user, password):
        self.logins.append((user, password))

    def send_message(self, msg):
        self.sent_messages.append(msg)


def test_without_smtp_config_prints_to_console_and_returns_true(monkeypatch, capsys):
    _clear_smtp_env(monkeypatch)

    ok = send_email("member@gmail.com", "Test subject", "Test body")

    assert ok is True
    output = capsys.readouterr().out
    assert "member@gmail.com" in output
    assert "Test subject" in output

def test_with_smtp_config_sends_message(monkeypatch):
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_PORT", "587")
    monkeypatch.setenv("SMTP_USER", "bot@shpeuh.org")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    FakeSMTP.instances.clear()
    monkeypatch.setattr(email_services.smtplib, "SMTP", FakeSMTP)

    ok = send_email("member@gmail.com", "Reminder", "Event coming up")

    assert ok is True
    assert len(FakeSMTP.instances) == 1
    smtp = FakeSMTP.instances[0]
    assert smtp.host == "smtp.test.com"
    assert smtp.port == 587
    assert smtp.tls_started is True
    assert smtp.logins == [("bot@shpeuh.org", "app-password")]

    assert len(smtp.sent_messages) == 1
    msg = smtp.sent_messages[0]
    assert msg["To"] == "member@gmail.com"
    assert msg["Subject"] == "Reminder"
    assert "Event coming up" in msg.get_content()

def test_smtp_always_gets_a_timeout(monkeypatch):
    """smtplib defaults to no timeout, i.e. an infinite socket wait. Every
    send_email caller is either an async handler (where a hang freezes the
    whole event loop) or a background loop, so the timeout must never be None."""
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    FakeSMTP.instances.clear()
    monkeypatch.setattr(email_services.smtplib, "SMTP", FakeSMTP)

    send_email("member@gmail.com", "Reminder", "Event coming up")

    assert FakeSMTP.instances[0].timeout == 10.0

def test_smtp_timeout_is_configurable(monkeypatch):
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_TIMEOUT", "3.5")
    FakeSMTP.instances.clear()
    monkeypatch.setattr(email_services.smtplib, "SMTP", FakeSMTP)

    send_email("member@gmail.com", "Reminder", "Event coming up")

    assert FakeSMTP.instances[0].timeout == 3.5

def test_from_defaults_to_smtp_user(monkeypatch):
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_USER", "bot@shpeuh.org")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    FakeSMTP.instances.clear()
    monkeypatch.setattr(email_services.smtplib, "SMTP", FakeSMTP)

    send_email("member@gmail.com", "Reminder", "Body")

    assert FakeSMTP.instances[0].sent_messages[0]["From"] == "bot@shpeuh.org"

def test_email_from_env_overrides_sender(monkeypatch):
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")
    monkeypatch.setenv("SMTP_USER", "bot@shpeuh.org")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    monkeypatch.setenv("EMAIL_FROM", "SHPE UH <noreply@shpeuh.org>")
    FakeSMTP.instances.clear()
    monkeypatch.setattr(email_services.smtplib, "SMTP", FakeSMTP)

    send_email("member@gmail.com", "Reminder", "Body")

    assert FakeSMTP.instances[0].sent_messages[0]["From"] == "SHPE UH <noreply@shpeuh.org>"

def test_smtp_failure_returns_false(monkeypatch):
    _clear_smtp_env(monkeypatch)
    monkeypatch.setenv("SMTP_HOST", "smtp.test.com")

    class BoomSMTP:
        def __init__(self, *args, **kwargs):
            raise smtplib.SMTPException("connection refused")

    monkeypatch.setattr(email_services.smtplib, "SMTP", BoomSMTP)

    assert send_email("member@gmail.com", "Reminder", "Body") is False
