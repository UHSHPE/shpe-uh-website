"""Load test: a room of members scanning an event QR at the same moment.

Not collected by pytest (no test_ prefix). Run it by hand, from backend/:

    .venv/bin/python tests/load/checkin_burst.py --users 300

It REBUILDS the shpe_test database (same drop_all/create_all the pytest suite
does), starts a real single-worker uvicorn against it on a spare port, fires
the bursts, and checks nobody was double-awarded. The dev database is never
touched. Rate limits are lifted so the numbers measure the server, not
slowapi; pass --real-limits to see what the shipped limits do to a room.
"""

import argparse
import asyncio
import os
import signal
import statistics
import subprocess
import sys
import tempfile
import time
from collections import Counter
from datetime import timedelta
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(BACKEND / "tests"))

TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://shpe:shpe_dev_password@localhost:5433/shpe_test",
)
# Before any app import: database.py binds its engine at import time.
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

import httpx  # noqa: E402
from sqlalchemy import delete, func, update  # noqa: E402
from sqlmodel import Session, SQLModel, create_engine, select  # noqa: E402

from conftest import make_event, make_user  # noqa: E402
from database import assert_local_database  # noqa: E402
from models.event_attendance import EventAttendance  # noqa: E402
from models.user.user import User  # noqa: E402
from security.hashing import get_password_hash  # noqa: E402
from security.jwt import create_access_token  # noqa: E402

PASSWORD = "load-test-password-1"
PORT = 8765
BASE = f"http://127.0.0.1:{PORT}"

# Blanked in the server's environment so its background jobs and email stay
# dev-mode no-ops whatever backend/.env holds. load_dotenv() never overrides a
# variable that is already set, even to "". Mirrors conftest's disable_* fixtures.
EXTERNAL_ENV = (
    "ENVIRONMENT", "ALLOWED_HOSTS", "TRUST_PROXY_IP_HEADERS", "SQL_ECHO",
    "SQUARE_ACCESS_TOKEN", "SQUARE_LOCATION_ID", "SQUARE_ENVIRONMENT",
    "GDRIVE_RESUME_FOLDER_ID", "GDRIVE_OAUTH_CLIENT_ID",
    "GDRIVE_OAUTH_CLIENT_SECRET", "GDRIVE_OAUTH_REFRESH_TOKEN",
    "CREDENTIALS", "SHEET_ID", "GOOGLE_SERVICE_ACCOUNT_JSON",
    "POINTS_OAUTH_CLIENT_ID", "POINTS_OAUTH_CLIENT_SECRET",
    "POINTS_OAUTH_REFRESH_TOKEN", "POINTS_SHEET_ID",
    "DUES_SHEET_ID", "DUES_TRACKER_CREDENTIALS", "SLACK_URL",
    "SMTP_HOST", "SMTP_PORT", "SMTP_USER", "SMTP_PASSWORD", "EMAIL_FROM",
)
RATE_LIMIT_ENV = (
    "RATE_LIMIT_LOGIN", "RATE_LIMIT_SIGNUP", "RATE_LIMIT_ATTEND",
    "RATE_LIMIT_CODE_PREVIEW",
)


def build_database(n_users: int):
    name = TEST_DATABASE_URL.rsplit("/", 1)[-1].split("?")[0]
    if not name.endswith("_test"):
        sys.exit(f"refusing to run against {name!r} — database name must end in _test")
    assert_local_database(TEST_DATABASE_URL)

    engine = create_engine(TEST_DATABASE_URL)
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)

    hashed = get_password_hash(PASSWORD)  # one real argon2 hash, shared
    with Session(engine) as s:
        emails = []
        for i in range(n_users):
            email = f"load{i}@cougarnet.uh.edu"
            make_user(
                s,
                cougarnet_email=email,
                personal_email=f"load{i}@gmail.com",
                psid=f"{9000000 + i}",
                hashed_password=hashed,
            )
            emails.append(email)
        event = make_event(
            s, title="GM Load Test", event_type="eboard", start_in=timedelta(0)
        )
        codes = (event.sign_in_code, event.sign_out_code)
    return engine, emails, codes


def reset_attendance(engine):
    with Session(engine) as s:
        s.exec(delete(EventAttendance))
        s.exec(update(User).values(points=0, failed_login_count=0, locked_until=None))
        s.commit()


def check_points(engine, n_users: int) -> list[str]:
    """Every member has exactly one row, and User.points equals what that row
    says they earned — the double-award check."""
    problems = []
    with Session(engine) as s:
        rows = s.exec(select(func.count()).select_from(EventAttendance)).one()
        if rows != n_users:
            problems.append(f"{rows} attendance rows for {n_users} members")
        mismatched = s.exec(
            select(func.count())
            .select_from(User)
            .join(EventAttendance, EventAttendance.user_id == User.id, isouter=True)
            .where(User.points != func.coalesce(EventAttendance.points_awarded, 0))
        ).one()
        if mismatched:
            problems.append(f"{mismatched} members whose points != their attendance row")
    return problems


def start_server(real_limits: bool):
    # faulthandler: a SIGABRT makes a hung server print every thread's stack.
    env = dict(os.environ, DATABASE_URL=TEST_DATABASE_URL, PYTHONFAULTHANDLER="1")
    for var in EXTERNAL_ENV:
        env[var] = ""
    if not real_limits:
        for var in RATE_LIMIT_ENV:
            env[var] = "1000000/minute"
    log = tempfile.NamedTemporaryFile("w+", suffix=".log", prefix="loadtest-", delete=False)
    # Same shape as the Dockerfile CMD: one worker.
    proc = subprocess.Popen(
        [sys.executable, "-m", "uvicorn", "main:app", "--host", "127.0.0.1",
         "--port", str(PORT), "--workers", "1", "--log-level", "warning"],
        cwd=BACKEND, env=env, stdout=log, stderr=subprocess.STDOUT,
    )
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            break
        try:
            httpx.get(f"{BASE}/events/code/not-a-code", timeout=1)
            return proc, log.name
        except httpx.TransportError:
            time.sleep(0.2)
    proc.kill()
    sys.exit(f"server did not start — see {log.name}")


class Recorder:
    def __init__(self):
        self.samples: dict[str, list[tuple[float, int]]] = {}

    async def call(self, label, request):
        start = time.perf_counter()
        try:
            status = (await request).status_code
        except httpx.HTTPError as exc:
            status = type(exc).__name__
        self.samples.setdefault(label, []).append((time.perf_counter() - start, status))
        return status

    def report(self) -> bool:
        ok = True
        for label, samples in self.samples.items():
            ms = sorted(t * 1000 for t, _ in samples)
            statuses = Counter(s for _, s in samples)
            p95 = ms[int(len(ms) * 0.95) - 1]
            print(
                f"  {label:<12} n={len(ms):<5} p50={statistics.median(ms):7.0f}ms "
                f"p95={p95:7.0f}ms max={ms[-1]:7.0f}ms  {dict(statuses)}"
            )
            if set(statuses) != {200}:
                ok = False
        return ok


def bearer(email: str) -> dict:
    token = create_access_token({"sub": email}, timedelta(hours=1))
    return {"Authorization": f"Bearer {token}"}


async def login(client, rec, email) -> dict | None:
    start = time.perf_counter()
    try:
        resp = await client.post("/login", data={"username": email, "password": PASSWORD})
        status = resp.status_code
    except httpx.HTTPError as exc:
        resp, status = None, type(exc).__name__
    rec.samples.setdefault("login", []).append((time.perf_counter() - start, status))
    if status != 200:
        return None
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def scan(client, rec, headers, code, taps=1):
    """What /attend/:code does: preview, then record. taps=2 is a double-tap."""
    await rec.call("preview", client.get(f"/events/code/{code}", headers=headers))
    await asyncio.gather(*(
        rec.call("attend", client.post("/events/attend", json={"code": code}, headers=headers))
        for _ in range(taps)
    ))


async def member(client, rec, email, code, *, cold, delay, taps=1):
    await asyncio.sleep(delay)
    headers = await login(client, rec, email) if cold else bearer(email)
    if headers:
        await scan(client, rec, headers, code, taps)


async def run_scenario(name, engine, emails, code, spread, *, cold, taps=1, reset=True):
    """cold(i) -> whether member i arrives logged out."""
    if reset:
        reset_attendance(engine)
    rec = Recorder()
    limits = httpx.Limits(max_connections=None, max_keepalive_connections=None)
    async with httpx.AsyncClient(base_url=BASE, timeout=90, limits=limits) as client:
        start = time.perf_counter()
        await asyncio.gather(*(
            member(client, rec, email, code, cold=cold(i),
                   delay=spread * i / len(emails), taps=taps)
            for i, email in enumerate(emails)
        ))
        wall = time.perf_counter() - start
    print(f"\n{name}  ({len(emails)} members over {spread:g}s, finished in {wall:.1f}s)")
    ok = rec.report()
    for problem in check_points(engine, len(emails)):
        print(f"  POINTS MISMATCH: {problem}")
        ok = False
    return ok


async def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--users", type=int, default=300)
    parser.add_argument("--spread", type=float, default=0,
                        help="seconds the arrivals are spread over (0 = all at once)")
    parser.add_argument("--real-limits", action="store_true",
                        help="keep the shipped rate limits instead of lifting them")
    args = parser.parse_args()

    engine, emails, (sign_in, sign_out) = build_database(args.users)
    proc, log_path = start_server(args.real_limits)
    print(f"server log: {log_path}")
    try:
        results = [
            await run_scenario("Sign-in, everyone already logged in, double-tap",
                               engine, emails, sign_in, args.spread,
                               cold=lambda i: False, taps=2),
            await run_scenario("Sign-out, same room", engine, emails, sign_out,
                               args.spread, cold=lambda i: False, taps=2, reset=False),
            await run_scenario("Sign-in, everyone logged out (login first)",
                               engine, emails, sign_in, args.spread,
                               cold=lambda i: True),
            await run_scenario("Sign-in, half logged out (logins racing scans)",
                               engine, emails, sign_in, args.spread,
                               cold=lambda i: i % 2 == 0),
        ]
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.send_signal(signal.SIGABRT)
            proc.wait(timeout=10)
            print(f"\nSERVER HUNG — thread stacks dumped to {log_path}")
    print("\nPASS" if all(results) else "\nFAIL — see non-200 statuses or mismatches above")
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    asyncio.run(main())
