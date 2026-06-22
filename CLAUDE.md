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
- **Backend:** FastAPI, SQLModel (ORM), SQLite (`database.db`), PyJWT, pwdlib (Argon2 hashing)
- **Auth:** JWT bearer tokens via `/login` and `/signup` endpoints

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
    database.py           # SQLite engine + session factory
    seed.py               # Seeds test user, all 14 committees with their real chairs/co-chairs (22 chair users), and sample events — run once: python seed.py
    routes/               # APIRouters: auth_routes, committee_routes, event_routes (incl. reminders), notification_routes, resume_routes
    uploads/resumes/      # Uploaded resume PDFs, one per user (user_<id>.pdf); gitignored, created on first upload
    models/               # SQLModel table definitions (user/, committee.py, committee_message.py, notification.py, event.py, event_reminder.py)
    security/             # jwt.py (token creation), hashing.py (Argon2)
    services/             # dependencies.py, user_services.py, committee_services.py, reminder_services.py, email_services.py, time_services.py, auth_user.py
    validators/           # email.py (normalize_email)
    tests/                # pytest suite; conftest.py has in-memory-DB fixtures (client, session, user) + make_user/make_event helpers
    .env                  # SECRET_KEY, ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES, optional SMTP_* (never commit)
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

# Optional — reminder emails. Without SMTP_HOST, emails print to the console (dev mode).
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<sender address>
SMTP_PASSWORD=<app password>
EMAIL_FROM=SHPE UH <noreply@example.org>   # optional, defaults to SMTP_USER
```

**Frontend** (`frontend/.env.local`):
```
VITE_API_URL=http://localhost:8000
```
The `api.js` axios instance reads `VITE_API_URL` — without this set, all API calls will fail.

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
- Tailwind v4 is used — do NOT use v3 syntax (e.g. `bg-[color]` utilities are fine, but config is in `tailwind.config.cjs`)

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

## Pages & Routes
| Path | Component | Auth required |
|------|-----------|---------------|
| `/` | `pages/home.jsx` | No |
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
| POST | `/login` | No | Returns JWT token |
| POST | `/signup` | No | Creates user, returns JWT token |
| GET | `/me` | Yes | Returns current user (includes `points`) |
| GET | `/events/upcoming?days=7` | Yes | Upcoming events within N days |
| GET | `/events` | No | All events ordered by start_time (public, powers the calendar) |
| GET | `/committees` | Yes | All committees with `is_member`, `is_chair`, and `chairs` (list of name + email) |
| POST | `/committees/{id}/join` | Yes | Join a committee (notifies the member + every chair) |
| DELETE | `/committees/{id}/leave` | Yes | Leave a committee |
| GET | `/committees/{id}/members` | Yes (chair only) | Roster with name, email, phone; 403 if not the chair |
| POST | `/committees/{id}/messages` | Yes (chair only) | Broadcast a message; notifies every active member |
| GET | `/committees/{id}/messages` | Yes (member or chair) | Committee messages, newest first; 403 otherwise |
| GET | `/notifications` | Yes | Current user's notifications, newest first |
| POST | `/notifications/{id}/read` | Yes | Mark one notification read |
| POST | `/me/resume` | Yes | Upload a PDF resume (multipart `file`); validates PDF type, ext, `%PDF` magic bytes, and ≤5 MB (400/413 otherwise). Sets `User.resume_filename` |
| GET | `/me/resume` | Yes | Download the current user's resume PDF (`FileResponse`); 404 if none |
| DELETE | `/me/resume` | Yes | Remove the current user's resume (204) |
| POST | `/events/{id}/remind` | Yes | Set an email reminder for an event (404 unknown event, 409 already set, 400 already started) |
| DELETE | `/events/{id}/remind` | Yes | Cancel an unsent reminder (404 if none active) |
| GET | `/events/reminders/me` | Yes | Current user's active (unsent) reminders |

## Committee leadership, notifications & messaging
- Committees support **co-chairs**: a committee's chairs are the users with a `CommitteeMembership` row where `is_chair=True` (one row per co-chair). `CommitteeOut.chairs` is a **list** of `ChairOut` (name + email) and `CommitteeOut.is_chair` reflects the current user's membership row.
- `Committee.chair_role` (a `Role` enum value, nullable) still maps each committee to one chair role (1:1). Co-chairs of the same committee **share the same Role** (e.g. both MentorSHPE co-chairs have `Role.mentorshpe_chair`). Chair-only endpoints are gated by `require_chair`, which checks `user.role == committee.chair_role` — so seed both the role on the user AND the `is_chair` membership row, or chairs will display but lack permissions (or vice versa).
- The real chair roster lives in `seed.py` (`COMMITTEE_ROSTER`): 14 committees, 22 chairs. Seeded chair logins are `<first>.<last>@cougarnet.uh.edu` / `password123`.
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

## Profile page & resume uploads
- `pages/profile.jsx` (route `/profile`, in the member dropdown under Committees) shows the signed-in user's info **read-only** (no editing) plus a resume section. It reads everything from `useAuth().user` (the `/me` payload) and tracks resume state locally.
- Resumes are **PDF only** and **private to the owner** (no chair/other-user access). `User.resume_filename` (nullable, on the `User` table model — NOT `UserBase`, so signup is untouched) stores the original name; `UserOut` exposes it so the frontend knows whether a resume exists. The PDF lives on disk at `backend/uploads/resumes/user_<id>.pdf` (deterministic → re-upload overwrites).
- `routes/resume_routes.py` validates uploads (PDF content-type + `.pdf` ext + `%PDF` magic bytes, ≤5 MB) and serves the file via `FileResponse`. Storage dir is `RESUME_DIR` (a module constant) — tests monkeypatch it to a `tmp_path` to stay hermetic.
- Frontend: viewing fetches the PDF as a **blob** (`getResumeBlob`, `responseType: "blob"`) and opens it with `URL.createObjectURL` — a bearer token can't ride on an `<iframe>`/`<a href>`. `api.js` functions: `uploadResume` (don't set `Content-Type` — let axios add the multipart boundary), `getResumeBlob`, `deleteResume`.
- **Adding the `resume_filename` column requires recreating `database.db`** — `create_all()` does not `ALTER` existing tables (delete the db, re-run `seed.py`, restart the backend).

## SQLite / datetime note
SQLite stores datetimes as plain text. Store and compare using naive UTC datetimes (`utcnow()` from `services/time_services.py`), not timezone-aware ones. The `Event.start_time` field uses naive UTC. On the frontend, append `'Z'` when constructing a `Date` object so the browser interprets it as UTC: `new Date(event.start_time + 'Z')`.

## Authenticated API calls
New API functions in `api/api.js` read the token from `localStorage` via the internal `authHeaders()` helper — do not pass the token as a parameter (that pattern is only used by the legacy `getMe(token)` function). **Public** endpoints (e.g. `getAllEvents()` → `GET /events`, which powers the public `/calendar` page) must NOT send `authHeaders()`.

## Before Writing Code
1. Check this file for existing patterns — follow them exactly
2. Check the relevant model in `models/` before touching DB logic
3. Check `api/api.js` before making any API call in the frontend
4. If adding a new page, add its route in `App.jsx`
