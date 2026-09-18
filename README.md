# SHPE UH Website

## The membership, events, and merch platform for SHPE at the University of Houston

This is the website for the **Society of Hispanic Professional Engineers** chapter at the
University of Houston — [www.shpeuh.com](https://www.shpeuh.com). It's the chapter's public face
and its internal operations tool in one application.

Members sign up with their CougarNet email, pay chapter dues, browse and join committees, check
into events by scanning a QR code at the door, and buy chapter merch. Chairs run their committees
from it: rosters, broadcasts, attendance, and per-event statistics. The E-Board runs the chapter
from it: role assignment, the org chart, dues tracking, and the storefront. Events come from the
Google Sheet officers already maintain, so nobody has to add an event twice.

It's a React single-page app on a FastAPI backend with PostgreSQL. **New to the chapter or to the
codebase? Start with the [glossary](docs/glossary.md)** — the code is full of chapter terms that
aren't guessable.

### What it does

- **Membership** — signup with email verification, $20 chapter dues that reset each May 30, member
  profiles, and a resume upload that syncs to the chapter's Resume Book on Google Drive
- **Events** — a public calendar that populates itself from the chapter's event-tracker sheet,
  email reminders, and QR sign-in/sign-out at the door that awards points by event pillar
- **Committees** — browse, join, and leave; chairs get rosters and broadcast messages
- **Merch shop** — public storefront with real card, Apple Pay, and Google Pay checkout through
  Square, and in-person pickup at chapter events
- **Chapter admin** — the president and both VPs get a members directory, chapter statistics, role
  assignment, and an editable org chart

The full feature reference is in [docs/features.md](docs/features.md).

## Getting started

You'll need:

- **Node.js** v18+ and npm
- **Python** 3.11+
- **Docker Desktop** (or another Docker runtime) — runs the PostgreSQL database
- **Git**

Budget about 15 minutes the first time. Each step below ends with a way to check it worked —
don't skip those, because two of these failures only show up much later.

### 1. Clone the repository

```bash
git clone https://github.com/UHSHPE/shpe-uh-website.git
cd shpe-uh-website
```

### 2. Start the database

```bash
docker compose up -d --wait
docker compose exec db createdb -U shpe shpe_test   # one-time: creates the test database
```

This starts PostgreSQL 17 in Docker on `localhost:5433` (see `docker-compose.yml`). The main
`shpe` database is created by the container automatically; `shpe_test`, used only by the test
suite, needs that one-time `createdb`.

`--wait` holds until the container reports healthy. Without it, `createdb` can run before Postgres
finishes initializing and fail with `connection to server on socket ... No such file or directory`
— if that happens, just re-run the `createdb` line.

> ✅ **Check:** `docker compose ps` shows the `db` service as `running (healthy)`.

### 3. Backend setup

```bash
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies (requirements-dev.txt adds the test tooling
# and pulls in requirements.txt itself)
pip install -r requirements-dev.txt
```

Create `backend/.env`:

```bash
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720
FRONTEND_URL=http://localhost:5173" > .env
```

That's everything local development needs. Every other variable is optional and documented in
[docs/environment.md](docs/environment.md) — leave them unset and the integrations they control
run in a safe simulated mode (emails print to your console, checkout is fake).

Then create the schema, seed it, and run:

```bash
# Create the database tables. Required — the app does not create them on
# startup; Alembic owns the schema. Safe to re-run (it's a no-op once applied).
alembic upgrade head

# Seed the database with committees, chairs, and test data.
# Safe to re-run: every seeder skips what already exists.
python seed.py

# Start the development server
python main.py
# or: uvicorn main:app --reload
```

> ✅ **Check:** <http://localhost:8000/health> returns `{"status":"ok"}`, and
> <http://localhost:8000/docs> lists the API. If `/health` works but pages 500 later, you skipped
> `alembic upgrade head`.

### 4. Frontend setup

In a second terminal:

```bash
cd frontend

# Install dependencies
npm install

# Create the environment file
echo "VITE_API_URL=http://localhost:8000" > .env.local

# Start the dev server
npm run dev
```

> ✅ **Check:** <http://localhost:5173> loads, and you can sign in with
> `test@cougarnet.uh.edu` / `password123`. Seeded chair, E-Board, and president accounts are
> listed in [docs/database.md](docs/database.md#seeded-accounts) — all use the same password.

### When something goes wrong

| Symptom | Cause | Fix |
|---|---|---|
| `connection refused` on port 5433 | Database container isn't up | `docker compose up -d --wait` |
| `port 5433 already allocated` | Another Postgres is using it | Stop it, or change the port in `docker-compose.yml` and `DATABASE_URL` |
| Backend starts, then 500s on the first real page | Tables were never created | `alembic upgrade head` |
| `SECRET_KEY` error on startup | No `backend/.env` | Re-run the `echo` block in step 3 |
| Frontend loads but every data page is empty | Backend isn't running, or `VITE_API_URL` has no `http://` | Start the backend; the scheme is **required** |
| Stale or broken data right after a reseed | Backend is holding pooled connections from before the wipe | Restart the backend |
| Committees or events missing entirely | Database was wiped without reseeding | `python seed.py` |

## Contributing

New committee members: you don't need permission to start. Pick something, branch, open a pull
request. The rules below exist so nobody has to repair `main` later.

### Branching and pull requests

**`main` is the live site. Never commit to it directly.** All work happens on `dev`.

```bash
git checkout dev
git pull
git checkout -b short-description-with-hyphens
```

Branch names are lowercase words separated by hyphens — `member-detail-view`,
`fix-mobile-footer`. No prefixes, no personal names.

1. **Open a pull request into `dev`** when your work is ready. No issue needed first — just open
   the PR. If you want feedback before it's finished, open it as a draft.
2. **Describe what changed and why.** If it's visible, include a screenshot. The person reviewing
   it hasn't been in your head for the last three hours.
3. **CI has to be green.** Two jobs run on every PR — backend tests, and frontend lint + build.
   Both must pass before merge.
4. **Every PR needs one review** before it merges. Don't merge your own.
5. `dev` merges into `main` for releases.

Run the same checks CI runs before you push:

```bash
cd backend && .venv/bin/python -m pytest tests/
cd frontend && npm run lint && npm run build
```

### Writing the code

- **Match the code around you.** Existing style wins over personal preference, even when you'd do
  it differently. Change only what your task requires — don't reformat or "improve" adjacent code
  in the same PR, because it buries the real change in noise.
- **Business logic goes in `backend/services/`**, not in the route. Routes parse, authorize, and
  delegate.
- **Frontend API calls go through the shared `api` axios instance** in `src/api/client.js`, using
  the feature modules in `src/api/` — never a bare
  `fetch`, never a raw axios import.
- **Every page calls `useDocumentTitle` once.** A page that skips it inherits the previous page's
  browser-tab title.
- Full conventions, including the load-bearing CSS ones, are in
  [docs/architecture.md](docs/architecture.md).

### If you change the database

1. Edit the model in `backend/models/`.
2. **If it's a new model, import it in `backend/database.py`.** That import is the only thing
   registering the table — forget it and the table is silently missing from migrations *and* from
   every test.
3. Generate the migration: `alembic revision --autogenerate -m "what you changed"`.
4. **Open the generated file and read it.** Autogenerate is a starting point, not a guarantee, and
   it does **not** detect new enum values — those you write by hand.
5. Apply it with `alembic upgrade head` and commit it alongside the model change.

Details and the enum workaround: [docs/database.md](docs/database.md).

### Tests

Fixing a bug? Write the failing test first, then fix it. Adding validation? Write the
invalid-input tests, then make them pass. Tests live in `backend/tests/<area>_tests/` and need the
database container running. See [docs/testing.md](docs/testing.md).

### Two things to be careful with

- **Never commit `backend/.env`, `frontend/.env.local`, or anything in `backend/secrets/`.** All
  three are gitignored — keep it that way.
- **`seed.py` is local-only.** It creates accounts that all share `password123`. It has guards that
  refuse to run against a non-local database, and those guards are not an inconvenience to work
  around.

## Where everything else lives

Full index: [docs/README.md](docs/README.md).

| Doc | What's in it |
|---|---|
| [glossary.md](docs/glossary.md) | Chapter and codebase terms — **read this first** |
| [architecture.md](docs/architecture.md) | How a request flows, repository layout, frontend conventions, pages |
| [features.md](docs/features.md) | What every feature does, in detail |
| [api.md](docs/api.md) | Every endpoint and the role it requires |
| [environment.md](docs/environment.md) | Every environment variable |
| [database.md](docs/database.md) | Migrations, seed data, seeded accounts, local reset |
| [testing.md](docs/testing.md) | Running and writing tests, CI, testing a real phone QR scan |
| [integrations.md](docs/integrations.md) | Square, Google Drive, and Google Sheets setup |
| [deployment.md](docs/deployment.md) | Vercel + Railway, production database, going-live checklist |

Coding agents (Claude Code, Codex) read [AGENTS.md](AGENTS.md).
