# AGENTS.md — SHPE UH Website

Instructions for coding agents (Claude Code reads this via `CLAUDE.md`; Codex reads it directly).
Setup, API reference, and deployment runbooks live in `README.md` — this file is only what an
agent would get wrong without being told.

## Project Overview

SHPE University of Houston chapter website. React + Vite frontend, FastAPI + PostgreSQL backend.

## Stack

- **Frontend:** React 19, Vite, Tailwind CSS v4, Framer Motion, React Router v7, Axios, qrcode.react
- **Backend:** FastAPI, SQLModel, PostgreSQL 17 (`postgresql+psycopg://`, psycopg 3), PyJWT, pwdlib (Argon2), slowapi
- **Auth:** JWT bearer via `/login`. `/signup` creates an **unverified** account and emails a link — no token returned, and login 403s until `/verify-email` confirms it.

## Running Locally

```bash
docker compose up -d          # Postgres 17 on localhost:5433 — required for backend AND tests
cd backend && alembic upgrade head && python main.py    # :8000
cd frontend && npm run dev                              # :5173
```

`create_db()` does not create tables — Alembic owns the schema. On a fresh or wiped database the
app boots fine and then 500s on the first query until `alembic upgrade head` has run.

## Testing & CI

```bash
cd backend && .venv/bin/python -m pytest tests/    # Postgres container must be running
cd frontend && npm run lint && npm run build
```

Tests live in `tests/<area>_tests/`, run against a dedicated `shpe_test` database. CI runs both
jobs on every push/PR to `main` and `dev`; both must pass before merging to `main`.

## Layout

```
backend/   main.py config.py database.py chapter_data.py seed.py bootstrap.py
           routes/ models/ services/ security/ validators/ alembic/ tests/
frontend/src/   pages/ components/ context/ hooks/ utils/ api/ App.jsx styles.css
```

- `config.py` — the single knob for every writable path (`DATA_DIR` → `RESUME_DIR`, `PRODUCT_IMAGE_DIR`), and the only place `ENVIRONMENT`/`SQUARE_ENVIRONMENT` are read.
- `chapter_data.py` — real chapter structure (committees, org chart, dues). Edit committees **here**, not in `seed.py`/`bootstrap.py`.
- `seed.py` local dev only (two guards, both exit 1). `bootstrap.py` is the production installer and structurally cannot create an account.

## Environment Variables

Full annotated list in `README.md`. The ones that are easy to get wrong:

- `CORS_ORIGINS` — browser origins the **frontend** is served from. `ALLOWED_HOSTS` — the Host header of the **API itself**. Not the same value.
- `TRUST_PROXY_IP_HEADERS=1` behind a proxy, or every rate limit collapses into one global bucket.
- `MAX_REQUEST_BODY_BYTES` must stay **above** the per-route 2 MB upload caps.
- `ENVIRONMENT=production` flips dev-mode fallbacks to fail closed and requires `SQUARE_*`, `SMTP_HOST`, and all four `GDRIVE_*` to be set or the container won't boot.
- `SQL_ECHO` — leave unset in production; it logs member emails and PSIDs.
- `VITE_API_URL` needs a scheme (`https://`). Without one the app white-screens on data pages only.

## Backend Patterns

- Use `SessionDependencies` (`services/dependencies.py`) for DB sessions — never build one manually.
- Normalize emails with `normalize_email()` (`validators/email.py`) before any lookup or insert.
- Use `utcnow()` (`services/time_services.py`) — `datetime.utcnow()` is deprecated on 3.12.
- Hash with `get_password_hash()` (`security/hashing.py`). Never store plaintext.
- New routes → an APIRouter in `routes/`, included in `main.py`.
- **New models must be imported in `database.py`.** That import is the only thing registering the table in `SQLModel.metadata` — forget it and the table is silently missing from migrations *and* every test.

## Frontend Patterns

- All API calls use the shared axios instance in `src/api/client.js` through the domain modules in `src/api/` — never `fetch`, never a raw axios import. `src/api/api.js` is the compatibility barrel. (Sole exception: the home page's Behold Instagram feed, an external public CDN.)
- New API functions read the token via the internal `authHeaders()` helper — don't pass it as a parameter. **Public** endpoints must NOT send `authHeaders()`.
- Pages in `src/pages/`, reusable UI in `src/components/`, routes in `App.jsx`.
- **Every page calls `useDocumentTitle` once**, near the top. `index.html` has one static `<title>` for all routes, so a page that skips it inherits the previous page's title.
- Long lists paginate client-side via `usePagination` + `<Pagination>`. Counts and badges must keep reading the **full** array, never `pageItems`. Pass `resetKey` when a tab/search/filter sits above the list. Call the hook above any early `return`.
- The About page has its **own hardcoded** roster, not synced with `chapter_data.py` or role assignment. Promoting a chair updates `/committees` only; About stays stale until hand-edited.

## Styling

- Design tokens live in `src/styles.css` `:root` — brand colors, gradients, radii, shadows. Reference the tokens rather than hardcoding hex.
- Tailwind **v4** (config in `tailwind.config.cjs`). Utility classes first; only add custom CSS when Tailwind can't do it. `App.css` is unused boilerplate.
- Shared buttons: `.primaryBtn` (navy), `.accentBtn` (red), `.ghostBtn` (outline).
- `--header-height` (80px) is a guarantee, not a guess. `.headerRow` height, `.brandMark img` height, and the `inset` box-shadow are all load-bearing — change one and `.main`'s padding, `DuesBanner`'s offset, and every `calc(100vh - …)` drift apart silently.

## Datetime

Store and compare **naive UTC** (`utcnow()`) — these map to Postgres `TIMESTAMP WITHOUT TIME ZONE`.
On the frontend append `'Z'` when constructing a Date: `new Date(event.start_time + 'Z')`.

## What NOT to do

**Secrets & config**
- Never commit `backend/.env` or `frontend/.env.local`.
- Never read `ENVIRONMENT`/`SQUARE_ENVIRONMENT` with a bare `os.getenv` — call `config.is_production()` / `config.square_is_production()`. Both read env at **call** time and strip/lowercase.
- Set `EMAIL_FROM` explicitly and validate it contains `@`; never default it to `SMTP_USER`. Never discard `send_email`'s return value. `SMTP_PORT` must be a STARTTLS port (587, not 465).

**Dependencies**
- Use `pyjwt` (imported as `jwt`), not `python-jose`.
- Don't add `python-dotenv` — already transitive. Just call `load_dotenv()`.

**Database & models**
- Never put a privilege- or state-bearing field on `UserBase` — it's inherited by `UserCreate` and settable from the public `POST /signup` body. This shipped once with `role` and `points`.
- Never query by a role's **display value** — SQLModel stores the enum *name*, Pydantic serializes the *value*.
- `alembic revision --autogenerate` does **not** detect changed enum members. Write those migrations by hand.
- Every seeder needs an "already seeded" guard — `seed.py` is re-run to top up.
- New seeded accounts need `email_verified = True`, or they seed fine and then can't log in.
- No digits in seeded user **names** — the `UserCreate` validator allows only letters, hyphens, apostrophes, spaces. Put them in the email.
- Guard destructive scripts on the **connection target** (`assert_local_database()`), not an ambient flag.
- Never key a sync on fields the source lets people edit — a rename mints a new identity and duplicates the row.

**Routes & middleware**
- Under a prefix, register `@router.get('')`, not `'/'`.
- Never call blocking I/O inside an `async def` handler — it freezes the event loop for every user.
- Never re-add `allow_origin_regex` to CORS — Starlette matches with `re.fullmatch`. Exact-origin allowlist only.
- Never fix a wrong request scheme with uvicorn's `--proxy-headers`/`--forwarded-allow-ips` — `services/forwarded_proto.py` owns it, and the Dockerfile deliberately passes neither.
- Enforce upload size caps **before** `await file.read()`, not after.
- `BodyLimitMiddleware` must own its own 413 — not via `app.add_exception_handler`.
- Never expose the API schema in production, and never disable only `/docs` — gate `/docs`, `/redoc`, and `/openapi.json` together.

**Rate limits**
- Never key limits on `request.client.host` behind a proxy — that's the proxy's address, identical for every visitor.
- Never size limits for a single user. At a GBM the whole room shares one NAT'd campus IP; QR check-in is the extreme case.

**Business logic**
- Never hard-delete a shop `Product` — `DELETE` is a soft delete, and restore needs the image.
- Never tell a buyer **which** check their card failed — generic decline only. `POST /shop/orders` is anonymous by design.
- Never let an "already in this state" branch fall through into the side effects.
- Never enforce a visibility flag only on the read path — enforce it on write too.
- Never let a dev-mode no-op return the same value as success when the caller discards state based on it.
- A soft-deleted event must be invisible everywhere — the filter lives in `services/event_services.py`.
- Anything that moves an event's `start_time` must call `reschedule_reminders()`; `remind_at` is computed once and never revisited on its own.
- Never double-award points.
- `User.has_paid_dues` is stored, not derived — set it wherever dues are earned (`create_order`, the sheet sync, `create_user`), never clear it outside `reset_dues.py`. The sync must filter on `current_dues_period_start()`, or next year's sheet marks the chapter paid today.
- Google auth differs by integration and the two are not interchangeable. **Drive resume uploads** (`drive_services.py`) use OAuth refresh-token credentials — a service account has no storage quota of its own and 403s `storageQuotaExceeded` uploading into a My Drive folder. The **event-tracker Sheet sync** (`event_tracker_services.py`) correctly uses a service account; reading a shared Sheet creates no files, so the quota limit doesn't apply. Don't "fix" one by copying the other's credentials.
- Never give product images a deterministic filename — they're served `Cache-Control: immutable`, so a replacement would serve the old photo forever.
- Never call `PasswordHash.recommended()` per hash — `security/hashing.py` holds one module-level instance.

**Frontend**
- Named React imports (`import { useState } from 'react'`), not `React.useState`.
- Lint fails the build on: `setState` synchronously in a `useEffect` body, writing a ref during render, and exporting helpers/constants from a file that also exports a component. `no-unused-vars` only ignores `^[A-Z_]` and JSX usage doesn't count, so files importing lowercase `motion` need `/* eslint-disable no-unused-vars */`.
- Never pair `.catch(() => {})` with a success toast — surface `err.response?.data?.detail`.
- Put cart rules in `CartContext.addItem`, not the page that happens to trigger them — there are several entry points.
- Never display a money figure the server didn't just confirm — cart lines snapshot price into localStorage indefinitely.
- `<Link to="/page#anchor">` does not scroll. The target page needs its own `scrollIntoView` effect.
- Guard a multi-step wizard's submit handler by step, or Enter POSTs a half-filled payload.
- Validate signup fields on the frontend too — backend-only means a 422 naming a field from step 4.
- Never give a page its own top offset for the fixed header, and never make new chrome `position: fixed` expecting pages to leave room. Full-viewport elements subtract it: `calc(100vh - var(--header-height))`.

**Tests**
- Never hardcode a rate-limit count — import the constant and use `limit_count()`.
- A second test user needs unique `personal_email` and `psid`, not just `cougarnet_email`.
- Date event fixtures relative to `utcnow()`, never a hardcoded calendar date — past events are frozen.
- Wiring up a new external service means adding an autouse `disable_*` fixture to `conftest.py`, or the suite runs against a developer's live credentials.

## Engineering Guidelines

**Think before coding.** State assumptions explicitly; if uncertain, ask. If multiple
interpretations exist, present them — don't pick silently. If a simpler approach exists, say so.
If something is unclear, stop and name what's confusing.

**Simplicity first.** Minimum code that solves the problem. No features beyond what was asked, no
abstractions for single-use code, no configurability that wasn't requested, no error handling for
impossible scenarios. If you write 200 lines and it could be 50, rewrite it. Ask: "would a senior
engineer call this overcomplicated?"

**Surgical changes.** Touch only what you must. Don't "improve" adjacent code, comments, or
formatting. Don't refactor what isn't broken. Match existing style even if you'd do it differently.
If you notice unrelated dead code, mention it — don't delete it. Do remove imports and variables
that *your* changes orphaned. **Every changed line should trace directly to the request.**

**Verify.** Turn tasks into checkable goals: "add validation" → "write tests for invalid inputs,
then make them pass"; "fix the bug" → "write a failing test that reproduces it, then fix it."
For multi-step work, state the plan as steps with a verification per step.
