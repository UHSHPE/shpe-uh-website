# SHPE UH Website

The official website for the **Society of Hispanic Professional Engineers (SHPE) — University of Houston** chapter. A full-stack web application for managing chapter membership, events, committees, and internal communications.

## Features

- **Authentication** — Secure sign-up and login with JWT tokens and Argon2 password hashing
- **Password Reset** — "Forgot password?" flow: a single-use reset link (valid 1 hour) is emailed to the member's CougarNet address; resetting signs out all existing sessions. Login and reset requests are rate-limited
- **Events Calendar** — Public calendar displaying upcoming chapter events
- **Email Reminders** — Members can request an email reminder for any upcoming event (sent 24h before, handled by a background loop)
- **Dashboard** — Personalized member dashboard with upcoming events and notifications
- **Profile** — Members can view their profile details and upload a PDF resume (view, replace, or remove it)
- **Committees** — Browse, join, and leave committees; chairs and co-chairs can view rosters and broadcast messages to members
- **Notifications** — In-app notification system for committee activity (joins, messages)
- **Merch Shop** — Public storefront with cart and checkout (payment **simulated** in v1; Square planned). Buyers pay online and pick up in person at a chapter event. The comms director and marketing chair manage products, orders, and shop settings from their profile page and are notified of every new order; buyers get an email when their order is ready for pickup
- **Gallery** — Photo gallery with an approval workflow
- **Instagram Feed** — Home-page grid of the chapter's latest Instagram posts, pulled live from a public Behold feed
- **Points** — Member points tracking

## Tech Stack

**Frontend**
- React 19, React Router v7
- Vite, Tailwind CSS v4, Framer Motion
- Axios

**Backend**
- FastAPI, SQLModel (SQLAlchemy 2), SQLite
- PyJWT, pwdlib (Argon2), Pydantic v2, Uvicorn
- slowapi (rate limiting)
- pytest + httpx for the test suite

## Prerequisites

- **Node.js** v18+ and npm
- **Python** 3.11+
- **Git**

## Getting Started

### 1. Clone the repository

```bash
git clone <repo-url>
cd shpe-uh-website
```

### 2. Backend setup

```bash
cd backend

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate       # Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

Create `backend/.env` (see [Environment Variables](#environment-variables)):

```bash
echo "SECRET_KEY=$(python3 -c 'import secrets; print(secrets.token_hex(32))')
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
FRONTEND_URL=http://localhost:5173" > .env
```

Then seed and run:

```bash
# Seed the database with committees, chairs, and test data (run once)
python seed.py

# Start the development server
python main.py
# or: uvicorn main:app --reload
```

Backend runs at **http://localhost:8000**. Interactive API docs at **http://localhost:8000/docs**.

### 3. Frontend setup

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
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | Token lifetime in minutes | `30` |
| `FRONTEND_URL` | No | Base URL of the frontend, used to build password-reset links in emails. Defaults to `http://localhost:5173` | `http://localhost:5173` |
| `SMTP_HOST` | No | SMTP server for reminder emails. **Unset = dev mode:** emails print to the console instead | `smtp.gmail.com` |
| `SMTP_PORT` | No | SMTP port | `587` |
| `SMTP_USER` | No | Sender address / SMTP login | `chapter@example.org` |
| `SMTP_PASSWORD` | No | SMTP password (use an app password for Gmail) | — |
| `EMAIL_FROM` | No | From header; defaults to `SMTP_USER` | `SHPE UH <noreply@example.org>` |

### `frontend/.env.local`

| Variable | Required | Description | Example |
|---|---|---|---|
| `VITE_API_URL` | Yes | Backend base URL | `http://localhost:8000` |
| `VITE_BEHOLD_FEED_URL` | No | Public [Behold](https://behold.so) JSON feed for the home-page Instagram grid. If unset/unreachable, the grid shows a shimmer placeholder | `https://feeds.behold.so/<feed-id>` |

> **Never commit `.env` or `.env.local` to version control.**

## Seeded Accounts

`python seed.py` creates a test member, all 14 committees and their chairs/co-chairs (22 chair accounts), a comms director, the shop settings row, and four sample shop products. All seeded accounts use the password `password123`.

| Account | Email | Role |
|---|---|---|
| Test member | `test@cougarnet.uh.edu` | Member |
| Committee chairs | `<first>.<last>@cougarnet.uh.edu` (e.g. `angel.montoya@cougarnet.uh.edu`) | Chair of their committee |
| Comms director | `comms.director@cougarnet.uh.edu` | Communication Director (shop admin) |

The seeded marketing chair (`valeria.zabala@cougarnet.uh.edu`) is the other shop admin.

The full chair roster lives in `backend/seed.py` (`COMMITTEE_ROSTER`).

> **Note:** if you reseed (`rm database.db && python seed.py`) while the backend is running, restart it — the server keeps a handle to the old database file and will serve stale data.

## Project Structure

```
shpe-uh-website/
├── frontend/
│   └── src/
│       ├── api/            # Axios instance + all API call functions (api.js)
│       ├── components/     # Header, Footer, Avatar, GalleryApproved, PrivateRoute, cart drawer, shop-manager panel, ...
│       ├── context/        # AuthContext (session), CartContext (shop cart, persisted locally)
│       ├── utils/          # Shared helpers (money formatting, order-status styling)
│       ├── pages/          # One file per route
│       └── App.jsx         # Route definitions
└── backend/
    ├── main.py             # FastAPI app: routers + background reminder-email loop
    ├── database.py         # SQLite engine and session factory
    ├── seed.py             # Committees, chair roster, and dev seed data
    ├── routes/             # APIRouters: auth, committees, events (+ reminders), notifications, password reset, resume, shop
    ├── uploads/            # Uploaded resume PDFs and product images (gitignored, created on first upload)
    ├── models/             # SQLModel table definitions (user/, shop/, committee, event, notification, ...)
    ├── security/           # JWT creation and password hashing
    ├── services/           # DB session deps, user/committee/reminder/email/password-reset services, rate limiter
    ├── validators/         # Input validation (email normalization)
    └── tests/              # pytest suite (in-memory SQLite fixtures in conftest.py)
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
| `/shop/checkout` | Two-step checkout: contact details, then (simulated) payment | No |
| `/shop/order/:code` | Order confirmation and live status (looked up by code + buyer email) | No |
| `/signin` | Sign in | No |
| `/signup` | Sign up | No |
| `/forgot-password` | Request a password-reset email | No |
| `/reset-password` | Choose a new password (opened from the emailed link) | No |
| `/dashboard` | Member dashboard | Yes |
| `/committees` | Browse/join committees, chair tools | Yes |
| `/profile` | Profile info, PDF resume, order history — plus the shop-management panel for shop admins (comms director / marketing chair) | Yes |

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/login` | No | Authenticate and receive a JWT token (rate limited: 5/minute) |
| POST | `/signup` | No | Register a new account |
| POST | `/password-reset/request` | No | Email a reset link if the account exists (always returns 200; rate limited: 3/hour) |
| POST | `/password-reset/confirm` | No | Set a new password using a valid reset token |
| GET | `/me` | Yes | Current user profile (includes points and `resume_filename`) |
| POST | `/me/resume` | Yes | Upload a PDF resume (PDF only, ≤5 MB) |
| GET | `/me/resume` | Yes | Download the current user's resume |
| DELETE | `/me/resume` | Yes | Remove the current user's resume |
| GET | `/events` | No | All events (powers the public calendar) |
| GET | `/events/upcoming?days=7` | Yes | Upcoming events within N days |
| POST | `/events/{id}/remind` | Yes | Set an email reminder for an event |
| DELETE | `/events/{id}/remind` | Yes | Cancel an unsent reminder |
| GET | `/events/reminders/me` | Yes | Current user's active reminders |
| GET | `/committees` | Yes | All committees with membership status and chair contacts |
| POST | `/committees/{id}/join` | Yes | Join a committee (notifies every chair) |
| DELETE | `/committees/{id}/leave` | Yes | Leave a committee |
| GET | `/committees/{id}/members` | Chair only | Roster with name, email, phone |
| POST | `/committees/{id}/messages` | Chair only | Broadcast a message to members |
| GET | `/committees/{id}/messages` | Member/Chair | Committee messages, newest first |
| GET | `/notifications` | Yes | Current user's notifications, newest first |
| POST | `/notifications/{id}/read` | Yes | Mark a notification as read |
| GET | `/shop/settings` | No | Shop settings (storefront tagline + per-order item cap) |
| GET | `/shop/products` | No | Active shop products |
| GET | `/shop/products/{id}` | No | One active product (type, sizes, price) |
| GET | `/shop/products/{id}/image` | No | Product image |
| POST | `/shop/orders` | No | Place an order after the (simulated) payment; total computed server-side (rate limited: 10/minute) |
| GET | `/shop/orders/{code}?email=` | No | Buyer order lookup — requires the matching buyer email |
| GET | `/shop/orders/me` | Yes | Signed-in member's order history |
| PATCH | `/shop/settings` | Shop admin | Update the tagline and/or per-order item cap |
| POST | `/shop/products` | Shop admin | Create a product |
| PATCH | `/shop/products/{id}` | Shop admin | Edit a product / toggle availability |
| DELETE | `/shop/products/{id}` | Shop admin | Remove a product |
| POST | `/shop/products/{id}/image` | Shop admin | Upload a product image (PNG/JPEG/WebP, ≤5 MB) |
| GET | `/shop/admin/products` | Shop admin | All products including sold-out |
| GET | `/shop/orders?status=` | Shop admin | All orders, filterable by status |
| PATCH | `/shop/orders/{id}` | Shop admin | Advance order status (`ready`/`picked_up`/`cancelled`) or save a note |

"Shop admin" = a user whose role is **Communication Director** or **Marketing Chair**.

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
- **No inventory is tracked.** Products are toggled sold-out/available, and each order is limited to a configurable number of units per item (default 5).
- Shop administration belongs to the **Communication Director** and **Marketing Chair** roles: they manage products (create/edit, images, sold-out toggle), the order queue, and shop settings (storefront tagline + the per-item order cap) from the **Shop Manager** panel on their profile page.

## Running Tests

```bash
cd backend
source .venv/bin/activate
python -m pytest tests/
```

Tests run against an in-memory SQLite database (no setup needed) using fixtures from `tests/conftest.py`.
