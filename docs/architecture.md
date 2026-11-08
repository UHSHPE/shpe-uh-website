# Architecture

A React single-page app talking to a FastAPI backend over JSON, with PostgreSQL behind it.
Nothing is server-rendered — the frontend is a static bundle, the backend is a pure API.

## Tech stack

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

## How a request flows

Tracing one call end to end, because almost every feature follows this path:

```
page in src/pages/          a component calls an API function
        │
src/api/client.js           the shared axios instance adds the base URL and handles expired sessions
src/api/*Api.js             feature modules add auth headers and call their backend endpoints
        │
        ▼  HTTP
backend/main.py             middleware: body-size ceiling, CORS, host check, rate limiter
        │
backend/routes/*.py         an APIRouter matches the path and checks the caller's role
        │
backend/services/*.py       the actual logic — this is where behaviour lives
        │
backend/models/*.py         SQLModel tables
        │
        ▼
PostgreSQL
```

Four conventions hold that path together, and breaking any of them fails in a confusing way
rather than an obvious one:

- **Every frontend API call goes through the shared `api` axios instance** in `src/api/client.js`
  via a feature module in `src/api/` — never a bare `fetch`, never a raw axios import. The client
  owns the base URL and expired-session handling; feature modules attach authentication. (The one
  exception is the home page's Behold Instagram feed, which is an external public CDN.)
- **Business logic belongs in `services/`, not in the route.** Routes parse, authorize, and
  delegate. A rule written in a route is a rule the other three callers of that logic don't get.
- **Database sessions come from `SessionDependencies`** (`services/dependencies.py`). Never build
  one by hand.
- **A new model must be imported in `backend/database.py`**, or the table is silently missing from
  migrations and tests. See [database.md](database.md).

## Repository layout

```
shpe-uh-website/
├── docker-compose.yml  # PostgreSQL 17 dev database container
├── frontend/
│   ├── index.html          # Page shell: title, favicons, description, Open Graph/Twitter card tags
│   ├── public/             # Served at the site root: favicons, og-image.png, site.webmanifest, robots.txt
│   └── src/
│       ├── api/            # Shared Axios client, feature API modules, and compatibility barrel
│       ├── components/     # Header, Footer, Avatar, gallery display/upload/moderation, PrivateRoute, cart drawer, shop-manager panel, ...
│       ├── constants/      # Dropdown option lists (userEnums.js mirrors the backend enums; countries.js feeds the signup country picker)
│       ├── context/        # AuthContext (session), CartContext (shop cart, persisted locally)
│       ├── hooks/          # useDocumentTitle (browser tab title per page), usePagination (10-per-page list paging)
│       ├── utils/          # Shared helpers (money formatting, order-status styling, cart re-pricing, event colors/labels/duration)
│       ├── pages/          # One file per route, incl. attend.jsx (mobile QR check-in) and my-events.jsx (chair Events page)
│       └── App.jsx         # Route definitions
└── backend/
    ├── main.py             # FastAPI app: routers, health checks, request body size ceiling + background loops (reminder emails, daily event-sheet sync)
    ├── config.py           # DATA_DIR — where uploaded files are written; also whether this is the live deployment
    ├── get_drive_refresh_token.py  # One-time helper for Google Drive resume-sync setup
    ├── database.py         # Postgres engine (DATABASE_URL), session factory, seed.py's local-database guard
    ├── alembic.ini         # Alembic config (the database URL comes from alembic/env.py, not this file)
    ├── alembic/            # Migration environment and versions/ — see Database Migrations
    ├── chapter_data.py     # Real chapter structure (committees, org chart, dues product) — shared by both seeders
    ├── seed.py             # Dev seed data: test members, chair/E-Board accounts (refuses any non-local database)
    ├── bootstrap.py        # Production installer: structure only, plus the three top-tier seats
    ├── Dockerfile          # Container image used for deployment
    ├── requirements.txt    # Runtime dependencies
    ├── requirements-dev.txt # Test tooling (includes requirements.txt)
    ├── routes/             # APIRouters: admin, auth, committees, events, gallery, notifications, password reset, resume, shop
    ├── uploads/            # Uploaded resumes, product images, and gallery photos (gitignored, created on first upload)
    ├── models/             # SQLModel table definitions (user/, shop/, committee, event, notification, ...)
    ├── security/           # JWT creation and password hashing
    ├── services/           # DB session deps, user/committee/reminder/email/Drive-sync/password-reset/shop/Square-payment/event-sheet-sync/reporting-structure/QR-attendance/event-statistics/event-visibility services, rate limiter, request body size limit, forwarded-proto (https) scheme fix, HIBP breached-password check
    ├── validators/         # Input validation (email normalization)
    └── tests/              # pytest suite (runs against a dedicated `shpe_test` Postgres database; requires the database container to be running)
```

## Frontend conventions

- Pages live in `src/pages/` (one file per route), reusable UI in `src/components/`, and routes are
  declared in `App.jsx`.
- **Every page calls `useDocumentTitle` once**, near the top. `index.html` carries a single static
  `<title>` for all routes, so a page that skips it inherits the *previous* page's title.
- Long lists paginate client-side with `usePagination` + `<Pagination>`. Counts and badges must keep
  reading the **full** array, never `pageItems`. Call the hook above any early `return`, and pass
  `resetKey` when a tab, search, or filter sits above the list.
- Design tokens (brand colors, gradients, radii, shadows) live in `src/styles.css` under `:root`.
  Reference the tokens rather than hardcoding hex values. Tailwind v4 utilities first; custom CSS
  only where Tailwind can't do it.
- `--header-height` (80px) is a guarantee, not a guess. `.headerRow` height, `.brandMark img`
  height, and the `inset` box-shadow are load-bearing together — change one and `.main`'s padding,
  the dues banner's offset, and every `calc(100vh - …)` drift apart silently. Full-viewport elements
  subtract it: `calc(100vh - var(--header-height))`. Never give a page its own top offset instead.

## Dates and times

The backend stores and compares **naive UTC** (`utcnow()` from `services/time_services.py`), which
maps to Postgres `TIMESTAMP WITHOUT TIME ZONE`. Don't use `datetime.utcnow()` — it's deprecated on
Python 3.12.

On the frontend, append `'Z'` when constructing a Date, or the browser reads the timestamp as local
time and events display hours off:

```js
new Date(event.start_time + 'Z')
```

## Pages

Each page sets its own browser tab title (`Calendar | SHPE UH`, `Shop | SHPE UH`, and so on), so history entries and bookmarks are distinguishable; the home page keeps the full site title. Product and order pages title themselves from the product name and the order code.

| Path | Description | Auth Required |
|---|---|---|
| `/` | Home | No |
| `/about` | About SHPE UH — history, pillars, and the E-Board & Chairs roster (with contact emails) | No |
| `/membershpe` | Membership info | No |
| `/sponsors` | Sponsors | No |
| `/gallery` | Public approved photos grouped by semester/year, plus member photo submission (sign-in required only to submit) | No |
| `/calendar` | Events calendar (with "Remind me by email") | No |
| `/shop` | Merch shop — browse products, filter by category | No |
| `/shop/:productId` | Product detail — pick a size (apparel) and quantity, add to cart | No |
| `/shop/checkout` | Two-step checkout: contact details, then payment (Square card element + Apple Pay / Google Pay where supported; simulated when Square isn't configured) | No |
| `/shop/order/:code` | Order confirmation and live status (looked up by code + buyer email) | No |
| `/signin` | Sign in | No |
| `/signup` | Sign up — five steps (Account, Academic, Personal, Background, Membership), each validated before you can continue; ends on a "check your email" screen | No |
| `/verify-email` | Confirm a new account from the emailed link, then route into chapter-dues checkout. A link that was already used shows that the account is verified and points to sign-in, rather than reporting a failure | No |
| `/forgot-password` | Request a password-reset email | No |
| `/reset-password` | Choose a new password (opened from the emailed link) | No |
| `/dashboard` | Member dashboard | Yes |
| `/committees` | Browse/join committees, chair tools | Yes |
| `/profile` | Profile info, PDF resume, and order history | Yes |
| `/members` | Member directory and org chart: chapter stats, member lookup, role assignment, and the reporting structure, across All/E-Board/Chairs/Structure tabs. Click any member for their full profile — contact details, academics, background answers, committees, and resume — president and VPs only | Yes |
| `/shop-manager` | Shop-management tools (products, orders, notifications, settings) — shop admins only (comms director / marketing chair / president) | Yes |
| `/gallery-manager` | Paginated photo moderation with Pending/Approved/Rejected/All filters — president, both VPs, communication director, and marketing chair only | Yes |
| `/my-events` | Chair/E-Board Events page: My Events / All Events tabs, a QR modal (Sign in/Sign out, fullscreen "present" view, live scan counter), a read-only attendance roster, and a per-event statistics panel. Both tabs open on the next upcoming event and page backwards into the past | Yes |
| `/attend/:code` | Mobile QR check-in flow — reached only by scanning a code, not linked from navigation. No site header/footer/cart; renders its own "sign in to continue" screen if you're signed out | No |

The endpoints behind these pages are listed in [api.md](api.md); what the features actually do is
in [features.md](features.md).
