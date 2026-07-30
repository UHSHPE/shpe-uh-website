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
- **Auth:** JWT bearer tokens via `/login`; `/signup` creates an **unverified** account and emails a verification link (no token returned) — the account can't log in until `/verify-email` confirms it. Self-service password reset via `/password-reset/*`

## Project Structure
```
shpe-uh-website/
  frontend/
    src/
      api/api.js          # Axios instance (baseURL from VITE_API_URL env var)
      components/         # Header, Footer, Avatar, GalleryApproved, PrivateRoute, CartDrawer, ProductImage, StatusPill, MyOrders, ShopManager, shopIcons, DuesBanner
      context/            # AuthContext, CartContext (cart lines + drawer + toast, persisted to localStorage)
      utils/shop.js       # formatCents, STATUS_META, isShopManager, isPresident, order helpers
      utils/dues.js       # DUES_PRODUCT_NAME + startDuesCheckout (shared by verify-email + DuesBanner)
      pages/              # home, about, gallery, membershpe, sponsors, get-involved, dashboard, committees, profile, members, shop-manager, shop, shop-product, shop-checkout, shop-order, verify-email
      App.jsx             # Routes (+ renders CartDrawer/ShopToast globally)
  backend/
    main.py               # FastAPI app: includes routers + background loops (reminder emails every 60s, event-sheet sync daily at 6 AM Central)
    get_drive_refresh_token.py  # One-time helper: mints the OAuth refresh token AND creates the app-owned resume folder (drive.file scope)
    database.py           # SQLite engine + session factory
    seed.py               # Seeds two test users (test@ dues-paid via a seeded order, test1@ unpaid), all 14 committees with their real chairs/co-chairs (22 chair users), a comms director (shop admin), the president (Daniel Lopez Gil — full admin), the shop-settings row, 5 shop products (incl. T-Shirt Dues), and sample events — run once: python seed.py. Refuses to run (exit 1) when ENVIRONMENT=production — all seeded accounts share password123
    routes/               # APIRouters: admin_routes (president-only), auth_routes, committee_routes, event_routes (incl. reminders), notification_routes, pw_reset_routes, resume_routes, shop_routes
    uploads/resumes/      # Uploaded resume PDFs, one per user (user_<id>.pdf); gitignored, created on first upload
    uploads/products/     # Product images, one per product (product_<id>.<ext>); gitignored, created on first upload
    models/               # SQLModel table definitions (user/ incl. pw_reset_token.py, email_verification.py, shop/ (product.py, order.py, shop_settings.py), committee.py, committee_message.py, notification.py, event.py, event_reminder.py)
    security/             # jwt.py (token creation), hashing.py (Argon2)
    services/             # dependencies.py, user_services.py, committee_services.py, reminder_services.py, email_services.py, drive_services.py, time_services.py, auth_user.py, pw_reset_services.py, rate_limit.py, shop_services.py, square_services.py, hibp_services.py, event_tracker_services.py
    validators/           # email.py (normalize_email)
    tests/                # pytest suite; conftest.py has in-memory-DB fixtures (client, session, user) + make_user/make_event helpers; shop_tests/conftest.py adds manager_client/make_product/sent_emails; admin_tests/conftest.py adds president_client/make_president/make_dues_order; event_tracker_tests/ covers the sheet parser + sync
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

# Set ONLY on the live server. Flips the dev-mode fallbacks to fail closed:
# startup (assert_production_config in main.py, called from lifespan) refuses
# to boot unless SQUARE_* + SMTP_HOST are set and SQUARE_ENVIRONMENT=production;
# charge_card raises instead of simulating; seed.py refuses to run.
# Leave unset for local dev and tests.
ENVIRONMENT=production

# Optional — reminder emails. Without SMTP_HOST, emails print to the console (dev mode).
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=<sender address>
SMTP_PASSWORD=<app password>
EMAIL_FROM=SHPE UH <noreply@example.org>   # optional, defaults to SMTP_USER

# Optional — Square card payments for the shop. Without these, checkout runs
# in simulated dev mode (console-printing no-op charge). Setup steps in README.
SQUARE_ACCESS_TOKEN=<from developer.squareup.com>
SQUARE_LOCATION_ID=<location id of the same Square application>
SQUARE_ENVIRONMENT=sandbox   # or "production"; must match the token

# Optional — Google Drive resume sync. Without folder id + credentials set,
# Drive sync is a console-printing no-op (dev mode). Setup steps in README.
GDRIVE_RESUME_FOLDER_ID=<app-created folder id printed by get_drive_refresh_token.py — NOT a hand-made folder's id>
GDRIVE_OAUTH_CLIENT_ID=<OAuth Desktop-app client id>
GDRIVE_OAUTH_CLIENT_SECRET=<OAuth client secret>
GDRIVE_OAUTH_REFRESH_TOKEN=<minted once via get_drive_refresh_token.py>

# Optional — event tracker Google Sheet sync. Without both set, the daily sync
# is a console-printing no-op (dev mode) and the calendar keeps whatever is
# already in the DB. Both are read at call time by is_configured().
CREDENTIALS=<path to the Google service-account JSON key file>
SHEET_ID=<id of the event-tracker spreadsheet, from its URL>
```

**Frontend** (`frontend/.env.local`):
```
VITE_API_URL=http://localhost:8000
VITE_BEHOLD_FEED_URL=https://feeds.behold.so/<feed-id>   # public Behold JSON feed for the home-page Instagram grid
VITE_SQUARE_APP_ID=<Square application id>       # optional — unset keeps checkout simulated
VITE_SQUARE_LOCATION_ID=<Square location id>     # must match the backend's SQUARE_LOCATION_ID
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
- Do not call setState synchronously inside a `useEffect` body — the lint config (react-hooks/set-state-in-effect) fails the build. For "reset state when a prop/route param changes" or "prefill once async data arrives", use the render-phase adjustment pattern (compare-and-set during render, like `Header.jsx`'s `prevPath` and `shop-checkout.jsx`'s prefill)
- Do not export helpers/constants from a file that also exports a React component — react-refresh lint fails. Put shared helpers in `utils/` and components in their own files (this is why `StatusPill` is its own component and `utils/shop.js` has no JSX)
- The lint config's `no-unused-vars` only ignores identifiers matching `^[A-Z_]`, and usage inside JSX (like `<motion.div>`) doesn't count — so any file importing lowercase `motion` from framer-motion needs `/* eslint-disable no-unused-vars */` at the top (Header.jsx, profile.jsx, members.jsx all do this)
- Do not put digits (or other symbols) in seeded/test user names — `UserCreate`'s name validator allows only letters, hyphens, apostrophes, and spaces, so a first_name like `Test1` crashes `seed.py` mid-run. Put distinguishing digits in the email instead (that's why the unpaid test member is "Test Unpaid" / `test1@cougarnet.uh.edu`)
- Do not add a delete/sweep pass to `sync_events` — the duplicate left behind by a rescheduled event is intentional (see "Event tracker sheet sync"); deleting silently kills reminders and resets points
- Do not hard-delete a shop `Product` (and do not unlink its image when retiring) — `DELETE /shop/products/{id}` is a **soft delete**; destroying the row breaks restore and throws away the image a restore needs (see "Merch shop")
- Do not pair `.catch(() => {})` with a success toast in the frontend — the user sees "saved" when nothing saved. Surface `err.response?.data?.detail` via `showToast` like `saveProduct`/`retireProductRow` do
- Do not use a Google **service account** to upload to a personal My Drive folder — Google 403s it (`storageQuotaExceeded`); use the OAuth refresh-token credentials instead (see "Google Drive resume sync")

## Pages & Routes
| Path | Component | Auth required |
|------|-----------|---------------|
| `/` | `pages/home.jsx` | No |
| `/forgot-password` | `pages/forgot-password.jsx` | No |
| `/reset-password` | `pages/reset-password.jsx` (token via `?token=`) | No |
| `/verify-email` | `pages/verify-email.jsx` (token via `?token=`; verifies then routes into dues checkout) | No |
| `/about` | `pages/about.jsx` | No |
| `/membershpe` | `pages/membershpe.jsx` | No |
| `/sponsors` | `pages/sponsors.jsx` | No |
| `/gallery` | `pages/gallery.jsx` | No |
| `/calendar` | `pages/calendar.jsx` | No |
| `/get-involved` | `pages/get-involved.jsx` (commented out) | No |
| `/shop` | `pages/shop.jsx` (public storefront) | No |
| `/shop/:productId` | `pages/shop-product.jsx` (product detail) | No |
| `/shop/checkout` | `pages/shop-checkout.jsx` (contact → payment: Square card element when `VITE_SQUARE_*` set, simulated otherwise) | No |
| `/shop/order/:code` | `pages/shop-order.jsx` (confirmation + status; lookup needs buyer email) | No |
| `/dashboard` | `pages/dashboard.jsx` | Yes (PrivateRoute) |
| `/committees` | `pages/committees.jsx` | Yes (PrivateRoute) |
| `/profile` | `pages/profile.jsx` | Yes (PrivateRoute) |
| `/members` | `pages/members.jsx` (president only; non-presidents → `/dashboard`) | Yes (PrivateRoute) |
| `/shop-manager` | `pages/shop-manager.jsx` (shop admins only; non-managers → `/dashboard`) | Yes (PrivateRoute) |

## Protected Routes
`components/PrivateRoute.jsx` wraps any route that requires authentication. If `token` is null it redirects to `/signin` preserving the intended destination in `location.state.from`. After sign-in the user is forwarded to that destination (or `/dashboard` by default).

## Backend API Endpoints
| Method | Path | Auth | Description |
|--------|------|------|-------------|
| POST | `/login` | No | Returns JWT token (rate limited: 5/minute per IP); 403 if the account's email isn't verified; 429 while the account is locked (10 failed attempts → 10-min lock) |
| POST | `/signup` | No | Creates an **unverified** user and emails a verification link to cougarnet_email; returns a generic message, **not** a JWT (rate limited: 5/hour per IP). A signup for an existing *unverified* email reclaims it (deletes the pending account + child rows); only a *verified* email 409s |
| POST | `/verify-email` | No | Confirms a signup with the token from the email (`{"token": raw}`); marks `email_verified=True` and returns a JWT. Single-use, 24h TTL, generic 400 for unknown/used/expired/orphaned tokens |
| POST | `/password-reset/request` | No | Always 200 with a generic body; if the account exists, emails a single-use reset link to cougarnet_email (rate limited: 3/hour per IP) |
| POST | `/password-reset/confirm` | No | Sets a new password from a valid token; generic 400 for unknown/used/expired tokens |
| GET | `/me` | Yes | Returns current user (includes `points` and computed `has_paid_dues`) |
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
| GET | `/shop/settings` | No | Shop settings singleton (tagline + `order_item_cap`) — the storefront reads both |
| PATCH | `/shop/settings` | Shop admin | Update tagline and/or per-order item cap |
| GET | `/shop/products` | No | Active, non-retired products only, ordered by created_at |
| GET | `/shop/products/{id}` | No | One product; 404 for unknown OR inactive OR retired |
| GET | `/shop/products/{id}/image` | No | Product image (FileResponse) |
| POST | `/shop/orders` | Optional | Charge card via Square (402 + no order on decline; dev-mode no-op when unconfigured), then create order (rate limited 10/minute); server recomputes total and charges exactly that; links `user_id` if a valid bearer token rides along |
| GET | `/shop/orders/me` | Yes | Signed-in member's order history (defined BEFORE `/orders/{code}` so "me" isn't swallowed) |
| GET | `/shop/orders/{code}?email=` | No | Buyer lookup; wrong/unknown code or email → one generic 404 |
| POST | `/shop/products` | Shop admin | Create product (201) |
| PATCH | `/shop/products/{id}` | Shop admin | Edit / toggle `is_active` (never touches `retired_at`) |
| DELETE | `/shop/products/{id}` | Shop admin | **Retire** (soft delete, 204): stamps `retired_at`, forces `is_active=False`, keeps the row + image. Idempotent; 400 for the dues product |
| POST | `/shop/products/{id}/restore` | Shop admin | Clear `retired_at` (200 `ProductOut`); leaves `is_active` False. Idempotent; 404 unknown |
| POST | `/shop/products/{id}/image` | Shop admin | Upload PNG/JPEG/WebP ≤5 MB (magic-byte checked) |
| GET | `/shop/admin/products` | Shop admin | All products incl. hidden AND retired (admin table) |
| GET | `/shop/orders?status=` | Shop admin | All orders, filterable by status |
| PATCH | `/shop/orders/{id}` | Shop admin | `{status?, notes?}`; illegal transition → 400; `ready` emails buyer |
| GET | `/admin/members?search=&paid=&role=` | President | Member directory (AdminMemberOut incl. has_paid_dues); search matches name/either email/PSID |
| GET | `/admin/stats` | President | Totals: accounts, dues paid/unpaid, national members, dues_period_start, classification/role/shirt-size counts |
| GET | `/admin/roles` | President | All assignable Role values (frontend dropdown source) |
| PATCH | `/admin/members/{id}/role` | President | `{role}`; 404 unknown user, 400 changing own role; chair roles sync CommitteeMembership.is_chair |

## President role & chapter admin
- **`Role.president` is the site-wide admin** — it was already in the Role enum; what's wired to it: membership in `SHOP_ADMIN_ROLES` (full shop manager), a bypass in `require_chair` + message access (every committee's chair tools), and the president-only `/admin/*` endpoints (`routes/admin_routes.py`, gated by `require_president` in `services/dependencies.py`, which mirrors `require_shop_admin`).
- **`/committees` reports `is_chair: true` on every committee for the president** (computed in the route, no membership rows involved) so the frontend Committees page shows the Manage panel everywhere. The president usually has `is_member: false` — the card then also shows a Join button; that's expected.
- **Role assignment must keep chair rows in sync**: chair permissions need BOTH `user.role == committee.chair_role` AND an `is_chair` membership row. `_sync_chair_memberships` in `admin_routes.py` handles both directions — assigning a chair role creates/reactivates the `is_chair` membership; removing one clears `is_chair` but keeps them as a regular member. Don't add another role-mutation path without it.
- **The president cannot change their own role** (400) — prevents self-lockout; handoff = promote the successor to President first (two presidents can coexist briefly), then they demote you.
- Admin schemas (`AdminMemberOut`, `AdminRoleUpdate`, `AdminStatsOut`) live in `models/user/user_schemas.py`. `AdminMemberOut` skips the multi-select lists, so it has no ≥1-row requirement (unlike `UserOut` — bare `make_user` fixtures serialize fine). Batch dues status comes from `shop_services.dues_paid_user_ids()` (one query, not per-member `has_paid_dues`).
- Frontend: `utils/shop.js` has `isPresident()` + `PRESIDENT_ROLE`, and its `SHOP_ADMIN_ROLES` string list includes `"President"`. `pages/members.jsx` (route `/members`) guards with `isPresident` and fetches members/stats/roles once, filtering client-side (new `api/api.js` functions: `getAdminMembers`, `getAdminStats`, `getAssignableRoles`, `updateMemberRole`); `Header.jsx`'s `memberLinksFor` inserts the Members tab (president) and Shop Manager tab (any shop admin) after Committees; the profile hero badge shows "★ President" instead of "★ Shop Manager" for the president.
- **Controlled `<select>` + `window.confirm` gotcha** (members.jsx role dropdown): if the confirm is cancelled, React state never changes so it won't repaint, but the DOM select already shows the new option — reset `e.target.value` manually in the onChange handler.
- Seeded president: **Daniel Lopez Gil** (matches the About page E-Board), `daniel.lopez.gil@cougarnet.uh.edu` / `password123`.
- Tests in `tests/admin_tests/` (`president_client` fixture — same "don't mix with `client` in one test" rule as `manager_client`).

## Committee leadership, notifications & messaging
- Committees support **co-chairs**: a committee's chairs are the users with a `CommitteeMembership` row where `is_chair=True` (one row per co-chair). `CommitteeOut.chairs` is a **list** of `ChairOut` (name + email) and `CommitteeOut.is_chair` reflects the current user's membership row.
- `Committee.chair_role` (a `Role` enum value, nullable) still maps each committee to one chair role (1:1). Co-chairs of the same committee **share the same Role** (e.g. both MentorSHPE co-chairs have `Role.mentorshpe_chair`). Chair-only endpoints are gated by `require_chair`, which checks `user.role == committee.chair_role` (the **president bypasses this check** — full admin) — so seed both the role on the user AND the `is_chair` membership row, or chairs will display but lack permissions (or vice versa).
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

## Event tracker sheet sync
- `services/event_tracker_services.py` pulls the chapter's event-tracker Google Sheet (gspread, **read-only** `spreadsheets.readonly` scope, service-account creds via `CREDENTIALS` + `SHEET_ID`) and reconciles it into the `Event` table. `main.py` runs `sync_events` in a background asyncio loop that fires **daily at 6 AM Central** (`SYNC_HOUR` + `seconds_until_next_sync`, started in `lifespan`). Unconfigured = dev-mode no-op: `fetch_sheet_events()` prints and returns `[]`.
- **Identity is `Event.source_row_id` = `event_key(date, title)` → `"2026-08-05|gbm 1"`** (ISO date + lowercased, whitespace-collapsed name). This is the *join* between a sheet row and a DB row — the auto-increment `Event.id` can't serve that role because the sheet has no column holding it, so without the key every sync would re-insert everything. The column is `index=True, unique=True`; **NULLs stay exempt** (SQL unique indexes treat NULLs as distinct), which is what lets `seed.py` and hand-added events coexist.
- **There is deliberately NO delete/sweep pass** — rows are only created or updated. All of the following are accepted tradeoffs, not bugs:
  - **Rescheduling adds a row instead of moving one.** A new date means a new key, so the old row stays behind and the calendar shows both. Chosen over a sweep because delete+reinsert mints a new `Event.id`, which silently orphans `EventReminder` rows (the join in `send_due_reminders` simply stops matching — no email, no error, and the calendar button resets as if the member never set it) and resets `points_value`/`event_type`, neither of which exists in the sheet. A visible duplicate someone fixes by hand beat a silent failure.
  - **Renames behave the same way** — the name is half the key.
  - **Deleting a sheet row does not remove the event.** The chapter confirmed nobody deletes rows.
  - If a sweep is ever added, it MUST scope to `source_row_id IS NOT NULL`, bail out when the fetch returns zero rows (an unconfigured or failed fetch returns `[]`, which would otherwise wipe the entire calendar), and decide what happens to existing reminders.
- `EXCLUDED_EVENTS` (normalized names, e.g. `"c&e retreat"`) are dropped in `parse_row` before the date is even parsed. **One-way door:** because nothing deletes, an event already synced before its name was added to the set stays in the DB forever.
- Row handling: the header row and the row-2 template row are skipped (`get_all_records()[1:]`), and a per-row `try/except` isolates failures so one unparseable date doesn't kill the batch. Note `parse_row` reads DATE with direct indexing (`row[COLUMNS["date"]]`), so renaming that sheet header would make **every** row raise, get swallowed, and log a cheerful "0 created, 0 updated" while doing nothing.
- Times: `parse_time` returns None for blank / `All Day` / `TBD`, so those events fall back to **local midnight**. `end_time` is built from the same `day` as the start — an event crossing midnight would store an end *before* its start. Confirmed no chapter events run past midnight; revisit if that changes.
- `parse_date` stamps the **current Central year** onto the sheet's MM/DD values. This is correct in normal use because the trackers are **semester-scoped** — the fall sheet runs Aug–Dec and spring is a separate sheet (Jan–May), so every row in one pull shares a calendar year. Do NOT "fix" this by adding a year column; it isn't needed.
- **The one hazard is `SHEET_ID` still pointing at the fall sheet on January 1.** The 6 AM sync then re-reads `09/15` as September of the *new* year, minting a new key for every row and inserting the entire fall semester as ghost events dated a year out — which persist, since nothing deletes. Either swap `SHEET_ID` to the spring sheet before January, or make `parse_date` anchor to the academic year (`now.year` if `now.month >= 8` else `now.year - 1`; months 8–12 take the anchor, 1–7 take anchor + 1), which keeps `09/15` at 2026 even when read in January 2027.
- Duplicate keys inside one pull collapse to one row: the first row is `session.add()`-ed but still pending, and the second row's existing-lookup SELECT triggers SQLAlchemy's autoflush, which writes the first INSERT before the query runs — so the second row finds it and updates in place. Result is `(created, updated) == (1, 1)` and one row holding the *second* row's values, no `IntegrityError`.
- Tests live in `tests/event_tracker_tests/` (`test_event_parsing.py`, `test_event_sync.py`) and use two deliberate seams: `fetch_sheet_events` tests monkeypatch `get_worksheet` with a fake worksheet so the real parse path runs, while `sync_events` tests monkeypatch `fetch_sheet_events` directly so they only exercise DB reconciliation. An autouse `disable_event_tracker_sync` fixture in `tests/conftest.py` clears `CREDENTIALS`/`SHEET_ID` — same `load_dotenv()` leak problem as the Drive and Square fixtures.

## Merch shop (spec: specs/shop/shop-page.md)
- **Payments — Square Web Payments SDK + Payments API** (`services/square_services.py`). Configured via `SQUARE_ACCESS_TOKEN` + `SQUARE_LOCATION_ID` (+ `SQUARE_ENVIRONMENT`, default sandbox — all read at **call time**) on the backend, `VITE_SQUARE_APP_ID` + `VITE_SQUARE_LOCATION_ID` on the frontend. The checkout page loads `square.js` from Square's CDN (required — it serves the secure card iframe; sandbox vs prod build is picked by the `sandbox-` app-id prefix), renders the card element in the payment step, and `card.tokenize()` swaps card data for a one-time token — card numbers never touch our server (PCI stays minimal). No webhooks: the charge response is synchronous.
- **Charges are itemized in Square** via the Orders API: the route mirrors the validated cart into `line_items` (`{"name": "Product (Size)", "quantity", "unit_price_cents"}`) and `charge_card` creates a Square order from them (`_create_itemized_order`), then passes its id as `order_id` to `payments.create` — the Dashboard shows per-item detail and item names flow into Square's sales reports. Gotchas: the Orders API wants `quantity` as a **string**; the line items must **sum exactly to the charged amount** or Square rejects the payment (guaranteed by construction — both come from the same validated lines); itemization is best-effort — if order creation fails, it logs and charges un-itemized rather than blocking the buyer. These are ad-hoc line items (no Square Catalog sync); if per-item unit counts in Square's Item reports ever need to be exact across renames, the upgrade path is mirroring products into the Square Catalog and passing `catalog_object_id`.
- **Charge order-of-operations in `POST /shop/orders`: validate → charge → persist.** The route calls `shop_services.validate_order_items` (returns `(lines, total_cents)` without persisting), charges that server-side total via `square_services.charge_card`, then passes the same `validated` pair into `create_order` so the stored total always equals the charged amount. A declined/failed charge raises `PaymentError` (buyer-safe message) → 402 with **no order row**; missing token while configured → 400 before any charge. `charge_card` returns a `ChargeResult(payment_id, receipt_url)` NamedTuple (None in dev mode): `Order.square_payment_id` records the payment id (internal — NOT in `OrderOut`), and `receipt_url` goes into the buyer's receipt email. The route is sync, so the blocking Square client already runs in FastAPI's threadpool — if it's ever made `async def`, wrap the charge in `asyncio.to_thread`.
- **Wallets (Apple Pay / Google Pay)** ride the same flow — no backend changes. The payment-step effect builds a `paymentRequest` (display amount only; the backend still charges its own recomputed total) and tries `payments.applePay()` / `payments.googlePay()`; each **throws where unsupported** (Apple Pay: sandbox, non-Safari, unregistered domain — expected, not a bug) and its button just stays hidden. `handlePay(walletMethod)` tokenizes whichever method is passed (the card element when null); a wallet-sheet `Cancel` result is silently ignored. Gotchas: the `#google-pay-button` container must exist in the DOM **before** `attach()` (it renders always, `display:none` until ready); the Apple Pay button is our own `<button className="applePayBtn">` (native `-apple-pay-button` vendor appearance — CSS lives in `styles.css`, Tailwind can't express it); the init effect depends on `[step, subtotalCents]` so a cart change rebuilds the paymentRequest. Going live with Apple Pay needs a one-time domain registration (Square Developer Dashboard → Apple Pay) + hosting Square's verification file at `frontend/public/.well-known/apple-developer-merchantid-domain-association`.
- **Unconfigured = dev mode, end to end** (same pattern as `email_services.py`): `charge_card` prints `[square dev mode] would charge …` and returns None, orders are created with `square_payment_id=None`, and the frontend keeps the demo card block + fake 1.3s delay. **Except when `ENVIRONMENT=production`** — then the dev-mode fallback is a security hole (silent free orders), so `main.py`'s `assert_production_config()` (first line of `lifespan`) refuses to boot with missing Square/SMTP config or a sandbox `SQUARE_ENVIRONMENT`, and `charge_card` raises `RuntimeError` (→ 500, no order row) instead of simulating. Keep any new dev-mode no-op behind the same flag. Tests never hit the real API: an autouse `disable_square_payments` fixture in `tests/conftest.py` **imports `main` first, then** clears all `SQUARE_*` env vars — the order matters: the client fixtures lazily `from main import app`, and the session's FIRST such import runs every route module's `load_dotenv()`, re-leaking `backend/.env` into `os.environ` mid-test (this bit once: shop-only test runs 400'd on "missing payment token" while full-suite runs passed, because auth tests absorbed the first import); configured-mode tests monkeypatch `square_services.is_configured`/`charge_card` (called as module attributes from `shop_routes`, so patching `services.square_services` works). Dep: `squareup` (lazy-imported inside `square_services.py`, so dev mode works without it).
- **Models** (`models/shop/`): `Product` (with `ProductType` enum `apparel`/`item`; `sizes` is a `list[str] | None` stored via `sa_column=Column(JSON)`; there is **no stock column** — no inventory is tracked; `is_active` = currently offered, `retired_at` = soft delete, see below), `Order` + `OrderItem` (`OrderStatus`: `paid → ready → picked_up`, plus `cancelled`; terminal is `picked_up`, NOT `completed`), and `ShopSettings` (singleton row: `tagline` + `order_item_cap`, defaults in the model; always access via `shop_services.get_shop_settings()`, which creates the row on first use). Money is integer **cents**; timestamps naive UTC via `utcnow()`. All three modules are imported in `database.py`.
- **Product lifecycle is three-state — `is_active` (offered?) × `retired_at` (soft delete?).** `retired_at IS NULL` + `is_active=True` → listed and orderable; NULL + False → hidden (admin Products table, "Hidden" pill, restorable to Active by the toggle); `retired_at` set → forced `is_active=False`, gone from `GET /shop/products` and 404 on the detail route, parked in the admin's collapsible **Retired** section. **No product row is ever destroyed** — `DELETE /shop/products/{id}` retires instead of deleting (`retire_product` in `shop_routes.py`), so `OrderItem` snapshots, the on-disk image, and any future restore all survive; **do not re-add a hard delete or an image unlink there**. Restore clears `retired_at` and deliberately **leaves `is_active` False** so nothing silently reappears on the storefront. Both ops are idempotent (retiring twice does not re-stamp `retired_at`). `ProductCreate`/`ProductUpdate` deliberately do **not** expose `retired_at` — retire/restore are dedicated endpoints so a stray PATCH field can't archive a product. `ProductOut` does expose it (always null on public responses; the admin table partitions on it). **Dues guard:** retiring `shop_services.DUES_PRODUCT_NAME` 400s — the post-verification dues checkout looks that product up by name, so retiring it would break signup with no other symptom (same fragility as renaming it). **Migration:** an existing `database.db` needs `sqlite3 backend/database.db "ALTER TABLE product ADD COLUMN retired_at DATETIME;"` — without it every `Product` query dies with `no such column`. Tests build the schema with `create_all()`, so they need nothing.
- **Per-order quantity cap** (no inventory): `create_order` rejects any line item whose quantity exceeds `ShopSettings.order_item_cap` (default 5) with a 400. Admins change the cap (and the storefront tagline) via `PATCH /shop/settings`; the frontend `CartContext` fetches the cap once and clamps add-to-cart and the steppers client-side.
- **`OrderItem` snapshots `product_name` and `unit_price_cents`** at purchase time, so orders stay readable after a product is edited or retired.
- **Order codes**: `SHPE-` + 4 chars from an alphabet without lookalikes (no 0/O/1/I) — `generate_order_code` retries until unique.
- **State machine** lives in `shop_services.ALLOWED_TRANSITIONS`; `apply_status_transition` stamps `ready_at`/`picked_up_at` and emails the buyer on `ready`. New orders create a `Notification` row + email for **every shop admin** (to their `personal_email`); the buyer also gets an **itemized receipt email at order time** (`shop_services.send_buyer_receipt` — sent to `buyer_email`, which checkout prefills with `personal_email`; includes Square's hosted `receipt_url` link when the charge was real).
- **Roles**: there is **no dedicated shop-manager role**. Shop admin rides on `SHOP_ADMIN_ROLES = {Role.comm_director, Role.marketing_chair, Role.president}` (defined in `models/user/user_enums.py`); `require_shop_admin` in `services/dependencies.py` gates admin endpoints (mirrors `require_chair`). Giving `marketing_chair` shop access does NOT affect their committee-chair permissions (`require_chair` checks `role == committee.chair_role`, still true). Seed provides `comms.director@cougarnet.uh.edu` (comm_director), Valeria Zabala (`valeria.zabala@cougarnet.uh.edu`, marketing_chair from COMMITTEE_ROSTER), and the president (`daniel.lopez.gil@cougarnet.uh.edu`), all `password123`.
- **`get_optional_user`** in `services/dependencies.py` (`OAuth2PasswordBearer(auto_error=False)`): returns the user for a valid token, None otherwise (never 401s). Used by `POST /shop/orders` so signed-in buyers' orders link to `user_id`. In tests, override it explicitly — the `client` fixture only overrides `get_current_user`.
- **Order lookup privacy**: `GET /shop/orders/{code}` requires a matching `?email=` (normalized); unknown code and wrong email return the same generic 404. Never reveal a code exists.
- **Route ordering**: `/shop/orders/me` is defined before `/shop/orders/{order_code}` in `shop_routes.py` — keep it that way or "me" matches the code param.
- **Product images** mirror the resume pattern: `PRODUCT_IMAGE_DIR` module constant (tests monkeypatch it to `tmp_path`), deterministic filename `product_<id>.<ext>`, content-type + magic-byte + ≤5 MB validation (PNG/JPEG/WebP).
- **Tests** in `tests/shop_tests/`; its `conftest.py` adds `manager_client` (auth'd as a `Role.comm_director` user — pass `role=Role.marketing_chair` to `make_manager` to cover the other admin role), `make_product`, and `sent_emails` (monkeypatches `shop_services.send_email`). Do NOT use `client` and `manager_client` in the same test — both override `get_current_user` on the same app and the last fixture wins.
- **Dues after email verification**: dues checkout now fires from the **verify-email page** (`pages/verify-email.jsx`), not signup — because the buyer must be signed in to pay and they aren't signed in until they verify. After `/verify-email` returns a JWT, the page logs the member in, fetches `/me` for their `shirt_size`, then calls `startDuesCheckout` (shared helper in `utils/dues.js`). It finds the shop product **by name `"T-Shirt Dues"`** (`DUES_PRODUCT_NAME`; matches `seed.py` and the membershpe tier card), adds it pre-sized to the cart (`openDrawer: false`), and navigates to `/shop/checkout`. Shirt size `Other` (or a size the product lacks) lands on the dues product page to pick a size; a missing/renamed product or shop error falls back to `navigate("/")` — verification never blocks on the shop. **Renaming the dues product silently breaks the auto-redirect** (name-based lookup, no schema flag). `signup.jsx` itself just shows a "check your email" screen and no longer touches the cart.
- **Dues rules & banner**: dues are **one per member per membership year, enforced server-side** — `shop_services.enforce_dues_rules` (called in `place_order` after validation, before charging) caps dues quantity at 1 per order, rejects guests (the purchase must attach to an account), and 400s a repeat purchase **within the current period**; a **cancelled** dues order doesn't count as paid (`has_paid_dues` matches on the `OrderItem.product_name` snapshot, so it survives product edits/retires). **Yearly reset**: dues reset every **May 30** — `has_paid_dues` only counts non-cancelled dues orders with `created_at >= current_dues_period_start()` (the most recent May 30, this year's if today is on/after it else last year's), so after the reset `has_paid_dues` flips back to False, the banner returns, and the member owes dues again. Change the reset date via `DUES_RESET_MONTH`/`DUES_RESET_DAY`. The cart also enforces one dues item client-side (`CartContext` `lineCap()` returns 1 for the dues product regardless of the shop-wide item cap). `UserOut.has_paid_dues` is **computed in `/me`** (not a DB column) and drives `components/DuesBanner.jsx` — a fixed red banner just below the header (top `var(--header-height)`, z-index 900 < header's 1000) shown to signed-in members who haven't paid, listing the benefits; its CTA and the signup redirect share `utils/dues.js` (`startDuesCheckout`). `shop-checkout` calls `AuthContext.refreshUser()` after a successful order so the banner clears without a reload; the dues product page locks the quantity stepper to 1 and swaps the add-to-cart button for an already-paid note. NOTE: `/me` fails validation for users with zero multi-select rows (UserOut requires ≥1 of each) — tests hitting `/me` must seed those rows (see `test_dues_rules.py::test_me_reports_dues_status`).
- **Frontend**: cart state lives in `context/CartContext.jsx` (localStorage key `shpe_cart`, lines merge by product+size, drawer + 2s toast included); `CartDrawer`/`ShopToast` render once in `App.jsx`. Category filter pills on `/shop` are derived from the `product_type`s present — never hardcode "Stickers". `createShopOrder` sends `authHeaders()` (empty for guests) so member orders link. After checkout the confirmation gets the order via route state; revisits look it up with code+email from sessionStorage (`shpe_last_order`), `?email=`, or a prompt. `/shop` has **no sold-out state** — `GET /shop/products` already filters hidden and retired products out, and the chapter fulfils per order, so the card renders the price unconditionally (the old "Sold out" badge/price branch was dead code and was removed; don't re-add it). The Shop Manager panel (`components/ShopManager.jsx` — Overview / Products / Orders / Notifications / Settings tabs) lives on its **own page** `pages/shop-manager.jsx` at route `/shop-manager` (moved off the profile page). The page guards with `isShopManager(user)` (from `utils/shop.js`, matches the `SHOP_ADMIN_ROLES` strings — covers comm_director + marketing_chair + president) and `<Navigate to="/dashboard">`s signed-in non-managers; `Header.jsx` shows a "Shop Manager" member-dropdown/mobile tab (via `memberLinksFor(user)`) only to managers. Its **Products** tab renders live products only (status pill reads "Active"/"Hidden"), with a collapsible **Retired (N)** section under the table: dimmed rows, a gray `--status-cancelled-*` "Retired" pill, and a **Restore** button in place of the trash icon — no edit button and no active-toggle on retired rows (restore first). `api.js` shop-admin functions are `retireProduct` (renamed from `deleteProduct`, same `DELETE` path) and `restoreProduct`; both handlers surface `err.response?.data?.detail` via `showToast` (the old `removeProduct` swallowed errors with `.catch(() => {})` and faked success — don't reintroduce that). `components/MyOrders.jsx` still lives on `pages/profile.jsx`, at the **bottom**, showing only the **most recent** order (orders arrive newest-first) with the rest behind a "Show all N orders" toggle; profile keeps a "★ Shop Manager" hero badge for admins. The `/shop` hero tagline comes from `GET /shop/settings` with a hardcoded product-agnostic fallback.
- **Shop styling tokens** (page bg, gray ramp additions, the four status color sets `--status-*`, `--gradient-success`, `--font-mono`, `--placeholder-hatch`) are in `styles.css` `:root` under "Shop"; keyframes are prefixed `shop*` (`shopPulse`, `shopSlideInRight`, …). The design handoff lives in `specs/shop/design_handoff_merch_shop/`.

## Email verification at signup
- `models/user/email_verification.py` — `EmailVerificationToken(user_id, token_hash, created_at, expires_at, used_at)`, same shape as `PasswordResetToken`. **Reuses** `generate_reset_token()`/`hash_reset_token()` (only the SHA-256 hash is stored). Active while `used_at` is NULL and not expired; TTL is 24h. Registered in `database.py` (imported next to `pw_reset_token`).
- `User.email_verified: bool` (on the **User table model**, defaults False). `authenticate_user` stays pure (`User | None`); the verified check lives in the `/login` route (403 "verify your email"). A new column on an existing table needs the in-place ALTER (`... ADD COLUMN email_verified BOOLEAN DEFAULT 0;`) then backfill existing members to 1 — or just reseed.
- **Signup flow** (`routes/auth_routes.py`): `/signup` creates the user unverified, mints a token, emails `{FRONTEND_URL}/verify-email?token=<raw>` to cougarnet_email, and returns a **generic message (no JWT)**. Rate limited **5/hour**. **Squat reclaim:** an existing *unverified* account for the same email is deleted (via `_delete_unverified_user`, which also clears the four multi-select child rows + verification/reset tokens — SQLite doesn't cascade and reuses row ids, so orphans would otherwise attach to the reclaimed id) and re-created; only a *verified* email 409s. Re-submitting signup for an unverified email therefore doubles as "resend link".
- **Confirm** (`/verify-email`, `EmailVerifyConfirm{token}`): looks up by hash, rejects unknown/used/expired **and orphaned** (user deleted by a later reclaim) tokens with a generic 400, else stamps `email_verified=True` + `used_at` and returns a login JWT. Idempotency: the frontend verify page guards the single-use POST with a `useRef` so React StrictMode's double-invoke doesn't 400 the second call.
- **Seed** sets `email_verified=True` on all seeded accounts (test users, chairs, comms director) — otherwise none could log in after a reseed. `tests/conftest.py`'s `make_user` also defaults `email_verified=True` (fixture users are established members); tests for the flow itself live in `tests/auth_tests/test_email_verification.py`.
- **Frontend:** `pages/verify-email.jsx` at route `/verify-email` (in `App.jsx`); signup shows a "check your email" screen instead of logging in; signin maps 403 to a "verify your email" message. `api.js`: `verifyEmail(token)` (public).

## Password reset & rate limiting
- `models/user/pw_reset_token.py` — `PasswordResetToken(user_id, token_hash, created_at, expires_at, used_at)`. Only the **SHA-256 hash** of the raw token is stored (the raw token is high-entropy `secrets.token_urlsafe(32)`, so SHA-256 — not Argon2 — is correct here). A token is active while `used_at` is NULL and `expires_at` is in the future; TTL is 1 hour. Requesting a new reset retires any prior active tokens for that user.
- `services/pw_reset_services.py` — `generate_reset_token()` / `hash_reset_token()`.
- `routes/pw_reset_routes.py` — `POST /password-reset/request` and `POST /password-reset/confirm`. **Never reveal whether an email exists**: request always returns the same 200 body (even if `send_email` fails), and confirm returns one generic 400 for unknown/used/expired tokens. Reset emails go to **cougarnet_email** (the verified UH address). The link is `{FRONTEND_URL}/reset-password?token=<raw>`.
- Confirm reuses the shared `validate_password_strength()` from `models/user/user_schemas.py` (also used by `UserCreate`) — change password rules there, in one place.
- **Password policy (NIST 800-63B style):** min 10 chars (`MIN_PASSWORD_LENGTH`), max 128 (`MAX_PASSWORD_LENGTH`) in `validate_password_strength` (`models/user/user_schemas.py`) — deliberately NO composition rules (upper/digit/special) and NO expiry; both are counterproductive per NIST. The schema validator is **pure/sync only** (pydantic runs it during request parsing) — don't put network calls in it. The breached-password check lives in the routes instead: `services/hibp_services.py` `is_password_pwned()` queries the Have I Been Pwned range API (k-anonymity — only the first 5 SHA-1 hex chars leave the server; **fail-open**: any error logs and allows). `/signup` and `/password-reset/confirm` call it via `await asyncio.to_thread(hibp_services.is_password_pwned, ...)` — as a **module attribute** so tests can monkeypatch — and reject with **422** (not 400 — the reset page shows "invalid link" for 400) *before* any DB mutation / before marking the reset token used. Tests never hit the network: an autouse `disable_hibp_check` fixture in `tests/conftest.py` stubs it to False. Side effect: `seed.py` calls `create_user()` directly (never the routes), so the seed password `password123` seeds fine. The frontend length checks in `signup.jsx` and `reset-password.jsx` mirror the minimum — keep them in sync.
- **Login lockout (per-account):** 10 consecutive failures (`LOCKOUT_THRESHOLD` in `routes/auth_routes.py`) lock the account for 10 minutes (`LOCKOUT_MINUTES`) → **429 "Too many attempts. Try again later."** raised *before* the Argon2 verify (cheap reject; signin.jsx already maps 429 to a "too many attempts" message). Every failure for an existing email increments `User.failed_login_count` and **commits**; an expired lock is cleared (both fields) before the attempt is evaluated; a successful login resets both fields. Wrong credentials stay a generic 401. The two columns (`failed_login_count`, `locked_until`) live on the `User` table model — a pre-existing `database.db` needs a reseed (delete it + re-run `seed.py`) or a manual `ALTER TABLE user ADD COLUMN ...`, since `create_all()` never ALTERs existing tables. Complements (does not replace) slowapi's per-IP 5/minute limit on `/login` — in lockout tests, call `limiter.reset()` between attempts or the IP limit's 429s shadow the lockout's.
- **JWT invalidation:** `create_access_token` sets `iat`; a successful reset stamps `User.password_changed_at`, and `get_current_user` rejects tokens whose `iat` predates it. PyJWT floors `iat` to whole seconds while `password_changed_at` keeps microseconds, so the comparison is at **whole-second granularity with strict `<`** — a token issued in the same second as the reset stays valid. Tokens without `iat` are rejected once `password_changed_at` is set.
- **Rate limiting (slowapi):** the `Limiter` lives in `services/rate_limit.py` (NOT `main.py` — route modules import it, and importing from `main` would be circular). `main.py` attaches it to `app.state` and registers the 429 handler. `/login` is `5/minute`, `/signup` is `5/hour`, `/password-reset/request` is `3/hour` (keyed by client IP). slowapi-decorated endpoints must take a `request: Request` parameter, with the `@limiter.limit(...)` decorator **below** the router decorator.
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
