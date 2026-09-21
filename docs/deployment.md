# Deployment

> **This page is for whoever runs the live site.** If you're a committee member working on a
> feature, you don't need any of it — everything here happens on infrastructure you won't touch.

The frontend deploys to **Vercel** and the backend to **Railway**, with DNS at the registrar.
Configuration values referenced below are documented in [environment.md](environment.md).

The frontend deploys to **Vercel** (paid tier — the free Hobby plan does not permit commercial use, and the site sells merch) and the backend to **Railway**, with DNS at the registrar.

**Frontend.** Import the repo in Vercel with root directory `frontend`; the framework, build command (`npm run build`), and output directory (`dist`) are detected automatically. Set `VITE_API_URL` (full URL including `https://`, no trailing slash), `VITE_SQUARE_APP_ID`, `VITE_SQUARE_LOCATION_ID`, and `VITE_BEHOLD_FEED_URL` for **both** Production and Preview — these are baked in at build time, so changing one needs a redeploy **with the build cache disabled** rather than a restart; a cached rebuild reproduces the old bundle unchanged. `frontend/vercel.json` supplies the single-page-app fallback (needed so emailed `/verify-email` and `/reset-password` links resolve) plus security and caching headers.

> **Set the site domain before the first deploy.** `frontend/index.html` hardcodes the production domain in four absolute URLs — `canonical`, `og:url`, `og:image`, `twitter:image` — grouped in a single commented block at the top of `<head>`. They have to be absolute, because link-preview scrapers (Facebook, iMessage, LinkedIn, Discord) do not reliably resolve relative paths; a relative `og:image` is the usual reason a shared link renders a preview card with no picture. Change all four together if the domain moves, then redeploy. Preview the result with Facebook's [Sharing Debugger](https://developers.facebook.com/tools/debug/) — it also force-refreshes the scraper's cache, which otherwise holds a stale card for days.

**Backend.** Railway builds `backend/Dockerfile`. Add a **managed Postgres** service and set `DATABASE_URL` to its connection string — the `docker-compose.yml` container is for local development only and must not be used in production. Railway injects `PORT` automatically. Point the health check at `/health`.

Set the **pre-deploy command** to `alembic upgrade head` (no `cd` — the image has the backend at its working directory, not under `backend/`). The app does not create tables at startup, so without this a fresh deploy comes up healthy — `/health` deliberately doesn't touch the database — and then fails on the first real query. Migrations need only `DATABASE_URL`, so they don't contend for the volume below.

Uploads still live on disk, so attach a volume mounted at `/data` and set `DATA_DIR=/data`. Without it, every resume, product image, and gallery photo is written to the container filesystem and destroyed on the next deploy. The database stores gallery metadata and review state, but not the image bytes.

Run exactly **one worker**. Rate-limit counters live in slowapi's process memory, so a second worker makes every limit twice as loose, non-deterministically. (The database no longer constrains this — moving off SQLite removed that half of the reason. Multiple workers become viable once the limiter is backed by Redis, and the uploads volume is shared or moved to object storage.)

## Filling the production database

`seed.py` refuses to run against a production database — every account it creates shares `password123`. But it's also the only thing that creates committees, so a fresh production database is empty and unusable: nobody can reach `/admin/*` to assign a role, `sync_events` can't link events to committees (so QR check-in silently does nothing), and the post-verification dues redirect can't find its product.

`backend/bootstrap.py` fills that gap. It creates **structure only** — the 14 committees, the 10 E-Board committee rows, the 20 org-chart links, the shop settings row, and the "T-Shirt Dues" product. It creates **no accounts**: it never imports `create_user` and contains no password, so it cannot make one however it's run. Every step is guarded, so it's safe to re-run.

```bash
railway ssh
```

```bash
python bootstrap.py
```

Prefer `railway ssh` over `railway run` — it executes inside the container, where `/data` exists and the environment matches the app. Run it **before the first 6 AM event-sheet sync**; without committees, no `EventHost` rows are written and chairs see none of their events until the next morning's sync.

Once the president, VP External, and VP Internal have signed up on the live site **and clicked their verification links**, install them:

```bash
python bootstrap.py --president first.last@cougarnet.uh.edu --vpe first.last@cougarnet.uh.edu --vpi first.last@cougarnet.uh.edu
```

Each flag is handled independently — one failing doesn't block the others, so re-run just that flag later. Each seat is **one-shot**: once someone holds it, the script refuses with no override, and every later change has to go through `/members`, where only the president can move a top-tier seat. Promotions email the sitting top-tier holders, so a role change can't happen unnoticed.

From there the president assigns every other role from `/members`, and adds real merch through Shop Manager.

## Going-live checklist

1. Generate a fresh `SECRET_KEY` — do not reuse the development one.
2. Set `ENVIRONMENT=production`. The app then refuses to start unless Square, SMTP and the four `GDRIVE_*` variables are fully configured and `CORS_ORIGINS` no longer points at localhost. It also stops serving the API schema — confirm `/docs`, `/redoc`, and `/openapi.json` all return 404 once deployed.
3. Set `TRUST_PROXY_IP_HEADERS=1`. It does two jobs — rate-limit bucketing and trusting `X-Forwarded-Proto` — so verify both: exhaust a rate limit from one network and immediately retry from a different one (the second must succeed), and confirm no response carries an `http://` `Location` header.
4. Set `ALLOWED_HOSTS` to the **API's** own hostname, not the frontend's, then check `curl -s https://<api>/health` returns `{"status":"ok"}` and not `Invalid host header`. Read the body — a wrong value 400s every route while still returning correct CORS headers, so a status-only check looks healthy.
5. Load the deployed site and open the browser console on `/calendar` and `/shop`. These are the first pages to call the API, and a wrong `VITE_API_URL` (missing `https://`) or a blocked mixed-content redirect shows up **only** there — `curl` and the health checks both pass regardless.
6. Point DNS at Vercel (frontend) and Railway (backend), and wait for both certificates to issue.
7. Confirm `alembic upgrade head` ran (`alembic current` should report a revision), then run `python bootstrap.py` to create the chapter structure (see above), and install the three top-tier seats once those accounts exist and are verified.
8. Register your domain for Apple Pay in the Square dashboard (see the Square section above).
9. Send a real verification email to a `@cougarnet.uh.edu` address and confirm it lands in the inbox, not junk. University mail filters are strict, and every signup depends on that message arriving.
10. Upload a resume, product image, and gallery photo; approve the gallery submission; place a test order; then redeploy and confirm every file and record survived.
11. Confirm the managed Postgres backups are on, set up a backup of the uploads volume, and **perform one full restore** of each before relying on them.
12. Schedule the yearly dues reset (see below).

## Resetting dues each May 30

`has_paid_dues` is a plain flag on the member with no record of which year it was earned in, so
something has to retire last year's payments when the membership year rolls over. That is
`backend/reset_dues.py` — one statement, safe to run twice, and it must run **on or just after
May 30** or last year's members keep their benefits into the new year.

```
30 5 * * *  [ "$(date +\%m-\%d)" = "05-30" ] && cd /app/backend && python reset_dues.py
```

Unlike `seed.py` it has no local-database guard — it is meant to run against production. Check the
cron log afterwards: it prints how many members it cleared.
