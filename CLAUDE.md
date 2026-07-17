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
      components/         # Header, Footer, Avatar, GalleryApproved, PrivateRoute, CartDrawer, ProductImage, StatusPill, MyOrders, ShopManager, shopIcons
      context/            # AuthContext, CartContext (cart lines + drawer + toast, persisted to localStorage)
      utils/shop.js       # formatCents, STATUS_META, isShopManager, order helpers
      pages/              # home, about, gallery, membershpe, sponsors, get-involved, dashboard, committees, profile, shop, shop-product, shop-checkout, shop-order
      App.jsx             # Routes (+ renders CartDrawer/ShopToast globally)
  backend/
    main.py               # FastAPI app: includes routers + background reminder email loop (60s)
    database.py           # SQLite engine + session factory
    seed.py               # Seeds test user, all 14 committees with their real chairs/co-chairs (22 chair users), a comms director (shop admin), the shop-settings row, 4 shop products, and sample events — run once: python seed.py
    routes/               # APIRouters: auth_routes, committee_routes, event_routes (incl. reminders), notification_routes, pw_reset_routes, resume_routes, shop_routes
    uploads/resumes/      # Uploaded resume PDFs, one per user (user_<id>.pdf); gitignored, created on first upload
    uploads/products/     # Product images, one per product (product_<id>.<ext>); gitignored, created on first upload
    models/               # SQLModel table definitions (user/ incl. pw_reset_token.py, shop/ (product.py, order.py, shop_settings.py), committee.py, committee_message.py, notification.py, event.py, event_reminder.py)
    security/             # jwt.py (token creation), hashing.py (Argon2)
    services/             # dependencies.py, user_services.py, committee_services.py, reminder_services.py, email_services.py, time_services.py, auth_user.py, pw_reset_services.py, rate_limit.py, shop_services.py, square_services.py
    validators/           # email.py (normalize_email)
    tests/                # pytest suite; conftest.py has in-memory-DB fixtures (client, session, user) + make_user/make_event helpers; shop_tests/conftest.py adds manager_client/make_product/sent_emails
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

# Optional — Square card payments for the shop. Without these, checkout runs
# in simulated dev mode (console-printing no-op charge). Setup steps in README.
SQUARE_ACCESS_TOKEN=<from developer.squareup.com>
SQUARE_LOCATION_ID=<location id of the same Square application>
SQUARE_ENVIRONMENT=sandbox   # or "production"; must match the token
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
| `/shop` | `pages/shop.jsx` (public storefront) | No |
| `/shop/:productId` | `pages/shop-product.jsx` (product detail) | No |
| `/shop/checkout` | `pages/shop-checkout.jsx` (contact → payment: Square card element when `VITE_SQUARE_*` set, simulated otherwise) | No |
| `/shop/order/:code` | `pages/shop-order.jsx` (confirmation + status; lookup needs buyer email) | No |
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
| POST | `/me/resume` | Yes | Upload a PDF resume (multipart `file`); validates PDF type, ext, `%PDF` magic bytes, and ≤5 MB (400/413 otherwise). Sets `User.resume_filename` |
| GET | `/me/resume` | Yes | Download the current user's resume PDF (`FileResponse`); 404 if none |
| DELETE | `/me/resume` | Yes | Remove the current user's resume (204) |
| POST | `/events/{id}/remind` | Yes | Set an email reminder for an event (404 unknown event, 409 already set, 400 already started) |
| DELETE | `/events/{id}/remind` | Yes | Cancel an unsent reminder (404 if none active) |
| GET | `/events/reminders/me` | Yes | Current user's active (unsent) reminders |
| GET | `/shop/settings` | No | Shop settings singleton (tagline + `order_item_cap`) — the storefront reads both |
| PATCH | `/shop/settings` | Shop admin | Update tagline and/or per-order item cap |
| GET | `/shop/products` | No | Active products only, ordered by created_at |
| GET | `/shop/products/{id}` | No | One product; 404 for unknown OR inactive |
| GET | `/shop/products/{id}/image` | No | Product image (FileResponse) |
| POST | `/shop/orders` | Optional | Charge card via Square (402 + no order on decline; dev-mode no-op when unconfigured), then create order (rate limited 10/minute); server recomputes total and charges exactly that; links `user_id` if a valid bearer token rides along |
| GET | `/shop/orders/me` | Yes | Signed-in member's order history (defined BEFORE `/orders/{code}` so "me" isn't swallowed) |
| GET | `/shop/orders/{code}?email=` | No | Buyer lookup; wrong/unknown code or email → one generic 404 |
| POST | `/shop/products` | Shop admin | Create product (201) |
| PATCH | `/shop/products/{id}` | Shop admin | Edit / toggle `is_active` |
| DELETE | `/shop/products/{id}` | Shop admin | Hard delete (204); order lines keep snapshots |
| POST | `/shop/products/{id}/image` | Shop admin | Upload PNG/JPEG/WebP ≤5 MB (magic-byte checked) |
| GET | `/shop/admin/products` | Shop admin | All products incl. inactive (admin table) |
| GET | `/shop/orders?status=` | Shop admin | All orders, filterable by status |
| PATCH | `/shop/orders/{id}` | Shop admin | `{status?, notes?}`; illegal transition → 400; `ready` emails buyer |

## Committee leadership, notifications & messaging
- Committees support **co-chairs**: a committee's chairs are the users with a `CommitteeMembership` row where `is_chair=True` (one row per co-chair). `CommitteeOut.chairs` is a **list** of `ChairOut` (name + email) and `CommitteeOut.is_chair` reflects the current user's membership row.
- `Committee.chair_role` (a `Role` enum value, nullable) still maps each committee to one chair role (1:1). Co-chairs of the same committee **share the same Role** (e.g. both MentorSHPE co-chairs have `Role.mentorshpe_chair`). Chair-only endpoints are gated by `require_chair`, which checks `user.role == committee.chair_role` — so seed both the role on the user AND the `is_chair` membership row, or chairs will display but lack permissions (or vice versa).
- The real chair roster lives in `seed.py` (`COMMITTEE_ROSTER`): 14 committees, 22 chairs. Seeded chair logins are `<first>.<last>@cougarnet.uh.edu` / `password123`.
- **Chair contact email shown in `ChairOut` is role-based, not the user's own email.** `chair_contact_email()` in `services/committee_services.py` maps each `chair_role` to a shared committee address (`CHAIR_EMAILS`, e.g. `academics@shpeuhchair.org`) so co-chairs display the same contact (matches the public About page). Roles with no published address (currently just Member Relations) fall back to the chair's `personal_email`. The frontend Committees card therefore keys chairs by name, **not** email, since co-chairs share one. Changing this is a code edit (no re-seed needed) — just restart the backend.
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

## Merch shop (spec: specs/shop/shop-page.md)
- **Payments — Square Web Payments SDK + Payments API** (`services/square_services.py`). Configured via `SQUARE_ACCESS_TOKEN` + `SQUARE_LOCATION_ID` (+ `SQUARE_ENVIRONMENT`, default sandbox — all read at **call time**) on the backend, `VITE_SQUARE_APP_ID` + `VITE_SQUARE_LOCATION_ID` on the frontend. The checkout page loads `square.js` from Square's CDN (required — it serves the secure card iframe; sandbox vs prod build is picked by the `sandbox-` app-id prefix), renders the card element in the payment step, and `card.tokenize()` swaps card data for a one-time token — card numbers never touch our server (PCI stays minimal). No webhooks: the charge response is synchronous.
- **Charge order-of-operations in `POST /shop/orders`: validate → charge → persist.** The route calls `shop_services.validate_order_items` (returns `(lines, total_cents)` without persisting), charges that server-side total via `square_services.charge_card`, then passes the same `validated` pair into `create_order` so the stored total always equals the charged amount. A declined/failed charge raises `PaymentError` (buyer-safe message) → 402 with **no order row**; missing token while configured → 400 before any charge. `Order.square_payment_id` records the charge (internal — NOT in `OrderOut`). The route is sync, so the blocking Square client already runs in FastAPI's threadpool — if it's ever made `async def`, wrap the charge in `asyncio.to_thread`.
- **Wallets (Apple Pay / Google Pay)** ride the same flow — no backend changes. The payment-step effect builds a `paymentRequest` (display amount only; the backend still charges its own recomputed total) and tries `payments.applePay()` / `payments.googlePay()`; each **throws where unsupported** (Apple Pay: sandbox, non-Safari, unregistered domain — expected, not a bug) and its button just stays hidden. `handlePay(walletMethod)` tokenizes whichever method is passed (the card element when null); a wallet-sheet `Cancel` result is silently ignored. Gotchas: the `#google-pay-button` container must exist in the DOM **before** `attach()` (it renders always, `display:none` until ready); the Apple Pay button is our own `<button className="applePayBtn">` (native `-apple-pay-button` vendor appearance — CSS lives in `styles.css`, Tailwind can't express it); the init effect depends on `[step, subtotalCents]` so a cart change rebuilds the paymentRequest. Going live with Apple Pay needs a one-time domain registration (Square Developer Dashboard → Apple Pay) + hosting Square's verification file at `frontend/public/.well-known/apple-developer-merchantid-domain-association`.
- **Unconfigured = dev mode, end to end** (same pattern as `email_services.py`): `charge_card` prints `[square dev mode] would charge …` and returns None, orders are created with `square_payment_id=None`, and the frontend keeps the demo card block + fake 1.3s delay. Tests never hit the real API: an autouse `disable_square_payments` fixture in `tests/conftest.py` clears all `SQUARE_*` env vars (`load_dotenv()` leaks `backend/.env` into the test process); configured-mode tests monkeypatch `square_services.is_configured`/`charge_card` (called as module attributes from `shop_routes`, so patching `services.square_services` works). Dep: `squareup` (lazy-imported inside `square_services.py`, so dev mode works without it).
- **Models** (`models/shop/`): `Product` (with `ProductType` enum `apparel`/`item`; `sizes` is a `list[str] | None` stored via `sa_column=Column(JSON)`; there is **no stock column** — no inventory is tracked, `is_active` is the soft-delete/sold-out toggle), `Order` + `OrderItem` (`OrderStatus`: `paid → ready → picked_up`, plus `cancelled`; terminal is `picked_up`, NOT `completed`), and `ShopSettings` (singleton row: `tagline` + `order_item_cap`, defaults in the model; always access via `shop_services.get_shop_settings()`, which creates the row on first use). Money is integer **cents**; timestamps naive UTC via `utcnow()`. All three modules are imported in `database.py`.
- **Per-order quantity cap** (no inventory): `create_order` rejects any line item whose quantity exceeds `ShopSettings.order_item_cap` (default 5) with a 400. Admins change the cap (and the storefront tagline) via `PATCH /shop/settings`; the frontend `CartContext` fetches the cap once and clamps add-to-cart and the steppers client-side.
- **`OrderItem` snapshots `product_name` and `unit_price_cents`** at purchase time, so orders stay readable after a product is edited or hard-deleted.
- **Order codes**: `SHPE-` + 4 chars from an alphabet without lookalikes (no 0/O/1/I) — `generate_order_code` retries until unique.
- **State machine** lives in `shop_services.ALLOWED_TRANSITIONS`; `apply_status_transition` stamps `ready_at`/`picked_up_at` and emails the buyer on `ready`. New orders create a `Notification` row + email for **every shop admin** (to their `personal_email`); the buyer gets NO email at order time.
- **Roles**: there is **no dedicated shop-manager role**. Shop admin rides on `SHOP_ADMIN_ROLES = {Role.comm_director, Role.marketing_chair}` (defined in `models/user/user_enums.py`); `require_shop_admin` in `services/dependencies.py` gates admin endpoints (mirrors `require_chair`). Giving `marketing_chair` shop access does NOT affect their committee-chair permissions (`require_chair` checks `role == committee.chair_role`, still true). Seed provides `comms.director@cougarnet.uh.edu` (comm_director) and Valeria Zabala (`valeria.zabala@cougarnet.uh.edu`, marketing_chair from COMMITTEE_ROSTER), both `password123`.
- **`get_optional_user`** in `services/dependencies.py` (`OAuth2PasswordBearer(auto_error=False)`): returns the user for a valid token, None otherwise (never 401s). Used by `POST /shop/orders` so signed-in buyers' orders link to `user_id`. In tests, override it explicitly — the `client` fixture only overrides `get_current_user`.
- **Order lookup privacy**: `GET /shop/orders/{code}` requires a matching `?email=` (normalized); unknown code and wrong email return the same generic 404. Never reveal a code exists.
- **Route ordering**: `/shop/orders/me` is defined before `/shop/orders/{order_code}` in `shop_routes.py` — keep it that way or "me" matches the code param.
- **Product images** mirror the resume pattern: `PRODUCT_IMAGE_DIR` module constant (tests monkeypatch it to `tmp_path`), deterministic filename `product_<id>.<ext>`, content-type + magic-byte + ≤5 MB validation (PNG/JPEG/WebP).
- **Tests** in `tests/shop_tests/`; its `conftest.py` adds `manager_client` (auth'd as a `Role.comm_director` user — pass `role=Role.marketing_chair` to `make_manager` to cover the other admin role), `make_product`, and `sent_emails` (monkeypatches `shop_services.send_email`). Do NOT use `client` and `manager_client` in the same test — both override `get_current_user` on the same app and the last fixture wins.
- **Frontend**: cart state lives in `context/CartContext.jsx` (localStorage key `shpe_cart`, lines merge by product+size, drawer + 2s toast included); `CartDrawer`/`ShopToast` render once in `App.jsx`. Category filter pills on `/shop` are derived from the `product_type`s present — never hardcode "Stickers". `createShopOrder` sends `authHeaders()` (empty for guests) so member orders link. After checkout the confirmation gets the order via route state; revisits look it up with code+email from sessionStorage (`shpe_last_order`), `?email=`, or a prompt. The Shop Manager panel (Overview / Products / Orders / Notifications / Settings tabs) + My Orders live inside `pages/profile.jsx` (`components/ShopManager.jsx`, `components/MyOrders.jsx`); the admin check is `isShopManager(user)` from `utils/shop.js`, which matches the two `SHOP_ADMIN_ROLES` role strings. The `/shop` hero tagline comes from `GET /shop/settings` with a hardcoded product-agnostic fallback.
- **Shop styling tokens** (page bg, gray ramp additions, the four status color sets `--status-*`, `--gradient-success`, `--font-mono`, `--placeholder-hatch`) are in `styles.css` `:root` under "Shop"; keyframes are prefixed `shop*` (`shopPulse`, `shopSlideInRight`, …). The design handoff lives in `specs/shop/design_handoff_merch_shop/`.

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
