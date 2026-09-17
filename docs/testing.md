# Testing

## Running the suite

```bash
docker compose up -d           # the database container must be running
cd backend
source .venv/bin/activate
python -m pytest tests/
```

Tests run against a dedicated `shpe_test` Postgres database — separate from the `shpe` dev
database, configured via `TEST_DATABASE_URL` — using fixtures from `tests/conftest.py`. The
`shpe_test` database has to exist first; see step 2 of
[Getting started](../README.md#2-start-the-database) if you haven't created it.

Run a single area or a single test while you work:

```bash
python -m pytest tests/shop_tests/           # one area
python -m pytest tests/shop_tests/test_orders.py::test_declined_card -v
```

> You do **not** need to run migrations against `shpe_test`. The suite builds its schema directly
> from the models and drops it again each run, so it's independent of migration history — which
> also means **a passing test run is not evidence that your migrations are correct**. Check those
> by applying them to a real database.

## Writing a test

Tests live in `tests/<area>_tests/`, matching the area of the app they cover. Four rules that are
specific to this suite:

- **Never hardcode a rate-limit count.** Import the constant and use `limit_count()` — the limits
  are configurable, so a hardcoded number makes the test lie the moment someone tunes one.
- **A second test user needs a unique `personal_email` and `psid`**, not just a different
  `cougarnet_email`. All three are unique per account.
- **Date event fixtures relative to `utcnow()`**, never to a hardcoded calendar date. Past events
  are frozen — a fixture pinned to a real date silently becomes a past-event test next semester.
- **Wiring up a new external service means adding an autouse `disable_*` fixture to
  `conftest.py`**, or the suite runs against a developer's live credentials.

For a bug fix, write the failing test first, then fix it. For new validation, write the
invalid-input tests, then make them pass.

## CI

Every push and pull request to `main` and `dev` runs two jobs in
[`.github/workflows/ci.yml`](../.github/workflows/ci.yml):

| Job | Runs |
|---|---|
| `backend` | `pytest tests/` against a Postgres 17 service container |
| `frontend` | `npm run lint`, then `npm run build` |

Both must pass before a pull request can merge. You can reproduce them locally:

```bash
cd backend && .venv/bin/python -m pytest tests/
cd frontend && npm run lint && npm run build
```

The lint job fails the build on three things that look harmless:

- calling `setState` synchronously in a `useEffect` body
- writing a ref during render
- exporting helpers or constants from a file that also exports a component

`no-unused-vars` only ignores names matching `^[A-Z_]`, and JSX usage doesn't count — so a file
importing lowercase `motion` from Framer Motion needs `/* eslint-disable no-unused-vars */`.

## Testing a real phone scan

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

