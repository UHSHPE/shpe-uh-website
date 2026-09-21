# API reference

Every endpoint the backend serves, grouped the way the routers are laid out in
`backend/routes/`. Auth column: **No** is public, **Yes** needs any signed-in member,
and anything else names the role required.

Routers live in `backend/routes/` — `auth_routes.py`, `event_routes.py`, `shop_routes.py`,
`committee_routes.py`, `admin_routes.py`, `dues_routes.py`, `leaderboard_routes.py`,
`notification_routes.py`, `pw_reset_routes.py`, `resume_routes.py`, `gallery_routes.py`. See
[architecture.md](architecture.md) for how a request reaches them.

While the backend is running locally you can also browse and *call* these from the
interactive docs at <http://localhost:8000/docs>. That page is a development convenience
only — under `ENVIRONMENT=production` the app serves no schema at all and `/docs`,
`/redoc`, and `/openapi.json` all return 404.


| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | No | Liveness probe for the hosting platform. Deliberately does not query the database, so a momentary lock can't get a healthy server restarted |
| GET | `/health/db` | No | Readiness check that does query the database — for manual verification after a deploy |
| POST | `/login` | No | Authenticate and receive a JWT token (rate limited, configurable via `RATE_LIMIT_LOGIN`); 403 until the account's email is verified; 429 after too many failed attempts (temporary account lock) |
| POST | `/signup` | No | Register a new account (unverified) and email a verification link; returns a message, not a token (rate limited, configurable via `RATE_LIMIT_SIGNUP`). CougarNet email and PSID are each unique to one account — a conflict with a verified account is rejected, while a conflict with an unverified one replaces that pending signup and sends a fresh link. If the email cannot be sent the request fails rather than claiming success — sign up again to retry |
| POST | `/verify-email` | No | Confirm a signup with the emailed token and receive a JWT token. Links are single-use; re-using one reports that the account is already verified (and issues no token) rather than looking like a failure — mail scanners routinely open the link before the member does |
| POST | `/password-reset/request` | No | Email a reset link if the account exists (always returns 200; rate limited, configurable via `RATE_LIMIT_PASSWORD_RESET`) |
| POST | `/password-reset/confirm` | No | Set a new password using a valid reset token |
| GET | `/me` | Yes | Current user profile (includes points and `resume_filename`) |
| POST | `/me/resume` | Yes | Upload a PDF resume (PDF only, ≤2 MB; rate limited, configurable via `RATE_LIMIT_UPLOAD`); renamed to `First_Last_PSID.pdf` and synced to Google Drive when configured |
| GET | `/me/resume` | Yes | Download the current user's resume |
| DELETE | `/me/resume` | Yes | Remove the current user's resume (also removed from Google Drive; if Drive is unreachable the local copy is still removed and the backend keeps its reference to the Drive file, so a later upload replaces it instead of leaving a stray copy) |
| POST | `/gallery/photos` | Yes | Submit a PNG/JPEG photo (≤2 MB; rate limited via `RATE_LIMIT_UPLOAD`). It starts pending and is assigned Spring/Fall plus year from the current date |
| GET | `/gallery/photos` | No | Metadata (`id`, semester, year) for approved, non-deleted gallery photos |
| GET | `/gallery/photos/{photo_id}/image` | No | Retrieve an approved gallery image. Pending, rejected, deleted, or missing photos return 404 |
| GET | `/gallery/admin/photos?status=` | Gallery admin | List non-deleted submissions with submitter, review status, reviewer, timestamps, semester, and year; optionally filter by `pending`, `approved`, or `rejected` |
| GET | `/gallery/admin/photos/{photo_id}/image` | Gallery admin | Retrieve a private thumbnail/image for moderation, regardless of review status |
| PATCH | `/gallery/admin/photos/{photo_id}/update` | Gallery admin | Approve or reject a photo and optionally correct its semester/year. First approval awards one point exactly once |
| DELETE | `/gallery/admin/photos/{photo_id}` | Gallery admin | Remove the stored image and soft-delete its record; previously awarded points remain |
| GET | `/events` | No | All events (powers the public calendar). Events removed from the tracker sheet are hidden |
| GET | `/events/upcoming?days=7` | Yes | Upcoming events within N days. Events removed from the tracker sheet are hidden |
| POST | `/events/{id}/remind` | Yes | Set an email reminder for an event |
| DELETE | `/events/{id}/remind` | Yes | Cancel an unsent reminder |
| GET | `/events/reminders/me` | Yes | Current user's active reminders |
| POST | `/events/attend` | Yes | Record a QR scan and award points; the scanned code itself says whether it's a sign-in or a sign-out. Scanning twice is safe — it never awards twice. Too early (more than ~1 hour before the event) is rejected, and a code for an event removed from the tracker sheet stops working |
| GET | `/events/code/{code}` | Optional | Preview a scanned code before recording anything — event name/time/location and whether check-in is open yet, expired, or already recorded (fills in with a valid token) |
| GET | `/events/mine` | Chair/E-Board | Events they host, with the sign-in/sign-out codes to render as QR |
| GET | `/events/all` | Chair/E-Board | Every chapter event, with the QR codes for the events this caller may present (every event for E-Board, hosted events for a chair) |
| GET | `/events/{id}/attendance` | Chair only | Attendance roster for one of their events |
| GET | `/events/{id}/stats` | Chair/E-Board | Aggregate statistics for any event — turnout, sign-outs, average time at the event, first-time attendees, guests brought, and classification / college / major / membership breakdowns. Counts only; no attendee is named |
| GET | `/events/{id}/scan-count` | Chair/E-Board | Live sign-in/sign-out counts for one event, for the QR modal to poll |
| GET | `/leaderboard` | No | Public chapter points leaderboard: every verified member, ranked by total points, with a breakdown of where those points came from across the 5 Core Pillars |
| GET | `/committees` | Yes | All committees with membership status and chair contacts |
| POST | `/committees/{id}/join` | Yes | Join a committee (notifies every chair). Joining again when you are already a member is a no-op that returns 200 and notifies nobody; joins are rate limited per account (`RATE_LIMIT_COMMITTEE_JOIN`). The internal E-Board rows are not joinable and return 404 |
| DELETE | `/committees/{id}/leave` | Yes | Leave a committee |
| GET | `/committees/{id}/members` | Chair only | Roster with name, email, phone |
| POST | `/committees/{id}/messages` | Chair only | Broadcast a message to members |
| GET | `/committees/{id}/messages` | Member/Chair | Committee messages, newest first. Members read only committees they can actually join; chairs of the internal E-Board rows still read theirs |
| GET | `/notifications` | Yes | Current user's notifications, newest first |
| POST | `/notifications/{id}/read` | Yes | Mark a notification as read |
| GET | `/shop/settings` | No | Shop settings (storefront tagline + per-order item cap) |
| GET | `/shop/products` | No | Shop products that are active and not retired |
| GET | `/shop/products/{id}` | No | One product (type, sizes, price); 404 if unknown, hidden, or retired |
| GET | `/shop/products/{id}/image` | No | Product image |
| POST | `/shop/orders` | No | Charge the card via Square (when configured), then place the order; total computed server-side (rate limited, configurable via `RATE_LIMIT_ORDER`). A declined card returns 402 with a single generic message — the specific reason goes to the server log, not the buyer — and too many declines from one connection returns 429 (`RATE_LIMIT_FAILED_CHARGE`) |
| GET | `/shop/orders/{code}?email=` | No | Buyer order lookup — requires the matching buyer email |
| GET | `/shop/orders/me` | Yes | Signed-in member's order history |
| PATCH | `/shop/settings` | Shop admin | Update the tagline and/or per-order item cap |
| POST | `/shop/products` | Shop admin | Create a product |
| PATCH | `/shop/products/{id}` | Shop admin | Edit a product / toggle availability |
| DELETE | `/shop/products/{id}` | Shop admin | Retire a product — hides it from the shop and keeps it restorable (nothing is deleted); the dues product can't be retired |
| POST | `/shop/products/{id}/restore` | Shop admin | Restore a retired product (it comes back hidden) |
| POST | `/shop/products/{id}/image` | Shop admin | Upload a product image (PNG/JPEG/WebP, ≤2 MB; rate limited, configurable via `RATE_LIMIT_UPLOAD`) |
| GET | `/shop/admin/products` | Shop admin | All products, including hidden and retired |
| GET | `/shop/orders?status=` | Shop admin | All orders, filterable by status |
| PATCH | `/shop/orders/{id}` | Shop admin | Advance order status (`ready`/`picked_up`/`cancelled`) or save a note. An order containing the dues product can never be cancelled — chapter dues are final once paid |
| GET | `/admin/members?search=&paid=&role=` | President / VP | Member directory with dues status; filter by name/email/PSID search, paid, or role |
| GET | `/admin/stats` | President / VP | Chapter stats: accounts, dues paid/unpaid, national members, classification/role/shirt-size breakdowns |
| POST | `/admin/dues/sync` | President / VP | Import membership-sheet dues and return aggregate counts; overlapping sync requests return 409 |
| GET | `/admin/roles` | President / VP | Every role the caller may assign (a VP's list omits President and both VP roles) |
| PATCH | `/admin/members/{id}/role` | President / VP | Assign a member's role (chair roles also sync the committee's chair membership). A VP can't assign or change President or VP roles |
| GET | `/admin/structure` | President / VP | The reporting tree: every e-board and chair role with its supervisor and who currently holds it |
| PUT | `/admin/structure/{role}` | President / VP | Set which role a role reports to. Organizational only — grants no permissions |

"Shop admin" = a user whose role is **Communication Director**, **Marketing Chair**, or **President**.

"Gallery admin" = a user whose role is **President**, **Vice President External**, **Vice
President Internal**, **Communication Director**, or **Marketing Chair**.
