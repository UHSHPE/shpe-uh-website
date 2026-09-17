# Integrations

Four external services, all optional for local development. Each one follows the same
**unset = dev mode** rule: with no credentials configured, the feature degrades to a safe
local no-op rather than failing. The variables themselves are listed in
[environment.md](environment.md); this page is the one-time setup for each.

| Integration | Unset means | Needed in production |
|---|---|---|
| [Square payments](#square-shop-payments) | Checkout is simulated, no real charge | Yes |
| [Google Drive resume sync](#google-drive-resume-sync) | Resumes stay local only | Yes |
| [Event tracker sheet](#event-tracker-sheet-sync) | Daily sync skipped; calendar shows only what's in the database | Recommended |
| [Membership dues import](#membership-sheet-dues-import) | Dues import disabled | Recommended |

The two Google integrations use **different kinds of credentials and are not interchangeable** —
see [Why two different Google credentials](#why-two-different-google-credentials) at the bottom
before you try to fix one by copying the other's setup.

## Square shop payments


When configured, the checkout payment step renders Square's secure card element (card numbers go straight to Square — they never touch this backend), and `POST /shop/orders` charges the card for the server-computed total **before** creating the order. A declined card leaves no order behind. Every buyer gets an emailed, itemized receipt at checkout — including Square's hosted receipt link when the charge was real. Square's fee is ~2.9% + 30¢ per online charge.

A declined card always shows the buyer the same message — "Your card was declined, check your details and try again" — rather than Square's specific reason, and after `RATE_LIMIT_FAILED_CHARGE` declines from one connection checkout returns a 429 for a few minutes. Both are deliberate: checkout is open to guests, so a message naming the exact reason (bad number vs. bad CVC vs. bad ZIP) would let someone sort a stolen-card list against the chapter's real merchant account, and the chargeback fees and fraud ratio land on us. The specific Square decline code is written to the server log, so a member who asks why their card failed can still be answered. Successful purchases never count toward the 429, so a buyer retrying a card is unaffected.

Every charge is **itemized in Square**: the cart is mirrored into a Square order (product name + size, quantity, unit price), so the Square Dashboard shows exactly what was bought per transaction and item names flow into Square's sales reports and exports — no manual tracking needed.

**Wallets:** Apple Pay and Google Pay buttons appear automatically above the card form on devices/browsers that support them — both reuse the exact same charge flow. Google Pay also works in the sandbox. **Apple Pay is production-only** and needs a one-time domain registration: Square Developer Dashboard → your app → **Apple Pay** → add your web domain, then host the verification file Square provides at `https://<your-domain>/.well-known/apple-developer-merchantid-domain-association` (put it in `frontend/public/.well-known/` — Vite serves `public/` at the site root). Until that's done, the Apple Pay button simply doesn't render.

Start in the **Sandbox** (fake money, test cards), then switch to Production:

1. Go to [developer.squareup.com](https://developer.squareup.com/apps) and sign in with the chapter's Square account, then create an application (any name, e.g. "SHPE UH Website").
2. In the application's **Sandbox** tab, copy the **Application ID** (`sandbox-sq0idb-...`) and **Access Token** (`EAAA...`).
3. Get the sandbox **Location ID**: open the app's **Locations** page (or Default Test Account) and copy the id.
4. Set `SQUARE_ACCESS_TOKEN`, `SQUARE_LOCATION_ID` (+ `SQUARE_ENVIRONMENT=sandbox`) in `backend/.env`, and `VITE_SQUARE_APP_ID`, `VITE_SQUARE_LOCATION_ID` in `frontend/.env.local`. Restart both servers.
5. Test with Square's sandbox card: `4111 1111 1111 1111`, any future expiry, any CVV, any ZIP. Charges appear in the [Sandbox Seller Dashboard](https://squareupsandbox.com/dashboard).
6. **Go live:** swap in the app's **Production** Application ID + Access Token, the real store's Location ID, and set `SQUARE_ENVIRONMENT=production`. Also set `ENVIRONMENT=production` — the backend will then refuse to start if any of this is missing, so a config mistake can never silently turn checkout into free simulated orders.

## Google Drive resume sync


When configured, every resume upload is mirrored to the Drive folder, re-uploads replace the old copy in place, and deleting a resume removes it from Drive too. Every resume is renamed to `First_Last_PSID.pdf` (the uploaded filename is discarded) — both locally and in Drive. Sync is best-effort: if Drive is unreachable the upload still succeeds locally.

**Deletions are the exception to "best-effort".** If Drive is unreachable or unconfigured when a member deletes their resume, the local copy is removed and the request still succeeds, but the backend keeps its internal reference to the Drive file so a later upload replaces it instead of leaving a stray copy. That is also why the four variables are required in production: an instance without them cannot carry out a deletion request in Drive, and a resume left behind there holds the member's name, PSID, phone number and work history. To find any resume whose Drive copy may still need clearing by hand:

```bash
docker compose exec db psql -U shpe -d shpe -c 'SELECT id, resume_drive_file_id FROM "user" WHERE resume_filename IS NULL AND resume_drive_file_id IS NOT NULL;'
```

> **Why OAuth and not a service account?** Google blocks service accounts from uploading to personal My Drive folders (403 `storageQuotaExceeded` — they have no storage quota). A service account only works with a Google Workspace **Shared Drive**. For a folder on a personal Gmail account, the backend must upload *as you* via OAuth.

> **Scoped to one folder.** The OAuth token uses the `drive.file` scope: the backend can only see and modify files/folders **it created itself** — never the rest of your Drive. That's why the setup script creates the resume folder for you (it can't reach a folder you made by hand). The folder is owned by you, in your My Drive, and you can move or rename it afterwards without breaking sync.

1. In [Google Cloud Console](https://console.cloud.google.com), create (or pick) a project and enable the **Google Drive API**.
2. **APIs & Services → OAuth consent screen** — configure it and set Publishing status to **In production** (refresh tokens minted while in "Testing" expire after 7 days).
3. **APIs & Services → Credentials → Create Credentials → OAuth client ID → Desktop app** — copy the client id and secret.
4. From `backend/`, run `.venv/bin/python get_drive_refresh_token.py <client_id> <client_secret> [folder name]` (folder name defaults to "SHPE Resume Book") — a browser opens; sign in with your Google account and approve. The script mints the refresh token and creates (or reuses) the resume folder.
5. Paste the four printed `GDRIVE_*` lines into `backend/.env` and restart the backend.

**If resumes stop appearing in Drive**, the refresh token has almost certainly expired — the usual cause is step 2 being skipped, since tokens minted while the consent screen is in "Testing" die after 7 days. Sync is best-effort by design (uploads still succeed locally; the failure only goes to the server log), so it fails quietly. Confirm it from `backend/`:

```bash
.venv/bin/python -c "
from services import drive_services
import google.auth.transport.requests as gt
cfg = drive_services._drive_config()
print('configured:', bool(cfg))
if cfg: cfg[0].refresh(gt.Request()); print('token OK')
"
```

`invalid_grant: Token has been expired or revoked` means exactly that. Set the consent screen to **In production** first (or it recurs in a week), re-run step 4, and replace `GDRIVE_OAUTH_REFRESH_TOKEN` in `backend/.env`. Keep the existing `GDRIVE_RESUME_FOLDER_ID` — the script reuses the folder when the name matches, and the id is what sync depends on.


## Event tracker sheet sync


When configured, the backend reads the chapter's event-tracker spreadsheet once a day (6 AM Central) and reconciles it into the events calendar. Access is **read-only** — the backend never writes to the sheet. **Events are matched by the spreadsheet row they live on**, so editing an event's name, description, time, location, or owning committee in the sheet updates the same calendar entry in place on the next sync — renaming an event no longer creates a duplicate.

> **Clearing a row removes the event from the calendar.** It's hidden, not destroyed — re-filling the row brings the same event back, and anything already hidden can be restored in the database.
>
> **Moving an event to a different day** means moving it to the row for that day, which the sync reads as the old event being removed and a new one added. The calendar ends up correct, but anyone who set an email reminder for it loses that reminder.
>
> **Events that have already started are never changed.** Editing or clearing a past row does nothing — that's what keeps check-in rosters and awarded points intact.

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

> **Each semester has its own tracker sheet.** Dates in the sheet are `MM/DD` with no year, so the sync assumes the current year — which is correct as long as `SHEET_ID` points at the sheet for the semester you're in. **Switch `SHEET_ID` to the spring sheet before January 1.** If the fall sheet is still configured when the year rolls over, its rows all read as past events and are simply left alone, so nothing breaks — but the spring events won't appear until you switch.

**Sheet format:** row 1 holds the column headers (`DATE`, `EVENT NAME`, `DESCRIPTION`, `LOCATION`, `START TIME`, `END TIME`, `OWNER(S)`, `COLLAB(S)?`), row 2 is a template/sample row that's always skipped, and real events start on row 3. `DATE` is `MM/DD` and times accept either 12-hour (`6:00 PM`) or 24-hour (`18:00`) formats — blank, `All Day`, or `TBD` times place the event at midnight. A row with no event name is ignored, and a row with an unreadable date is skipped without affecting the others.

`OWNER(S)` and `COLLAB(S)?` are dropdowns, and they decide which committee an event is filed under. `OWNER(S)` is either `<Committee> Chair - <name>` or an E-Board position; `COLLAB(S)?` optionally names one more committee co-hosting the event, or an outside organization, which is ignored. Both are matched against the sheet's own spelling of each committee name, so **adding a new option to either dropdown needs a matching entry in `COMMITTEE_ROLES`** (`backend/services/event_tracker_services.py`) — otherwise the event is quietly filed under the E-Board instead.


## Membership-sheet dues import


The backend imports dues at startup and every ten minutes using the dedicated `DUES_TRACKER_CREDENTIALS` and `DUES_SHEET_ID` settings. Give the service-account email **Viewer** access to the membership spreadsheet. Relative credential paths are resolved from the backend's working directory. The integration requests only `spreadsheets.readonly`.

The **first worksheet** must contain one `Student PSID` header (currently column F) and one `Payment Verified?` header (currently column AA). Columns are located by header, and PSIDs are read as seven-digit strings so leading zeros survive. Only a `TRUE` checkbox grants dues; unchecked, blank, or unexpected values remain unverified claims.

The spreadsheet title must contain exactly one consecutive academic-year pair, such as `2026-2027 SHPE UH Membership`. That title fixes the membership period to May 30 of the first year. Missing or ambiguous years and missing or duplicate required headers abort the import. Invalid PSIDs are skipped and reported.

Verified claims count alongside website dues purchases in member status, statistics, and duplicate-purchase protection. An import creates no shop order. Payments are recognized even when the member registers after the import, and expire at the next May 30. Repeated imports and duplicate PSIDs create no duplicate claims; a checked duplicate wins. Once verified, a claim remains verified if its checkbox is later unchecked or its row disappears. Payment reversals require a deliberate correction to the imported record; sheet edits alone do not revoke dues.

Presidents and vice presidents can trigger `POST /admin/dues/sync`. Success returns `processed` (unique valid PSIDs), `verified` (checked claims in this snapshot), `skipped` (invalid rows), and `period_start`. A running sync returns 409, invalid sheet structure returns 422, and missing configuration or an upstream/database failure returns 503. Failed imports preserve existing records. Returning to the browser tab refreshes `/me` so the dues banner reflects the imported status.

Apply the database migration with `alembic upgrade head` before starting the updated backend. Tests mock Google access and run against the separate `shpe_test` database.


## Why two different Google credentials

Drive resume sync and the event-tracker sheet both talk to Google, but they authenticate in
different ways, and copying one's setup onto the other will not work:

- **Drive resume uploads** (`services/drive_services.py`) use **OAuth refresh-token**
  credentials. A service account has no storage quota of its own, so uploading into a personal
  My Drive folder fails with a 403 `storageQuotaExceeded`.
- **The event-tracker sheet** (`services/event_tracker_services.py`) uses a **service account**,
  which is correct — reading a shared sheet creates no files, so the quota limit never applies.

The membership dues import also uses a service account, for the same reason, with its own
dedicated key (`DUES_TRACKER_CREDENTIALS`) rather than sharing the event tracker's.
