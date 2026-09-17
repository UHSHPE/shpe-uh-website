# Database, migrations, and seed data

PostgreSQL 17, accessed through SQLModel. Locally it runs in the Docker container defined by
`docker-compose.yml` on port **5433**; in production it is a managed Postgres service.

Three things worth knowing before you touch the schema:

- **The app does not create tables at startup.** Alembic owns the schema, so `alembic upgrade head`
  is a required setup step *and* a required deploy step. On a fresh or wiped database the app boots
  fine and then 500s on the first query until you run it.
- **A new model must be imported in `backend/database.py`.** That import is the only thing that
  registers the table in `SQLModel.metadata` — forget it and the table is silently missing from
  migrations *and* from every test.
- **`seed.py` is local-only; `bootstrap.py` is the production installer.** They are not
  interchangeable. See [Seed data vs. bootstrap](#seed-data-vs-bootstrap).

## Migrations

The schema is managed by [Alembic](https://alembic.sqlalchemy.org/) (`backend/alembic/`). The app does **not** create tables at startup, so `alembic upgrade head` is a required setup step and a required deploy step.

Run every command below from `backend/` with the virtualenv activated.

**Applying migrations** — brings a database up to the latest revision. Safe to re-run; it's a no-op once there's nothing left to apply:

```bash
alembic upgrade head
```

**After changing a model** (new column, new table, changed constraint) — generate a revision, then read it before applying:

```bash
alembic revision --autogenerate -m "add whatever you changed"
```

This writes a file to `backend/alembic/versions/`. **Open it and check it** — autogenerate is a starting point, not a guarantee, and it should be reviewed like any other code before it runs against a database. Then apply it with `alembic upgrade head` and commit the file alongside the model change.

> **Adding a value to an enum is the one case autogenerate misses.** Enums like `Role` and `OrderStatus` become real PostgreSQL types, and Alembic does not diff their values — you'll get a revision that does nothing. Add the statement by hand in the generated file:
>
> ```python
> op.execute("ALTER TYPE role ADD VALUE 'new_chair'")
> ```

**Useful commands:**

| Command | What it does |
|---|---|
| `alembic current` | Which revision the database is on |
| `alembic history` | All revisions, newest first |
| `alembic downgrade -1` | Roll back one revision |
### Starting over locally

Migrations make this unnecessary for ordinary schema changes, but a full reset is still the
quickest way out of a wedged local database:

```bash
docker compose down -v          # -v is essential — drops the database volume
docker compose up -d --wait
docker compose exec db createdb -U shpe shpe_test
cd backend && alembic upgrade head && python seed.py
```

Never run this against production — it destroys all data.

> If you wipe and reseed while the backend is running, **restart it**. It holds pooled
> connections from before the wipe and will otherwise serve stale or broken data.

## Seed data vs. bootstrap

Two scripts populate a database, and they exist for opposite situations.

| | `seed.py` | `bootstrap.py` |
|---|---|---|
| For | Local development | Production |
| Creates accounts | Yes — all with `password123` | **No.** It never imports `create_user` and contains no password, so it structurally cannot |
| Creates structure | Yes | Yes — committees, org chart, shop settings, dues product |
| Guards | Exits 1 if `ENVIRONMENT=production` **or** `DATABASE_URL` isn't a local Postgres | Every step is guarded; safe to re-run |

`seed.py` having two independent guards matters: `ENVIRONMENT` says nothing about *which*
database is being written, so exporting a production `DATABASE_URL` for a `psql` or Alembic
session — with `ENVIRONMENT` unset, as it normally is locally — would otherwise sail straight
past the first guard. Seed data must never enter the live database.

Both scripts read the real chapter structure from `backend/chapter_data.py` — committees, the org
chart (`DEFAULT_REPORTS`), the chair roster (`COMMITTEE_ROSTER`), and the dues product. **Edit
committees there, not in either script.**

Production setup using `bootstrap.py` is covered in
[deployment.md](deployment.md#filling-the-production-database).

## Seeded accounts

`python seed.py` creates two test members (one with dues already paid, one without), all 14 committees and their chairs/co-chairs (22 chair accounts), a comms director, the chapter president, the rest of the E-Board (both VPs plus the five officers, named to match the About page), the reporting structure (the chapter org chart, 20 links), the shop settings row, and five sample shop products (including the $20 "T-Shirt Dues").

All seeded accounts use the password `password123` — which is the whole reason for the guards described above.

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

The full chair roster lives in `backend/chapter_data.py` (`COMMITTEE_ROSTER`), alongside the E-Board committee rows, the org chart, and the dues product. That file holds the **real chapter structure** and is shared by `seed.py` and `bootstrap.py` — edit committees there, not in either script.


Re-running `python seed.py` is safe — every seeder skips what already exists, so it only fills in
what's missing. The flip side: editing seed data in the file has **no effect on rows that already
exist**. Clear those rows first.

A few rules the seeders have to follow, which will bite you if you add one:

- New seeded accounts need `email_verified = True`, or they seed fine and then can't log in.
- **No digits in seeded user names** — the `UserCreate` validator allows only letters, hyphens,
  apostrophes, and spaces. Put digits in the email instead.
- Every seeder needs an "already seeded" guard, because `seed.py` gets re-run to top up.
