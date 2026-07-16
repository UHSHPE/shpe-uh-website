# CLAUDE.md — SHPE UH Website

## Self-Update Instructions
After every session, update this file if any of the following happened:
- A bug was caused by a pattern not listed here → add it to "What NOT to do"
- A new file, route, or dependency was added → update the relevant section
- A correction was made to existing instructions → fix it here
- A new "lesson learned" emerged → add it to "Key Rules & Lessons Learned"

**Also keep `README.md` in sync.** If a change affects anything the README documents — features, setup steps, env vars, seeded accounts, project structure, pages, API endpoints, or test instructions — update the corresponding README section in the same session. The README is user-facing: keep it accurate but free of internal lessons/gotchas (those belong here).

Keep this file accurate. It is read at the start of every session.

## Project Overview
SHPE University of Houston chapter website. React + Vite frontend, FastAPI + SQLite backend.

## Stack
- **Frontend:** React 19, Vite, Tailwind CSS v4, Framer Motion, React Router v7, Axios
- **Backend:** FastAPI, SQLModel (ORM), SQLite (`database.db`), PyJWT, pwdlib (Argon2 hashing), slowapi (rate limiting)
- **Auth:** JWT bearer tokens via `/login` and `/signup` endpoints; self-service password reset via `/password-reset/*`

## Project Structure
```
shpe-uh-website/
  frontend/
    src/
      api/api.js          # Axios instance (baseURL from VITE_API_URL env var)
      components/         # Header, Footer, Avatar, GalleryApproved, PrivateRoute
      pages/              # home, about, gallery, membershpe, sponsors, get-involved, dashboard, committees, profile
      App.jsx             # Routes
  backend/
    main.py               # FastAPI app: includes routers + background reminder email loop (60s)
    get_drive_refresh_token.py  # One-time helper: mints the OAuth refresh token AND creates the app-owned resume folder (drive.file scope)
    database.py           # SQLite engine + session factory
    seed.py               # Seeds test user, all 14 committees with their real chairs/co-chairs (22 chair users), and sample events — run once: python seed.py
    routes/               # APIRouters: auth_routes, committee_routes, event_routes (incl. reminders), notification_routes, pw_reset_routes, resume_routes
    uploads/resumes/      # Uploaded resume PDFs, one per user (user_<id>.pdf); gitignored, created on first upload
    models/               # SQLModel table definitions (user/ incl. pw_reset_token.py, committee.py, committee_message.py, notification.py, event.py, event_reminder.py)
    security/             # jwt.py (token creation), hashing.py (Argon2)
    services/             # dependencies.py, user_services.py, committee_services.py, reminder_services.py, email_services.py, drive_services.py, time_services.py, auth_user.py, pw_reset_services.py, rate_limit.py
    validators/           # email.py (normalize_email)
    tests/                # pytest suite; conftest.py has in-memory-DB fixtures (client, session, user) + make_user/make_event helpers
    .env                  # SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, FRONTEND_URL, optional SMTP_* (never commit)
```

## Running Locally
**Backend** (requires `.venv` activated):
```bash
cd backend
python main.py        # or: uvicorn main:app --reload
```
Runs on http://localhost:8000

**Frontend:**
```bash
cd frontend
npm run dev
```
Runs on http://localhost:5173

## Environment Variables
**Backend** (`backend/.env`):
```
SECRET_KEY=<random hex — generate with: python3 -c "import secrets; print(secrets.token_hex(32))">
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30

# Base URL of the frontend, used to build password-reset links in emails.
# Defaults to http://localhost:5173 if unset.
FRONTEND_URL=http://localhost:5173

# Optional — reminder emails. Without SMTP_HOST, emails print to the console (dev mode).
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<sender address>
SMTP_PASSWORD=<app password>
EMAIL_FROM=SHPE UH <noreply@example.org>   # optional, defaults to SMTP_USER

# Optional — Google Drive resume sync. Without folder id + credentials set,
# Drive sync is a console-printing no-op (dev mode). Setup steps in README.
GDRIVE_RESUME_FOLDER_ID=<app-created folder id printed by get_drive_refresh_token.py — NOT a hand-made folder's id>
GDRIVE_OAUTH_CLIENT_ID=<OAuth Desktop-app client id>
GDRIVE_OAUTH_CLIENT_SECRET=<OAuth client secret>
GDRIVE_OAUTH_REFRESH_TOKEN=<minted once via get_drive_refresh_token.py>
```

**Frontend** (`frontend/.env.local`):
```
VITE_API_URL=http://localhost:8000
VITE_BEHOLD_FEED_URL=https://feeds.behold.so/<feed-id>   # public Behold JSON feed for the home-page Instagram grid
```
The `api.js` axios instance reads `VITE_API_URL` — without this set, all API calls will fail.
`VITE_BEHOLD_FEED_URL` powers the home page's Instagram section; if unset or the fetch fails, the grid keeps its shimmer placeholder (layout never breaks).

## Continuous Integration

GitHub Actions runs on every push and pull request to `main` and `dev`:

- **backend** — installs `backend/requirements.txt` and runs `pytest tests/`
- **frontend** — runs `npm ci`, `npm run lint`, and `npm run build`

Both jobs must pass before merging into `main`.

## Key Rules & Lessons Learned

### Never commit secrets
- `backend/.env` and `frontend/.env.local` must stay out of git
- These should already be in `.gitignore` — verify before any commit

### Backend patterns
- Always use `SessionDependencies` (from `services/dependencies.py`) for DB sessions — do not create sessions manually
- Normalize emails with `normalize_email()` from `validators/email.py` before any DB lookup or insert
- New routes go in an APIRouter under `routes/` (included in `main.py`); new DB models go in `models/` and must be imported in `database.py` so SQLModel registers them before `create_db()` runs
- Use `utcnow()` from `services/time_services.py` for "now" — `datetime.utcnow()` is deprecated and raises DeprecationWarning on Python 3.12
- Tests live in `tests/<area>_tests/`; run with `.venv/bin/python -m pytest tests/` from `backend/`. API tests use the `client` fixture from `tests/conftest.py` (in-memory SQLite + auth override); `httpx` is required for TestClient
- Passwords are hashed with `get_password_hash()` from `security/hashing.py` — never store plaintext

### Frontend patterns
- All API calls go through the `api` axios instance in `src/api/api.js` — never use fetch or a raw axios import
- Pages live in `src/pages/`, reusable UI in `src/components/`
- Routes are defined in `App.jsx` — update there when adding new pages
- The About page (`pages/about.jsx`) has its **own hardcoded** 2026-2027 E-Board + Chairs roster (names/positions/emails). This is **separate from and not synced with** `seed.py`'s `COMMITTEE_ROSTER` — editing one does NOT update the other, and they can drift (the About chairs use committee role-based `@shpeuhchair.org` emails, while seed users use `<first>.<last>@cougarnet.uh.edu`). Cards fall back to an initials placeholder when a member has no `img`, and the email line is omitted when `email` is empty.
- Tailwind v4 is used — do NOT use v3 syntax (e.g. `bg-[color]` utilities are fine, but config is in `tailwind.config.cjs`)
- The home page (`pages/home.jsx`) `#insta` grid is wired to a live **Behold** (behold.so) Instagram feed: a `useEffect` fetches `VITE_BEHOLD_FEED_URL` on mount, takes the first 6 `data.posts`, and renders each as an `<a>` (permalink, new tab) wrapping an `<img>`. Image src is `post.sizes?.medium?.mediaUrl` (Behold-hosted thumbnail) with `post.mediaUrl` (Instagram CDN) as fallback. This is an **external public CDN** — it uses `fetch()` directly, NOT the `api.js` axios instance. On fetch error / unset env var, `instaPosts` stays empty and the original shimmer placeholder renders as fallback so the layout never breaks.

### Styling
- The design-system tokens live in `src/styles.css` `:root` — brand colors (`--shpe-navy`, `--shpe-blue`, `--shpe-red`, `--event-*`), gradients (`--gradient-navy`, `--gradient-orange`), radii (`--radius-*`), shadows (`--shadow-card/pop/modal`), and container widths. Reference these tokens (in Tailwind arbitrary values or inline styles) rather than hardcoding hex. Legacy aliases `--blue`/`--navText`/`--muted` are kept for existing pages.
- Work Sans (the brand typeface) is loaded via a Google Fonts `@import` at the top of `styles.css` and set as the `body` font (`--font-body`) — don't re-import it per page.
- Use Tailwind utility classes first; only add custom CSS to `styles.css` when Tailwind can't do it (e.g. the header member-dropdown classes). `App.css` is unused Vite boilerplate — don't add to it.
- Shared button classes: `.primaryBtn` (navy), `.accentBtn` (SHPE red), `.ghostBtn` (outline).
- Framer Motion is available for animations — use it for page transitions and reveals

### What NOT to do
- Do not use `python-jose` — the project uses `pyjwt` (imported as `jwt`)
- Do not add `python-dotenv` to requirements — it is already a transitive dependency; just call `load_dotenv()` at the top of any file that needs env vars
- Do not create new axios instances — reuse the one in `api/api.js`
- Do not use `React.useState` / `React.useEffect` — use named imports: `import { useState, useEffect } from 'react'`
- Do not use a Google **service account** to upload to a personal My Drive folder — Google 403s it (`storageQuotaExceeded`); use the OAuth refresh-token credentials instead (see "Google Drive resume sync")

## Pages & Routes
| Path | Component | Auth required |
|------|-----------|---------------|
| `/` | `pages/home.jsx` | No |
| `/forgot-password` | `pages/forgot-password.jsx` | No |
| `/reset-password` | `pages/reset-password.jsx` (token via `?token=`) | No |
| `/about` | `pages/about.jsx` | No |
| `/membershpe` | `pages/membershpe.jsx` | No |
| `/sponsors` | `pages/sponsors.jsx` | No |
| `/gallery` | `pages/gallery.jsx` | No |
| `/calendar` | `pages/calendar.jsx` | No |
| `/get-involved` | `pages/get-involved.jsx` (commented out) | No |
| `/dashboard` | `pages/dashboard.jsx` | Yes (PrivateRoute) |
| `/committees` | `pages/committees.jsx` | Yes (PrivateRoute) |
| `/profile` | `pages/profile.jsx` | Yes (PrivateRoute) |

## Protected Routes
`components/PrivateRoute.jsx` wraps any route that requires authentication. If `token` is null it redirects to `/signin` preserving the intended destination in `location.state.from`. After sign-in the user is forwarded to that destination (or `/dashboard` by default).

## Backend API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/login` | No | Returns JWT token (rate limited: 5/minute per IP) |
| POST | `/signup` | No | Creates user, returns JWT token |
| POST | `/password-reset/request` | No | Always 200 with a generic body; if the account exists, emails a single-use reset link to cougarnet_email (rate limited: 3/hour per IP) |
| POST | `/password-reset/confirm` | No | Sets a new password from a valid token; generic 400 for unknown/used/expired tokens |
| GET | `/me` | Yes | Returns current user (includes `points`) |
| GET | `/events/upcoming?days=7` | Yes | Upcoming events within N days |
| GET | `/events` | No | All events ordered by start_time (public, powers the calendar) |
| GET | `/committees` | Yes | All committees with `is_member`, `is_chair`, and `chairs` (list of name + role-based contact email) |
| POST | `/committees/{id}/join` | Yes | Join a committee (notifies the member + every chair) |
| DELETE | `/committees/{id}/leave` | Yes | Leave a committee |
| GET | `/committees/{id}/members` | Yes (chair only) | Roster with name, email, phone; 403 if not the chair |
| POST | `/committees/{id}/messages` | Yes (chair only) | Broadcast a message; notifies every active member |
| GET | `/committees/{id}/messages` | Yes (member or chair) | Committee messages, newest first; 403 otherwise |
| GET | `/notifications` | Yes | Current user's notifications, newest first |
| POST | `/notifications/{id}/read` | Yes | Mark one notification read |
| POST | `/me/resume` | Yes | Upload a PDF resume (multipart `file`); validates PDF type, ext, `%PDF` magic bytes, and ≤2 MB (400/413 otherwise). Renames it to `First_Last_PSID.pdf` (sets `User.resume_filename`); mirrors to Google Drive when `GDRIVE_*` is configured |
| GET | `/me/resume` | Yes | Download the current user's resume PDF (`FileResponse`); 404 if none |
| DELETE | `/me/resume` | Yes | Remove the current user's resume (204); also deletes the Google Drive copy |
| POST | `/events/{id}/remind` | Yes | Set an email reminder for an event (404 unknown event, 409 already set, 400 already started) |
| DELETE | `/events/{id}/remind` | Yes | Cancel an unsent reminder (404 if none active) |
| GET | `/events/reminders/me` | Yes | Current user's active (unsent) reminders |

## Committee leadership, notifications & messaging
- Committees support **co-chairs**: a committee's chairs are the users with a `CommitteeMembership` row where `is_chair=True` (one row per co-chair). `CommitteeOut.chairs` is a **list** of `ChairOut` (name + email) and `CommitteeOut.is_chair` reflects the current user's membership row.
- `Committee.chair_role` (a `Role` enum value, nullable) still maps each committee to one chair role (1:1). Co-chairs of the same committee **share the same Role** (e.g. both MentorSHPE co-chairs have `Role.mentorshpe_chair`). Chair-only endpoints are gated by `require_chair`, which checks `user.role == committee.chair_role` — so seed both the role on the user AND the `is_chair` membership row, or chairs will display but lack permissions (or vice versa).
- The real chair roster lives in `seed.py` (`COMMITTEE_ROSTER`): 14 committees, 22 chairs. Seeded chair logins are `<first>.<last>@cougarnet.uh.edu` / `password123`.
- **Chair contact email shown in `ChairOut` is role-based, not the user's own email.** `chair_contact_email()` in `services/committee_services.py` maps each `chair_role` to a shared committee address (`CHAIR_EMAILS`, e.g. `academics@shpeuhchair.org`) so co-chairs display the same contact (matches the public About page). Roles with no published address fall back to the chair's `personal_email` — as of now every committee role has a published address (Web Dev is `Web.Dev@…`, Member Relations is `Member.Relations@…`), so that fallback is just a safety net. The frontend Committees card therefore keys chairs by name, **not** email, since co-chairs share one. Changing this is a code edit (no re-seed needed) — just restart the backend.
- `models/notification.py` — `Notification` rows are per-user (`user_id`), with optional `committee_id`, `is_read`, and a `body` string. Joining a committee creates a welcome notification for the joiner AND a "X joined" notification for **every** chair. Sending a committee message creates one notification per active member (sender excluded).
- `models/committee_message.py` — `CommitteeMessage` is a chair→committee broadcast. `CommitteeMessageOut` includes a resolved `sender_name`.
- Frontend: the Committees page lists **every** chair (name + email) as a contact line on each card; chairs get a **Manage committee** panel (roster with phone + message composer), members get a read-only **View messages** panel. The Dashboard shows a **Notifications** panel (unread highlighted; click to mark read).
- New `api/api.js` functions: `getCommitteeMembers`, `getCommitteeMessages`, `sendCommitteeMessage`, `getNotifications`, `markNotificationRead`.

## Event email reminders
- `models/event_reminder.py` — `EventReminder(user_id, event_id, remind_at, sent_at)`. A reminder is "active" while `sent_at` is NULL.
- Timing (`compute_remind_at` in `services/reminder_services.py`): 24h before the event; if the event is <24h away, 1h before; if <1h away, immediately. Events that already started → 400.
- `send_due_reminders(session)` emails each due unsent reminder to the user's **personal_email** and stamps `sent_at`. Failed sends stay unsent and are retried. `main.py` runs this in a background asyncio loop every 60s (started in `lifespan`, via `asyncio.to_thread`).
- `services/email_services.py` — `send_email(to, subject, body)`: SMTP via `SMTP_*` env vars; with no `SMTP_HOST` it prints to the console and returns True (dev mode). SMTP failure returns False (no raise).
- Frontend: the public `/calendar` page shows a "Remind me by email" button on future events (toggles to cancel). Signed-out users are sent to `/signin` with `location.state.from`, same as PrivateRoute. Reminder state comes from `getMyReminders()`.
- `api/api.js` functions: `setEventReminder`, `cancelEventReminder`, `getMyReminders`.

## Password reset & rate limiting
- `models/user/pw_reset_token.py` — `PasswordResetToken(user_id, token_hash, created_at, expires_at, used_at)`. Only the **SHA-256 hash** of the raw token is stored (the raw token is high-entropy `secrets.token_urlsafe(32)`, so SHA-256 — not Argon2 — is correct here). A token is active while `used_at` is NULL and `expires_at` is in the future; TTL is 1 hour. Requesting a new reset retires any prior active tokens for that user.
- `services/pw_reset_services.py` — `generate_reset_token()` / `hash_reset_token()`.
- `routes/pw_reset_routes.py` — `POST /password-reset/request` and `POST /password-reset/confirm`. **Never reveal whether an email exists**: request always returns the same 200 body (even if `send_email` fails), and confirm returns one generic 400 for unknown/used/expired tokens. Reset emails go to **cougarnet_email** (the verified UH address). The link is `{FRONTEND_URL}/reset-password?token=<raw>`.
- Confirm reuses the shared `validate_password_strength()` from `models/user/user_schemas.py` (also used by `UserCreate`) — change password rules there, in one place.
- **JWT invalidation:** `create_access_token` sets `iat`; a successful reset stamps `User.password_changed_at`, and `get_current_user` rejects tokens whose `iat` predates it. PyJWT floors `iat` to whole seconds while `password_changed_at` keeps microseconds, so the comparison is at **whole-second granularity with strict `<`** — a token issued in the same second as the reset stays valid. Tokens without `iat` are rejected once `password_changed_at` is set.
- **Rate limiting (slowapi):** the `Limiter` lives in `services/rate_limit.py` (NOT `main.py` — route modules import it, and importing from `main` would be circular). `main.py` attaches it to `app.state` and registers the 429 handler. `/login` is `5/minute`, `/password-reset/request` is `3/hour` (keyed by client IP). slowapi-decorated endpoints must take a `request: Request` parameter, with the `@limiter.limit(...)` decorator **below** the router decorator.
- slowapi's counters are in-memory and persist across tests in one process — `tests/conftest.py` has an autouse `reset_rate_limiter` fixture calling `limiter.reset()` so counts don't bleed between tests. Auth tests that must exercise real JWT flow use the `unauth_client` fixture (`client` overrides `get_current_user` and bypasses auth).
- The `password_changed_at` column lives on the `User` TABLE model (not `UserBase`), same pattern as `resume_filename`. Adding it required a db rebuild (done); new tables like `passwordresettoken` are created by `create_all()` automatically.
- Frontend: `/forgot-password` (always shows the same "check your email" confirmation) and `/reset-password` (reads `?token=`, new + confirm fields, redirects to `/signin` with `location.state.message` on success — signin renders that message). Sign-in has a "Forgot password?" link and maps 429 to a "too many attempts" error. `api.js`: `requestPasswordReset`, `confirmPasswordReset` — both **public**, no auth headers.

## Profile page & resume uploads
- `pages/profile.jsx` (route `/profile`, in the member dropdown under Committees) shows the signed-in user's info **read-only** (no editing) plus a resume section. It reads everything from `useAuth().user` (the `/me` payload) and tracks resume state locally.
- Resumes are **PDF only** and **private to the owner** (no chair/other-user access). `User.resume_filename` (nullable, on the `User` table model — NOT `UserBase`, so signup is untouched) stores the canonical `First_Last_PSID.pdf` name; `UserOut` exposes it so the frontend knows whether a resume exists. The PDF lives on disk at `backend/uploads/resumes/user_<id>.pdf` (deterministic → re-upload overwrites).
- `routes/resume_routes.py` validates uploads (PDF content-type + `.pdf` ext + `%PDF` magic bytes, ≤2 MB) and serves the file via `FileResponse`. Storage dir is `RESUME_DIR` (a module constant) — tests monkeypatch it to a `tmp_path` to stay hermetic. Every resume is **renamed to `First_Last_PSID.pdf`** (`_canonical_resume_name()` — multi-word names join with underscores, uploaded filename discarded); that canonical name is used for `resume_filename`, the download name, and the Drive copy. The profile page also pre-checks type and the 2 MB cap client-side for instant feedback — keep the two limits in sync.
- **Google Drive sync** (`services/drive_services.py`): when `GDRIVE_RESUME_FOLDER_ID` + credentials are set, uploads mirror the PDF to that Drive folder under the same canonical `First_Last_PSID.pdf` name and deletes remove it. `User.resume_drive_file_id` (table model, internal — NOT in `UserOut`) tracks the Drive file: re-uploads **update in place** (same file id → no orphans; 404 falls back to create), and a failed Drive delete keeps the id so the next upload replaces the orphan. Sync is **best-effort**: failures are logged, never raised — the local file in `uploads/resumes/` stays the source of truth, and without config every Drive call is a console-printing no-op (same dev-mode pattern as `email_services.py`). The googleapiclient is blocking → routes call it via `asyncio.to_thread`. Deps: `google-api-python-client`, `google-auth`, `google-auth-oauthlib` (helper script only). Drive tests monkeypatch the two functions on `routes.resume_routes` (they're imported there by name); an **autouse `disable_drive_sync` fixture in conftest.py clears all `GDRIVE_*` env vars** so tests never hit the real API even when `backend/.env` has live credentials (drive config is read at call time, and `load_dotenv()` leaks .env into the test process).
- **Credentials — OAuth only, deliberately.** The backend uploads *as the folder owner's Google account* via `GDRIVE_OAUTH_CLIENT_ID`/`_SECRET`/`_REFRESH_TOKEN`. There is intentionally **no service-account path**: Google 403s service-account uploads to personal My Drive folders (`storageQuotaExceeded`: "Service Accounts do not have storage quota — use shared drives or OAuth delegation"); SA keys only work with Workspace Shared Drives, which the chapter doesn't have — don't re-add one. Mint the refresh token once with `backend/get_drive_refresh_token.py <client_id> <client_secret> [folder name]` (Desktop-app OAuth client; consent screen must be **In production** or refresh tokens die after 7 days). Setup steps live in the README.
- **OAuth is scoped to `drive.file` — one folder only, by design.** The token can only see files/folders the app itself created, never the rest of the owner's Drive. Consequence: `GDRIVE_RESUME_FOLDER_ID` **must** be the app-created folder id printed by `get_drive_refresh_token.py` (the script creates or reuses a folder, default name "SHPE Resume Book") — pointing it at a hand-made folder 404s. The owner can move/rename the folder in Drive freely (sync is id-based), but renaming means a script re-run would create a fresh folder instead of reusing it. Don't "fix" upload 404s by widening the scope to full `drive` — that's the privacy boundary the owner asked for.
- Frontend: viewing fetches the PDF as a **blob** (`getResumeBlob`, `responseType: "blob"`) and opens it with `URL.createObjectURL` — a bearer token can't ride on an `<iframe>`/`<a href>`. `api.js` functions: `uploadResume` (don't set `Content-Type` — let axios add the multipart boundary), `getResumeBlob`, `deleteResume`.
- **Adding a column to an existing table requires migrating `database.db`** — `create_all()` creates missing *tables* (e.g. `passwordresettoken`) but never `ALTER`s an existing table to add a new column, so a new field on `User` (like `resume_filename` or `password_changed_at`) is silently absent from an old db. Symptom: **every** query that selects that model fails with `sqlite3.OperationalError: no such column`, which breaks `/login`, `/me`, and the reminder loop at once. To keep existing data, migrate in place: `sqlite3 backend/database.db "ALTER TABLE user ADD COLUMN <name> <TYPE>;"` (nullable, no default). Only delete the db + re-run `seed.py` when you don't need the current rows. Either way, restart the backend afterward (see auto-memory: recreating the db under a live uvicorn serves stale data / 401s).

## SQLite / datetime note
SQLite stores datetimes as plain text. Store and compare using naive UTC datetimes (`utcnow()` from `services/time_services.py`), not timezone-aware ones. The `Event.start_time` field uses naive UTC. On the frontend, append `'Z'` when constructing a `Date` object so the browser interprets it as UTC: `new Date(event.start_time + 'Z')`.

## Authenticated API calls
New API functions in `api/api.js` read the token from `localStorage` via the internal `authHeaders()` helper — do not pass the token as a parameter (that pattern is only used by the legacy `getMe(token)` function). **Public** endpoints (e.g. `getAllEvents()` → `GET /events`, which powers the public `/calendar` page) must NOT send `authHeaders()`.

## Before Writing Code
1. Check this file for existing patterns — follow them exactly
2. Check the relevant model in `models/` before touching DB logic
3. Check `api/api.js` before making any API call in the frontend
4. If adding a new page, add its route in `App.jsx`
