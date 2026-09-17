# Environment variables

Two files, neither committed: `backend/.env` and `frontend/.env.local`. Local development
needs only a handful — see [Getting started](../README.md#getting-started). Everything else
is either a deployment concern or an optional integration.

Two names are easy to mix up:

- **`CORS_ORIGINS`** is the browser origin the **frontend** is served from.
- **`ALLOWED_HOSTS`** is the `Host` header of the **API itself**.

They are not the same value, and setting one to the other's value breaks every request.

Several integrations follow an **unset = dev mode** rule: with no credentials configured the
feature degrades to a safe local no-op (emails print to the console, checkout is simulated,
sheet sync is skipped) instead of failing. `ENVIRONMENT=production` flips those fallbacks to
fail closed, so the live server can never silently run in a simulated mode. Setup walkthroughs
for each integration live in [integrations.md](integrations.md).

## `backend/.env`

| Variable | Required | Description | Example |
|---|---|---|---|
| `SECRET_KEY` | Yes | Random hex secret for JWT signing | `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `ALGORITHM` | Yes | JWT signing algorithm | `HS256` |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Yes | Token lifetime in minutes. Defaults to `720` (12 h): there is no refresh-token flow, so a short lifetime makes members re-authenticate constantly, and every re-auth is an expensive password hash | `720` |
| `DATABASE_URL` | No | Postgres connection string. Defaults to the `docker-compose.yml` credentials/port, so local dev needs nothing here unless those change | `postgresql+psycopg://shpe:shpe_dev_password@localhost:5433/shpe` |
| `TEST_DATABASE_URL` | No | Separate Postgres database used only by the test suite. Defaults to the same host/port/credentials as `DATABASE_URL`, database `shpe_test` (create it once with `docker compose exec db createdb -U shpe shpe_test`) | `postgresql+psycopg://shpe:shpe_dev_password@localhost:5433/shpe_test` |
| `DATA_DIR` | No | Directory for uploaded files (`uploads/resumes`, `uploads/products`). The database lives in Postgres, but uploads are still on disk, so this must point at a mounted volume when deploying. Unset = the `backend/` directory | `/data` |
| `FRONTEND_URL` | **Yes in production** | Base URL of the frontend, used to build the verification and password-reset links in emails. Defaults to `http://localhost:5173`, so leaving it unset ships emails whose links point at localhost and strands every new member. Nothing catches this: the startup localhost check reads `CORS_ORIGINS` when that is set, so it passes while `FRONTEND_URL` is still the default | `https://www.shpeuh.com` |
| `ENVIRONMENT` | No | Set to `production` on the live server **only**. Makes the app fail closed instead of falling back to dev-mode no-ops: startup refuses to boot unless Square + SMTP + Google Drive are fully configured (with `SQUARE_ENVIRONMENT=production`), a charge attempt without Square config raises instead of simulating a free order, and `seed.py` refuses to run (use `bootstrap.py` to populate a production database — see [deployment.md](deployment.md)). Surrounding whitespace and letter case are ignored, so a pasted `"production "` still counts. Leave unset for local dev | `production` |
| `SMTP_HOST` | No | SMTP server for verification, reset and reminder emails. **Unset = dev mode:** emails print to the console instead. This is the only switch — `ENVIRONMENT` does not turn email on | `smtp.gmail.com` |
| `SMTP_PORT` | No | SMTP port. Must be a **STARTTLS** port (587): the client calls `starttls()`, so implicit-TLS port 465 will not work | `587` |
| `SMTP_USER` | No | SMTP login. An address for Gmail; the literal word `resend` for Resend | `chapter@example.org` |
| `SMTP_PASSWORD` | No | SMTP password — an app password for Gmail, the API key (`re_…`) for Resend | — |
| `EMAIL_FROM` | **Yes, for API-key relays** | From header; defaults to `SMTP_USER`. That default only works when the username happens to be an address (Gmail). Resend's SMTP username is the literal word `resend`, so leave this unset there and every send is refused — set it to an address on a domain you have verified with the provider | `SHPE UH <noreply@example.org>` |
| `SQUARE_ACCESS_TOKEN` | No | Square API access token for shop card payments. **Unset = dev mode:** checkout is simulated, no real charge | `EAAA...` |
| `SQUARE_LOCATION_ID` | No | Location id of the Square account (same application as the token) | `L4X...` |
| `SQUARE_ENVIRONMENT` | No | `sandbox` (default) or `production` — must match where the token was minted. Whitespace and case are ignored, as with `ENVIRONMENT`; anything unrecognized means sandbox | `sandbox` |
| `CREDENTIALS` | No | Path to the Google **service-account** JSON key used to read the event-tracker sheet. **Unset = dev mode:** the daily sync is skipped and the calendar shows only what's already in the database | `/path/to/service-account.json` |
| `GOOGLE_SERVICE_ACCOUNT_JSON` | No | The same service-account key as a single-line JSON string (`jq -c . key.json`), for hosts with no way to mount a file. Takes precedence over `CREDENTIALS` | `{"type":"service_account",...}` |
| `SHEET_ID` | No | Id of the event-tracker spreadsheet (the long string in its URL) | `1AbC...xyz` |
| `DUES_TRACKER_CREDENTIALS` | No | Dedicated membership-sheet service-account key: a JSON file path locally or the JSON contents in a deployment secret | `secrets/dues-service-account.json` |
| `DUES_SHEET_ID` | No | Id of the membership spreadsheet; dues imports are disabled unless this and `DUES_TRACKER_CREDENTIALS` are set | `1AbC...xyz` |

### Google Drive resume sync

Set together, or not at all.

| Variable | Required | Description | Example |
|---|---|---|---|
| `GDRIVE_RESUME_FOLDER_ID` | In production | Drive folder that resume PDFs are synced to — must be the **app-created** folder id printed by `get_drive_refresh_token.py` (a hand-made folder isn't reachable under the `drive.file` scope). **Unset = dev mode:** resumes stay local only | `1AbC...xyz` |
| `GDRIVE_OAUTH_CLIENT_ID` | In production | OAuth client id for Drive resume sync | `...apps.googleusercontent.com` |
| `GDRIVE_OAUTH_CLIENT_SECRET` | In production | OAuth client secret for Drive resume sync | — |
| `GDRIVE_OAUTH_REFRESH_TOKEN` | In production | Refresh token minted by `get_drive_refresh_token.py` | — |

All four are optional for local development and **required when `ENVIRONMENT=production`** — the backend refuses to start without them, because an unconfigured instance cannot delete a resume's Drive copy when a member asks it to. Set them before deploying.

Setup walkthrough: [Google Drive resume sync](integrations.md#google-drive-resume-sync).

### Deployment-only

Leave these unset for local development.


| Variable | Description | Example |
|---|---|---|
| `CORS_ORIGINS` | Comma-separated list of browser origins allowed to call the API. Falls back to `FRONTEND_URL`, then the Vite dev server. Under `ENVIRONMENT=production` the app **refuses to start** if this still points at localhost | `https://example.org,https://www.example.org` |
| `ALLOWED_HOSTS` | Comma-separated `Host` header allowlist for requests arriving **at the API** — your API's own domain, *not* the frontend's. With no custom API domain yet, that's the platform hostname (e.g. `<project>.up.railway.app`). A value that doesn't match rejects every request with `400 Invalid host header`, including `/health`. Leave unset to skip the check | `api.example.org` |
| `TRUST_PROXY_IP_HEADERS` | Set to `1` when the app runs behind a proxy or load balancer. **Without it every rate limit becomes one global bucket** shared by all visitors, because every request appears to come from the proxy's address. It also lets the app trust `X-Forwarded-Proto`, so redirects it generates use `https://` instead of an `http://` URL the browser blocks as mixed content | `1` |
| `TRUSTED_PROXY_HOPS` | How many proxies sit in front of the app. Only change it if you add a CDN in front of the platform edge | `1` |
| `RATE_LIMIT_LOGIN` / `_SIGNUP` / `_ORDER` / `_PASSWORD_RESET` | Per-IP limits. Defaults are deliberately generous because a campus event puts hundreds of members behind one shared IP | `60/minute` |
| `RATE_LIMIT_ATTEND` / `_CODE_PREVIEW` | Per-IP limits for QR check-in. Higher still: a whole room scans from one network within a couple of minutes, and check-in is already protected per-account (sign-in required, and a repeat scan awards no extra points) | `600/minute` |
| `RATE_LIMIT_UPLOAD` | Per-IP limit on the two upload routes (resume, product image) | `60/minute` |
| `RATE_LIMIT_FAILED_CHARGE` | Per-IP limit on **declined** card charges at checkout. Much tighter than the others because a successful purchase never counts against it — only a decline does, so a real buyer retrying a card never comes close | `10/10 minutes` |
| `RATE_LIMIT_COMMITTEE_JOIN` | Per-**account** limit on committee joins (the only per-account limit here — everything above is per-IP). Counts only joins that actually create a membership, so re-clicking Join on a committee you are already in never counts against it | `30/hour` |
| `MAX_REQUEST_BODY_BYTES` | Hard ceiling on request body size, rejected with a 413 as the bytes arrive. Must stay **above** the 2 MB per-file upload limits, or valid uploads fail with the wrong error | `4194304` (4 MB) |
| `SMTP_TIMEOUT` | Seconds to wait on the mail server before giving up | `10` |
| `SQL_ECHO` | `1` logs every SQL statement. Leave unset in production — the log would include member emails and PSIDs | — |

## `frontend/.env.local`

| Variable | Required | Description | Example |
|---|---|---|---|
| `VITE_API_URL` | Yes | Backend base URL. Must include the `http://` or `https://` scheme — without one, axios treats it as a relative path and API calls silently resolve against the frontend's own domain | `http://localhost:8000` |
| `VITE_BEHOLD_FEED_URL` | No | Public [Behold](https://behold.so) JSON feed for the home-page Instagram grid. If unset/unreachable, the grid shows a shimmer placeholder | `https://feeds.behold.so/<feed-id>` |
| `VITE_SQUARE_APP_ID` | No | Square application id for the checkout card element (sandbox ids start with `sandbox-`). **Unset = dev mode:** payment step stays simulated | `sandbox-sq0idb-...` |
| `VITE_SQUARE_LOCATION_ID` | No | Square location id — same one as the backend's `SQUARE_LOCATION_ID` | `L4X...` |

> **Never commit `.env` or `.env.local` to version control.**

