# SHPE UH Website

The official website for the **Society of Hispanic Professional Engineers (SHPE) — University of Houston** chapter. A full-stack web application for managing chapter membership, events, committees, and internal communications.

## Features

- **Authentication** — Secure sign-up and login with JWT tokens and Argon2 password hashing. Passwords must be 10–128 characters and are checked against the Have I Been Pwned breached-password database (no composition rules, no forced expiry — per NIST guidance); accounts lock temporarily after repeated failed logins
- **Password Reset** — "Forgot password?" flow: a single-use reset link (valid 1 hour) is emailed to the member's CougarNet address; resetting signs out all existing sessions. Login and reset requests are rate-limited
- **Events Calendar** — Public calendar displaying upcoming chapter events
- **Event Sheet Sync** — The calendar populates itself from the chapter's event-tracker Google Sheet, re-read once a day, so officers add events in the sheet they already maintain and never touch the website
- **Email Reminders** — Members can request an email reminder for any upcoming event (sent 24h before, handled by a background loop)
- **Dashboard** — Personalized member dashboard with upcoming events and notifications
- **Profile** — Members can view their profile details and upload a PDF resume (view, replace, or remove it); resumes can be mirrored to a chapter Google Drive folder
- **Committees** — Browse, join, and leave committees; chairs and co-chairs can view rosters and broadcast messages to members
- **Notifications** — In-app notification system for committee activity (joins, messages)
- **Merch Shop** — Public storefront with cart and checkout (card, **Apple Pay**, and **Google Pay** payments via **Square**; runs in a simulated dev mode until Square credentials are configured). Buyers pay online and pick up in person at a chapter event. The comms director, marketing chair, and president manage products, orders, and shop settings from the Shop Manager page and are notified of every new order; buyers get an emailed receipt at checkout and another email when their order is ready for pickup
- **President & VP Tools** — The chapter president has full admin access everywhere (shop manager plus every committee's chair tools). The president and both vice presidents share a **Members** page with four tabs: **All**, **E-Board**, and **Chairs** show chapter-wide stats (total accounts, dues paid vs. not, national members, classification and shirt-size breakdowns), member lookup by name/email/PSID, and role assignment; **Structure** holds the chapter org chart. Assigning or removing a chair role automatically updates that committee's chair membership. VPs can assign every role except President and the two VP seats, which only the president manages
- **Reporting Structure** — An editable org chart of who oversees whom: officers report to a vice president, chairs report to a vice president or an officer. It links *roles*, not people, so it survives elections and chair handovers without re-entry. Purely organizational — being someone's supervisor grants no extra permissions
- **Email Verification** — signing up creates an account that stays inactive until the member clicks a verification link emailed to their CougarNet address; only then can they log in. This also prevents someone from registering an email they don't control.
- **Chapter Dues at Signup** — right after verifying their email, new members are routed straight into paying their $20 "T-Shirt Dues" (t-shirt included) through the Square checkout, pre-sized with the shirt size from their signup form. Dues are **one per member per membership year** (server-enforced, sign-in required) and **reset every May 30**, so members re-pay each year; signed-in members who haven't paid the current year see a site-wide red banner listing the benefits that ride on dues (Slack access, National convention sponsorship, $10,000+ in scholarships, MentorSHPE, the Resume Book, and the chapter shirt)
- **Gallery** — Photo gallery with an approval workflow
- **Instagram Feed** — Home-page grid of the chapter's latest Instagram posts, pulled live from a public Behold feed
- **Points** — Member points tracking
- **QR Event Attendance** — Every event gets a sign-in and a sign-out QR code. Members scan with their phone's normal camera — there's no app to install and no in-app scanner — and points are awarded on the spot: 2 for signing in and 2 for signing out of a regular event, 3 and 2 for a general meeting, plus 2 for bringing a new member. Scanning the same code twice never awards twice, a code doesn't work until roughly an hour before the event starts, and it stops working once the event is over. Chairs and E-Board present the QR (in a modal or fullscreen at the door) from their **Events** page, watch a live scan counter, and review a read-only attendance roster for each event they host

## Tech Stack

**Frontend**
- React 19, React Router v7
- Vite, Tailwind CSS v4, Framer Motion
- Axios
- qrcode.react (renders the sign-in/sign-out QR codes for chairs)

**Backend**
- FastAPI, SQLModel (SQLAlchemy 2), PostgreSQL 17 (via Docker), psycopg 3
- PyJWT, pwdlib (Argon2), Pydantic v2, Uvicorn
- slowapi (rate limiting)
- squareup (Square Payments API for shop checkout)
- pytest + httpx for the test suite

## Prerequisites

- **Node.js** v18+ and npm
- **Python** 3.11+
- **Git**
- **Docker Desktop** (or another Docker runtime) — runs the PostgreSQL database

## Getting Started

### 1. Clone the repository

```bash
git clone <repo-url>
cd shpe-uh-website
```

### 2. Start the database

```bash
docker compose up -d
docker compose exec db createdb -U shpe shpe_test   # one-time: creates the test database
```

This starts PostgreSQL 17 in Docker, listening on `localhost:5433` (see `docker-compose.yml`). The main `shpe` database is created automatically by the container; `shpe_test` (used only by the test suite) needs the one-time `createdb` above.

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

Create `backend/.env` (see [Environment Variables](#environment-variables)):

```bash
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=720
FRONTEND_URL=http://localhost:5173" > .env
```

Then seed and run:

```bash
# Seed the database with committees, chairs, and test data.
# Safe to re-run: every seeder skips what already exists.
python seed.py

# Start the development server
python main.py
# or: uvicorn main:app --reload
```

Backend runs at **http://localhost:8000**. Interactive API docs at **http://localhost:8000/docs**.

### 4. Frontend setup

```bash
cd frontend

# Install dependencies
npm install

# Create the environment file
echo "VITE_API_URL=http://localhost:8000" > .env.local

# Start the dev server
npm run dev
```

Frontend runs at **http://localhost:5173**.

## Environment Variables

### `backend/.env`

| Variable | Required | Description | Example |
|---|---|---|---|
| `SECRET_KEY` | Yes | Random hex secret for JWT signing | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ALGORITHM` | Yes | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | Token lifetime in minutes. Defaults to `720` (12 h): there is no refresh-token flow, so a short lifetime makes members re-authenticate constantly, and every re-auth is an expensive password hash | `720` |
| `DATABASE_URL` | No | Postgres connection string. Defaults to the `docker-compose.yml` credentials/port, so local dev needs nothing here unless those change | `postgresql+psycopg://shpe:shpe_dev_password@localhost:5433/shpe` |
| `TEST_DATABASE_URL` | No | Separate Postgres database used only by the test suite. Defaults to the same host/port/credentials as `DATABASE_URL`, database `shpe_test` (create it once with `docker compose exec db createdb -U shpe shpe_test`) | `postgresql+psycopg://shpe:shpe_dev_password@localhost:5433/shpe_test` |
| `DATA_DIR` | No | Directory for uploaded files (`uploads/resumes`, `uploads/products`). The database lives in Postgres, but uploads are still on disk, so this must point at a mounted volume when deploying. Unset = the `backend/` directory | `/data` |
| `FRONTEND_URL` | No | Base URL of the frontend, used to build password-reset links in emails. Defaults to `http://localhost:5173` | `http://localhost:5173` |
| `ENVIRONMENT` | No | Set to `production` on the live server **only**. Makes the app fail closed instead of falling back to dev-mode no-ops: startup refuses to boot unless Square + SMTP are fully configured (with `SQUARE_ENVIRONMENT=production`), a charge attempt without Square config raises instead of simulating a free order, and `seed.py` refuses to run. Leave unset for local dev | `production` |
| `SMTP_HOST` | No | SMTP server for reminder emails. **Unset = dev mode:** emails print to the console instead | `smtp.gmail.com` |
| `SMTP_PORT` | No | SMTP port | `587` |
| `SMTP_USER` | No | Sender address / SMTP login | `chapter@example.org` |
| `SMTP_PASSWORD` | No | SMTP password (use an app password for Gmail) | — |
| `EMAIL_FROM` | No | From header; defaults to `SMTP_USER` | `SHPE UH <noreply@example.org>` |
| `SQUARE_ACCESS_TOKEN` | No | Square API access token for shop card payments. **Unset = dev mode:** checkout is simulated, no real charge | `EAAA...` |
| `SQUARE_LOCATION_ID` | No | Location id of the Square account (same application as the token) | `L4X...` |
| `SQUARE_ENVIRONMENT` | No | `sandbox` (default) or `production` — must match where the token was minted | `sandbox` |
| `CREDENTIALS` | No | Path to the Google **service-account** JSON key used to read the event-tracker sheet. **Unset = dev mode:** the daily sync is skipped and the calendar shows only what's already in the database | `/path/to/service-account.json` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | No | The same service-account key as a single-line JSON string (`jq -c . key.json`), for hosts with no way to mount a file. Takes precedence over `CREDENTIALS` | `{"type":"service_account",...}` |
| `SHEET_ID` | No | Id of the event-tracker spreadsheet (the long string in its URL) | `1AbC...xyz` |

##### Deployment-only

Leave these unset for local development.

| Variable | Description | Example |
|---|---|---|
| `CORS_ORIGINS` | Comma-separated list of browser origins allowed to call the API. Falls back to `FRONTEND_URL`, then the Vite dev server. Under `ENVIRONMENT=production` the app **refuses to start** if this still points at localhost | `https://example.org,https://www.example.org` |
| `CORS_ORIGIN_REGEX` | Extra origins by pattern — useful for preview deployments | `https://.*\.vercel\.app` |
| `ALLOWED_HOSTS` | Comma-separated `Host` header allowlist. Set it to your API domain so the raw platform hostname stops answering | `api.example.org` |
| `TRUST_PROXY_IP_HEADERS` | Set to `1` when the app runs behind a proxy or load balancer. **Without it every rate limit becomes one global bucket** shared by all visitors, because every request appears to come from the proxy's address | `1` |
| `TRUSTED_PROXY_HOPS` | How many proxies sit in front of the app. Only change it if you add a CDN in front of the platform edge | `1` |
| `RATE_LIMIT_LOGIN` / `_SIGNUP` / `_ORDER` / `_PASSWORD_RESET` | Per-IP limits. Defaults are deliberately generous because a campus event puts hundreds of members behind one shared IP | `60/minute` |
| `RATE_LIMIT_ATTEND` / `_CODE_PREVIEW` | Per-IP limits for QR check-in. Higher still: a whole room scans from one network within a couple of minutes, and check-in is already protected per-account (sign-in required, and a repeat scan awards no extra points) | `600/minute` |
| `SMTP_TIMEOUT` | Seconds to wait on the mail server before giving up | `10` |
| `SQL_ECHO` | `1` logs every SQL statement. Leave unset in production — the log would include member emails and PSIDs | — |

#### Square shop payments (optional, one-time setup)

When configured, the checkout payment step renders Square's secure card element (card numbers go straight to Square — they never touch this backend), and `POST /shop/orders` charges the card for the server-computed total **before** creating the order. A declined card leaves no order behind. Every buyer gets an emailed, itemized receipt at checkout — including Square's hosted receipt link when the charge was real. Square's fee is ~2.9% + 30¢ per online charge.

Every charge is **itemized in Square**: the cart is mirrored into a Square order (product name + size, quantity, unit price), so the Square Dashboard shows exactly what was bought per transaction and item names flow into Square's sales reports and exports — no manual tracking needed.

**Wallets:** Apple Pay and Google Pay buttons appear automatically above the card form on devices/browsers that support them — both reuse the exact same charge flow. Google Pay also works in the sandbox. **Apple Pay is production-only** and needs a one-time domain registration: Square Developer Dashboard → your app → **Apple Pay** → add your web domain, then host the verification file Square provides at `https://<your-domain>/.well-known/apple-developer-merchantid-domain-association` (put it in `frontend/public/.well-known/` — Vite serves `public/` at the site root). Until that's done, the Apple Pay button simply doesn't render.

Start in the **Sandbox** (fake money, test cards), then switch to Production:

1. Go to [developer.squareup.com](https://developer.squareup.com/apps) and sign in with the chapter's Square account, then create an application (any name, e.g. "SHPE UH Website").
2. In the application's **Sandbox** tab, copy the **Application ID** (`sandbox-sq0idb-...`) and **Access Token** (`EAAA...`).
3. Get the sandbox **Location ID**: open the app's **Locations** page (or Default Test Account) and copy the id.
4. Set `SQUARE_ACCESS_TOKEN`, `SQUARE_LOCATION_ID` (+ `SQUARE_ENVIRONMENT=sandbox`) in `backend/.env`, and `VITE_SQUARE_APP_ID`, `VITE_SQUARE_LOCATION_ID` in `frontend/.env.local`. Restart both servers.
5. Test with Square's sandbox card: `4111 1111 1111 1111`, any future expiry, any CVV, any ZIP. Charges appear in the [Sandbox Seller Dashboard](https://squareupsandbox.com/dashboard).
6. **Go live:** swap in the app's **Production** Application ID + Access Token, the real store's Location ID, and set `SQUARE_ENVIRONMENT=production`. Also set `ENVIRONMENT=production` — the backend will then refuse to start if any of this is missing, so a config mistake can never silently turn checkout into free simulated orders.
| `GDRIVE_RESUME_FOLDER_ID` | No | Drive folder that resume PDFs are synced to — must be the **app-created** folder id printed by `get_drive_refresh_token.py` (a hand-made folder isn't reachable under the `drive.file` scope). **Unset = dev mode:** resumes stay local only | `1AbC...xyz` |
| `GDRIVE_OAUTH_CLIENT_ID` | No | OAuth client id for Drive resume sync (see setup below) | `...apps.googleusercontent.com` |
| `GDRIVE_OAUTH_CLIENT_SECRET` | No | OAuth client secret for Drive resume sync | — |
| `GDRIVE_OAUTH_REFRESH_TOKEN` | No | Refresh token minted by `get_drive_refresh_token.py` | — |

#### Google Drive resume sync (optional, one-time setup)

When configured, every resume upload is mirrored to the Drive folder, re-uploads replace the old copy in place, and deleting a resume removes it from Drive too. Every resume is renamed to `First_Last_PSID.pdf` (the uploaded filename is discarded) — both locally and in Drive. Sync is best-effort: if Drive is unreachable the upload still succeeds locally.

> **Why OAuth and not a service account?** Google blocks service accounts from uploading to personal My Drive folders (403 `storageQuotaExceeded` — they have no storage quota). A service account only works with a Google Workspace **Shared Drive**. For a folder on a personal Gmail account, the backend must upload *as you* via OAuth.

> **Scoped to one folder.** The OAuth token uses the `drive.file` scope: the backend can only see and modify files/folders **it created itself** — never the rest of your Drive. That's why the setup script creates the resume folder for you (it can't reach a folder you made by hand). The folder is owned by you, in your My Drive, and you can move or rename it afterwards without breaking sync.

1. In [Google Cloud Console](https://console.cloud.google.com), create (or pick) a project and enable the **Google Drive API**.
2. **APIs & Services → OAuth consent screen** — configure it and set Publishing status to **In production** (refresh tokens minted while in "Testing" expire after 7 days).
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID → Desktop app** — copy the client id and secret.
4. From `backend/`, run `.venv/bin/python get_drive_refresh_token.py <client_id> <client_secret> [folder name]` (folder name defaults to "SHPE Resume Book") — a browser opens; sign in with your Google account and approve. The script mints the refresh token and creates (or reuses) the resume folder.
5. Paste the four printed `GDRIVE_*` lines into `backend/.env` and restart the backend.

#### Event tracker sheet sync (optional, one-time setup)

When configured, the backend reads the chapter's event-tracker spreadsheet once a day (6 AM Central) and reconciles it into the events calendar. Access is **read-only** — the backend never writes to the sheet. Events are matched by date + name, so editing an event's description, time, location, or owning committee in the sheet updates the calendar entry in place on the next sync.

> **Moving an event to a different day, or renaming it, creates a second calendar entry** rather than replacing the first — the old one has to be removed by hand. The sync only ever adds and updates; it never deletes, so removing a row from the sheet also leaves its calendar entry in place.

> Unlike the Drive resume sync above, a **service account is the right choice here** — it only needs read access to a sheet you share with it, so the personal-Drive storage limitation doesn't apply.

1. In [Google Cloud Console](https://console.cloud.google.com), create (or pick) a project and enable the **Google Sheets API**.
2. **APIs & Services → Credentials → Create Credentials → Service account** — create one, then open it, go to **Keys → Add key → Create new key → JSON**, and download the file.
3. Open the downloaded JSON and copy the `client_email` value (ends in `.iam.gserviceaccount.com`).
4. In the event-tracker spreadsheet, click **Share** and give that address **Viewer** access.
5. Move the JSON into `backend/secrets/` (create the folder if it isn't there — it's gitignored, so the key never reaches version control).
6. Set `CREDENTIALS` and `SHEET_ID` in `backend/.env`, then restart the backend. `SHEET_ID` is the long string in the sheet's URL (`docs.google.com/spreadsheets/d/<SHEET_ID>/edit`):

   ```
   CREDENTIALS=secrets/your-service-account.json
   SHEET_ID=<id from the sheet URL>
   ```

> `CREDENTIALS` is resolved relative to the working directory, so a `secrets/...` path assumes the backend was started from `backend/` (as in `cd backend && python main.py`). Use an absolute path if you launch it from somewhere else.

> Keep the service-account JSON out of version control — treat it like a password. `backend/secrets/` and `backend/.env` are both already gitignored.

> **Each semester has its own tracker sheet.** Dates in the sheet are `MM/DD` with no year, so the sync assumes the current year — which is correct as long as `SHEET_ID` points at the sheet for the semester you're in. **Switch `SHEET_ID` to the spring sheet before January 1**; if the fall sheet is still configured when the year rolls over, its events get re-read as next year's and appear on the calendar a second time.

**Sheet format:** row 1 holds the column headers (`DATE`, `EVENT NAME`, `DESCRIPTION`, `LOCATION`, `START TIME`, `END TIME`, `OWNER(S)`, `COLLAB(S)?`), row 2 is a template/sample row that's always skipped, and real events start on row 3. `DATE` is `MM/DD` and times accept either 12-hour (`6:00 PM`) or 24-hour (`18:00`) formats — blank, `All Day`, or `TBD` times place the event at midnight. A row with no event name is ignored, and a row with an unreadable date is skipped without affecting the others.

`OWNER(S)` and `COLLAB(S)?` are dropdowns, and they decide which committee an event is filed under. `OWNER(S)` is either `<Committee> Chair - <name>` or an E-Board position; `COLLAB(S)?` optionally names one more committee co-hosting the event, or an outside organization, which is ignored. Both are matched against the sheet's own spelling of each committee name, so **adding a new option to either dropdown needs a matching entry in `COMMITTEE_ROLES`** (`backend/services/event_tracker_services.py`) — otherwise the event is quietly filed under the E-Board instead.

### `frontend/.env.local`

| Variable | Required | Description | Example |
|---|---|---|---|
| `VITE_API_URL` | Yes | Backend base URL | `http://localhost:8000` |
| `VITE_BEHOLD_FEED_URL` | No | Public [Behold](https://behold.so) JSON feed for the home-page Instagram grid. If unset/unreachable, the grid shows a shimmer placeholder | `https://feeds.behold.so/<feed-id>` |
| `VITE_SQUARE_APP_ID` | No | Square application id for the checkout card element (sandbox ids start with `sandbox-`). **Unset = dev mode:** payment step stays simulated | `sandbox-sq0idb-...` |
| `VITE_SQUARE_LOCATION_ID` | No | Square location id — same one as the backend's `SQUARE_LOCATION_ID` | `L4X...` |

> **Never commit `.env` or `.env.local` to version control.**

## Seeded Accounts

`python seed.py` creates two test members (one with dues already paid, one without), all 14 committees and their chairs/co-chairs (22 chair accounts), a comms director, the chapter president, the rest of the E-Board (both VPs plus the five officers, named to match the About page), the reporting structure (the chapter org chart, 20 links), the shop settings row, and five sample shop products (including the $20 "T-Shirt Dues"). All seeded accounts use the password `password123` — which is why `seed.py` refuses to run (exit 1) when `ENVIRONMENT=production` is set: seed data must never enter the live database.

| Account | Email | Role |
|---|---|---|
| Test member (dues **paid** — no banner) | `test@cougarnet.uh.edu` | Member |
| Test member (dues **not paid** — sees the dues banner) | `test1@cougarnet.uh.edu` | Member |
| Committee chairs | `<first>.<last>@cougarnet.uh.edu` (e.g. `angel.montoya@cougarnet.uh.edu`) | Chair of their committee |
| Comms director | `comms.director@cougarnet.uh.edu` | Communication Director (shop admin) |
| President | `daniel.lopez.gil@cougarnet.uh.edu` | President (full admin: Members page, shop, all committees) |
| VP External | `carlos.alba@cougarnet.uh.edu` | Vice President External (Members page; can't touch the presidency) |
| VP Internal | `gabriela.lorenzo@cougarnet.uh.edu` | Vice President Internal (Members page; can't touch the presidency) |
| E-Board officers | `jaden.gomez@`, `sara.sanchez@`, `santiago.gonzalez@`, `fernando.vaca@`, `alejandro.castro@` (all `cougarnet.uh.edu`) | Treasurer, Secretary, New Member Rep, Regional Rep, Director of Internal Affairs — no admin powers, they fill the org chart |

The seeded marketing chair (`valeria.zabala@cougarnet.uh.edu`) is the third shop admin.

The full chair roster lives in `backend/seed.py` (`COMMITTEE_ROSTER`).

Re-running `python seed.py` is safe — every seeder skips what already exists, so it only fills in what's missing (that's how the E-Board officers were added to an existing database). The flip side: editing seed data in the file has no effect on rows that are already there; clear those rows first.

> **Note:** if you wipe and reseed the database (see below) while the backend is running, restart it — it holds pooled connections from before the wipe and will otherwise serve stale or broken data.

> **Picking up a schema change:** this project doesn't use database migrations yet, so a model change (new column, new enum value, etc.) is picked up by wiping and reseeding rather than an in-place upgrade:
>
> ```bash
> docker compose down -v          # -v is essential — drops the database volume
> docker compose up -d
> docker compose exec db createdb -U shpe shpe_test
> cd backend && python seed.py
> ```
>
> This is a pre-deploy convenience — once the site is holding real member data, wiping stops being an option and proper migrations will need to be introduced.

## Project Structure

```
shpe-uh-website/
├── docker-compose.yml  # PostgreSQL 17 dev database container
├── frontend/
│   └── src/
│       ├── api/            # Axios instance + all API call functions (api.js)
│       ├── components/     # Header, Footer, Avatar, GalleryApproved, PrivateRoute, cart drawer, shop-manager panel, ...
│       ├── context/        # AuthContext (session), CartContext (shop cart, persisted locally)
│       ├── utils/          # Shared helpers (money formatting, order-status styling, event colors/labels/duration)
│       ├── pages/          # One file per route, incl. attend.jsx (mobile QR check-in) and my-events.jsx (chair Events page)
│       └── App.jsx         # Route definitions
└── backend/
    ├── main.py             # FastAPI app: routers, health checks + background loops (reminder emails, daily event-sheet sync)
    ├── config.py           # DATA_DIR — where uploaded files are written
    ├── get_drive_refresh_token.py  # One-time helper for Google Drive resume-sync setup
    ├── database.py         # Postgres engine (DATABASE_URL) and session factory
    ├── seed.py             # Committees, chair roster, and dev seed data
    ├── Dockerfile          # Container image used for deployment
    ├── requirements.txt    # Runtime dependencies
    ├── requirements-dev.txt # Test tooling (includes requirements.txt)
    ├── routes/             # APIRouters: admin (president + VPs), auth, committees, events (+ reminders), notifications, password reset, resume, shop
    ├── uploads/            # Uploaded resume PDFs and product images (gitignored, created on first upload)
    ├── models/             # SQLModel table definitions (user/, shop/, committee, event, notification, ...)
    ├── security/           # JWT creation and password hashing
    ├── services/           # DB session deps, user/committee/reminder/email/Drive-sync/password-reset/shop/Square-payment/event-sheet-sync/reporting-structure/QR-attendance services, rate limiter, HIBP breached-password check
    ├── validators/         # Input validation (email normalization)
    └── tests/              # pytest suite (runs against a dedicated `shpe_test` Postgres database; requires the database container to be running)
```

## Pages

| Path | Description | Auth Required |
|---|---|---|
| `/` | Home | No |
| `/about` | About SHPE UH — history, pillars, and the E-Board & Chairs roster (with contact emails) | No |
| `/membershpe` | Membership info | No |
| `/sponsors` | Sponsors | No |
| `/gallery` | Photo gallery | No |
| `/calendar` | Events calendar (with "Remind me by email") | No |
| `/shop` | Merch shop — browse products, filter by category | No |
| `/shop/:productId` | Product detail — pick a size (apparel) and quantity, add to cart | No |
| `/shop/checkout` | Two-step checkout: contact details, then payment (Square card element + Apple Pay / Google Pay where supported; simulated when Square isn't configured) | No |
| `/shop/order/:code` | Order confirmation and live status (looked up by code + buyer email) | No |
| `/signin` | Sign in | No |
| `/signup` | Sign up (multi-step; ends on a "check your email" screen) | No |
| `/verify-email` | Confirm a new account from the emailed link, then route into chapter-dues checkout | No |
| `/forgot-password` | Request a password-reset email | No |
| `/reset-password` | Choose a new password (opened from the emailed link) | No |
| `/dashboard` | Member dashboard | Yes |
| `/committees` | Browse/join committees, chair tools | Yes |
| `/profile` | Profile info, PDF resume, and order history | Yes |
| `/members` | Member directory and org chart: chapter stats, member lookup, role assignment, and the reporting structure, across All/E-Board/Chairs/Structure tabs — president and VPs only | Yes |
| `/shop-manager` | Shop-management tools (products, orders, notifications, settings) — shop admins only (comms director / marketing chair / president) | Yes |
| `/my-events` | Chair/E-Board Events page: My Events / All Events tabs, a QR modal (Sign in/Sign out, fullscreen "present" view, live scan counter) for each hosted event, and a read-only attendance roster | Yes |
| `/attend/:code` | Mobile QR check-in flow — reached only by scanning a code, not linked from navigation. No site header/footer/cart; renders its own "sign in to continue" screen if you're signed out | No |

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Liveness probe for the hosting platform. Deliberately does not query the database, so a momentary lock can't get a healthy server restarted |
| GET | `/health/db` | No | Readiness check that does query the database — for manual verification after a deploy |
| POST | `/login` | No | Authenticate and receive a JWT token (rate limited, configurable via `RATE_LIMIT_LOGIN`); 403 until the account's email is verified; 429 after too many failed attempts (temporary account lock) |
| POST | `/signup` | No | Register a new account (unverified) and email a verification link; returns a message, not a token (rate limited, configurable via `RATE_LIMIT_SIGNUP`) |
| POST | `/verify-email` | No | Confirm a signup with the emailed token and receive a JWT token |
| POST | `/password-reset/request` | No | Email a reset link if the account exists (always returns 200; rate limited, configurable via `RATE_LIMIT_PASSWORD_RESET`) |
| POST | `/password-reset/confirm` | No | Set a new password using a valid reset token |
| GET | `/me` | Yes | Current user profile (includes points and `resume_filename`) |
| POST | `/me/resume` | Yes | Upload a PDF resume (PDF only, ≤2 MB); renamed to `First_Last_PSID.pdf` and synced to Google Drive when configured |
| GET | `/me/resume` | Yes | Download the current user's resume |
| DELETE | `/me/resume` | Yes | Remove the current user's resume (also removed from Google Drive) |
| GET | `/events` | No | All events (powers the public calendar) |
| GET | `/events/upcoming?days=7` | Yes | Upcoming events within N days |
| POST | `/events/{id}/remind` | Yes | Set an email reminder for an event |
| DELETE | `/events/{id}/remind` | Yes | Cancel an unsent reminder |
| GET | `/events/reminders/me` | Yes | Current user's active reminders |
| POST | `/events/attend` | Yes | Record a QR scan and award points; the scanned code itself says whether it's a sign-in or a sign-out. Scanning twice is safe — it never awards twice. Too early (more than ~1 hour before the event) is rejected |
| GET | `/events/code/{code}` | Optional | Preview a scanned code before recording anything — event name/time/location and whether check-in is open yet, expired, or already recorded (fills in with a valid token) |
| GET | `/events/mine` | Chair/E-Board | Events they host, with the sign-in/sign-out codes to render as QR |
| GET | `/events/all` | Chair/E-Board | Every chapter event, read-only (no codes) |
| GET | `/events/{id}/attendance` | Chair only | Attendance roster for one of their events |
| GET | `/events/{id}/scan-count` | Chair only | Live sign-in/sign-out counts for one event, for the QR modal to poll |
| GET | `/committees` | Yes | All committees with membership status and chair contacts |
| POST | `/committees/{id}/join` | Yes | Join a committee (notifies every chair) |
| DELETE | `/committees/{id}/leave` | Yes | Leave a committee |
| GET | `/committees/{id}/members` | Chair only | Roster with name, email, phone |
| POST | `/committees/{id}/messages` | Chair only | Broadcast a message to members |
| GET | `/committees/{id}/messages` | Member/Chair | Committee messages, newest first |
| GET | `/notifications` | Yes | Current user's notifications, newest first |
| POST | `/notifications/{id}/read` | Yes | Mark a notification as read |
| GET | `/shop/settings` | No | Shop settings (storefront tagline + per-order item cap) |
| GET | `/shop/products` | No | Shop products that are active and not retired |
| GET | `/shop/products/{id}` | No | One product (type, sizes, price); 404 if unknown, hidden, or retired |
| GET | `/shop/products/{id}/image` | No | Product image |
| POST | `/shop/orders` | No | Charge the card via Square (when configured), then place the order; total computed server-side (rate limited, configurable via `RATE_LIMIT_ORDER`) |
| GET | `/shop/orders/{code}?email=` | No | Buyer order lookup — requires the matching buyer email |
| GET | `/shop/orders/me` | Yes | Signed-in member's order history |
| PATCH | `/shop/settings` | Shop admin | Update the tagline and/or per-order item cap |
| POST | `/shop/products` | Shop admin | Create a product |
| PATCH | `/shop/products/{id}` | Shop admin | Edit a product / toggle availability |
| DELETE | `/shop/products/{id}` | Shop admin | Retire a product — hides it from the shop and keeps it restorable (nothing is deleted); the dues product can't be retired |
| POST | `/shop/products/{id}/restore` | Shop admin | Restore a retired product (it comes back hidden) |
| POST | `/shop/products/{id}/image` | Shop admin | Upload a product image (PNG/JPEG/WebP, ≤2 MB) |
| GET | `/shop/admin/products` | Shop admin | All products, including hidden and retired |
| GET | `/shop/orders?status=` | Shop admin | All orders, filterable by status |
| PATCH | `/shop/orders/{id}` | Shop admin | Advance order status (`ready`/`picked_up`/`cancelled`) or save a note |
| GET | `/admin/members?search=&paid=&role=` | President / VP | Member directory with dues status; filter by name/email/PSID search, paid, or role |
| GET | `/admin/stats` | President / VP | Chapter stats: accounts, dues paid/unpaid, national members, classification/role/shirt-size breakdowns |
| GET | `/admin/roles` | President / VP | Every role the caller may assign (a VP's list omits President and both VP roles) |
| PATCH | `/admin/members/{id}/role` | President / VP | Assign a member's role (chair roles also sync the committee's chair membership). A VP can't assign or change President or VP roles |
| GET | `/admin/structure` | President / VP | The reporting tree: every e-board and chair role with its supervisor and who currently holds it |
| PUT | `/admin/structure/{role}` | President / VP | Set which role a role reports to. Organizational only — grants no permissions |

"Shop admin" = a user whose role is **Communication Director**, **Marketing Chair**, or **President**.

## President & role assignment

The **President** role is the site-wide admin: shop manager access, every committee's chair tools (roster + messages on all committees), and the **Members** page (`/members`) backed by the `/admin/*` endpoints. From there they can look up any account, see who has and hasn't paid dues for the current membership year, and assign roles — vice presidents, e-board, committee chairs, or plain member.

**Both Vice Presidents share the Members page**, so role fixes don't wait on one person. Two limits keep the top of the chapter out of reach: a VP can't assign the President or either VP role (none appear in their dropdown), and a VP can't change the role of anyone who currently holds one. That covers both directions of the same risk — without it a VP could demote the president or their fellow VP, or promote an ally into a VP seat, and the chapter could end up with nobody holding full admin.

### Reporting structure

The **Structure** tab draws the chapter org chart as a tree — the president at the top, each VP branching beneath, their officers below that, and the chairs as leaves, with each card showing who currently holds the role (or **Vacant**). Change a reporting line with the dropdown on any card. The president sits at the top and both VPs report to them (fixed). Each e-board officer reports to one VP, and each committee chair reports to a VP or an officer — the president and both VPs can rearrange either.

It links **roles rather than people**: "Academic Chair reports to Treasurer" keeps working when a new person is elected, so nothing needs re-entering after a handover. Co-chairs of one committee share a role and therefore share a supervisor.

`seed.py` preloads the chapter's current chart: the New Member Representative, Treasurer, and Regional Representative report to the VP External; the Communications Director, Secretary, and Director of Internal Affairs report to the VP Internal; and all 14 chairs sit beneath those officers. Seeding **skips the structure entirely once any link exists**, so re-running `seed.py` never overwrites changes made on the Structure tab. To reload the chart from the file, clear it first:

```bash
docker compose exec db psql -U shpe -d shpe -c "DELETE FROM rolereport;" && python backend/seed.py
```

> The structure is organizational only. Being listed as someone's supervisor grants **no** extra permissions — role assignment stays with the president and VPs.

Nobody can change their own role. To hand off the presidency, the sitting president promotes their successor first — two presidents can coexist briefly — and the successor then demotes them.

Every role change asks for confirmation, naming both the old and new role, and warns when the change will also move someone on or off a committee's chair listing.

> **Assigning a chair role updates the Committees page, not the About page.** The new chair appears on their committee card automatically, keeping the shared committee address (e.g. `academics@shpeuhchair.org`) rather than their personal one. The About page roster is maintained by hand — update `frontend/src/pages/about.jsx` after a chair handover.

## Committees & Chairs

Committees support **co-chairs** — a committee can have one or two chairs, and every chair:

- Appears as a contact (name + email) on the committee card
- Can view the member roster and broadcast messages
- Is notified when a member joins

Chair permissions are tied to the user's `Role` (e.g. `academic_chair`) matching the committee's `chair_role`, plus an `is_chair` membership row. Both are set up by the seed.

## Merch Shop

The shop sells chapter apparel (with sizes) and items like stickers. Anyone can browse and buy — no account needed; signed-in members get checkout prefilled and an order history under their profile.

- **Payment is simulated in v1** — the "Pay" step instantly succeeds and no real money moves. A real Square checkout is planned and will replace only that step.
- **Fulfillment is in-person pickup** at chapter events (no shipping). Every order gets a short code (e.g. `SHPE-A1B2`); the buyer brings it to pickup.
- Order lifecycle: `paid → ready → picked_up` (or `cancelled`). Marking an order **ready** emails the buyer; new orders notify all shop admins in-app and by email.
- **No inventory is tracked.** Each product is either **Active** (listed in the shop) or **Hidden** (kept in the admin table, off the storefront), and every order is limited to a configurable number of units per item (default 5).
- **Products are never deleted.** Retiring one takes it off the storefront and files it under **Retired** in the Shop Manager, where it can be restored at any time (a restored product comes back Hidden, so an admin republishes it deliberately). Past orders keep showing exactly what was bought, and the product image is kept too. The **T-Shirt Dues** product can't be retired — newly verified members are sent straight to it.
- Shop administration belongs to the **Communication Director**, **Marketing Chair**, and **President** roles: they manage products (create/edit, images, show/hide, retire/restore), the order queue, and shop settings (storefront tagline + the per-item order cap) from the **Shop Manager** page at `/shop-manager`.

## QR Event Attendance

Chairs and E-Board members generate QR codes from the **Events** page (`/my-events`) and present them at the door — in a modal, or fullscreen for projecting. Members scan with their phone's regular camera, which opens `/attend/<code>` on the site; there's no in-app scanner and nothing to install.

### Testing a real phone scan

The QR encodes `window.location.origin`, so scanning it on a phone only works if the phone can actually reach that origin — `localhost` on your laptop means nothing to a phone. To test with a real camera on the same Wi-Fi network:

1. Find your computer's LAN IP (e.g. `ipconfig getifaddr en0` on macOS, `ipconfig` on Windows).
2. Point the frontend at that IP instead of `localhost` in `frontend/.env.local`:
   ```
   VITE_API_URL=http://<your-lan-ip>:8000
   ```
3. Start both dev servers reachable from other devices on the network — `python main.py` already binds the backend to `0.0.0.0:8000`, so only the frontend needs the flag:
   ```bash
   cd backend && python main.py
   cd frontend && npm run dev -- --host
   ```
4. **CORS note:** the allowed origins come from the `CORS_ORIGINS` env var (falling back to `FRONTEND_URL`, then `http://localhost:5173`). A browser hitting the site via your LAN IP sends a different `Origin`, so add it in `backend/.env` and restart the backend — no code change needed:
   ```
   CORS_ORIGINS=http://localhost:5173,http://<your-lan-ip>:5173
   ```
5. On your laptop, sign in as a seeded chair (or the president) and open `/my-events` at `http://<your-lan-ip>:5173/my-events` — opening it via the LAN IP (not `localhost`) matters, since that's what gets baked into the QR.
6. Click **Show QR** on an event, then scan it with your phone's camera on the same network. Walk the flow: sign in (if needed) → confirm → "Did you bring a new member?" → success.
7. Scan the same code again to see the "Already checked in" screen, then scan the sign-out code to see the duration + points summary. Check `/dashboard` for the updated points total.

Revert `VITE_API_URL` (and the CORS origin above) afterward for normal local development.

## Deployment

The frontend deploys to **Vercel** (paid tier — the free Hobby plan does not permit commercial use, and the site sells merch) and the backend to **Railway**, with DNS at the registrar.

**Frontend.** Import the repo in Vercel with root directory `frontend`; the framework, build command (`npm run build`), and output directory (`dist`) are detected automatically. Set `VITE_API_URL` (no trailing slash), `VITE_SQUARE_APP_ID`, `VITE_SQUARE_LOCATION_ID`, and `VITE_BEHOLD_FEED_URL` for **both** Production and Preview — these are baked in at build time, so changing one needs a redeploy rather than a restart. `frontend/vercel.json` supplies the single-page-app fallback (needed so emailed `/verify-email` and `/reset-password` links resolve) plus security and caching headers.

**Backend.** Railway builds `backend/Dockerfile`. Add a **managed Postgres** service and set `DATABASE_URL` to its connection string — the `docker-compose.yml` container is for local development only and must not be used in production. Railway injects `PORT` automatically. Point the health check at `/health`.

Uploads still live on disk, so attach a volume mounted at `/data` and set `DATA_DIR=/data`. Without it, every resume and product image is written to the container filesystem and destroyed on the next deploy. The database is unaffected by this — it's in Postgres.

Run exactly **one worker**. Rate-limit counters live in slowapi's process memory, so a second worker makes every limit twice as loose, non-deterministically. (The database no longer constrains this — moving off SQLite removed that half of the reason. Multiple workers become viable once the limiter is backed by Redis, and the uploads volume is shared or moved to object storage.)

**Going live checklist**

1. Generate a fresh `SECRET_KEY` — do not reuse the development one.
2. Set `ENVIRONMENT=production`. The app then refuses to start unless Square and SMTP are fully configured and `CORS_ORIGINS` no longer points at localhost.
3. Set `TRUST_PROXY_IP_HEADERS=1`. Verify it worked: exhaust a rate limit from one network, then immediately try from a different one — the second must succeed.
4. Point DNS at Vercel (frontend) and Railway (backend), and wait for both certificates to issue.
5. Register your domain for Apple Pay in the Square dashboard (see the Square section above).
6. Send a real verification email to a `@cougarnet.uh.edu` address and confirm it lands in the inbox, not junk. University mail filters are strict, and every signup depends on that message arriving.
7. Upload a resume and a product image, place a test order, then redeploy and confirm all three survived.
8. Confirm the managed Postgres backups are on, set up a backup of the uploads volume, and **perform one full restore** of each before relying on them.

## Running Tests

```bash
docker compose up -d   # the database container must be running
cd backend
source .venv/bin/activate
python -m pytest tests/
```

Tests run against a dedicated `shpe_test` Postgres database (separate from the `shpe` dev database, configured via `TEST_DATABASE_URL` — see [Environment Variables](#environment-variables)) using fixtures from `tests/conftest.py`. The `shpe_test` database needs to exist first — see step 2 of [Getting Started](#getting-started) if you haven't created it yet.
