# Glossary

Terms you'll hit in the code, in tickets, and in chapter conversation. Chapter terms first,
because the code is full of them and none are guessable.

## Chapter terms

**SHPE** — Society of Hispanic Professional Engineers, the national organization. This repo is the
website for the University of Houston chapter.

**E-Board** — the executive board: the President, both Vice Presidents, and the officers
(Treasurer, Secretary, New Member Representative, Regional Representative, Director of Internal
Affairs, Communications Director). In the code, E-Board seats also exist as internal `Committee`
rows so they can hold messages and appear in the org chart — those rows are **not joinable** and
return 404 if a member tries.

**Chair / co-chair** — the member who runs a committee. A committee can have one or two. Chair
permissions come from two things together: the user's `Role` matching the committee's `chair_role`,
**and** an `is_chair` membership row.

**GBM** — General Body Meeting, the chapter-wide meeting. Relevant to the code mostly because a GBM
puts hundreds of members behind one campus IP at the same time, which is why rate limits are sized
the way they are.

**Pillar** — one of SHPE's 5 Core Pillars, which categorize events (Community Outreach, and four
others). An event's pillar decides how many points signing in awards. An event tagged with several
pillars awards the **highest**, not the sum.

**PSID** — the 7-digit student ID the University of Houston assigns. Unique to one account, used to
match members against the membership spreadsheet.

**CougarNet email** — a UH-issued `@cougarnet.uh.edu` address. Signing up requires one, and it's
where verification and password-reset mail goes. Also unique to one account.

**Classification** — academic standing: freshman through graduate. Collected at signup and reported
in event statistics.

**National member** — a member who has also paid dues to SHPE nationally, separate from chapter
dues. Tracked as a field on the member, reported in chapter stats.

**Dues / membership year** — the $20 "T-Shirt Dues" that make someone a full chapter member, paid
through the shop and including a shirt. Dues are **one per member per membership year** and
**reset every May 30**, so members re-pay annually. Members who haven't paid the current year see a
site-wide red banner.

**MentorSHPE** — the chapter's mentorship program. Named in the dues banner as a paid-member
benefit; no code of its own.

**Resume Book** — the collection of member resumes shared with sponsors. Backed by the Google Drive
resume sync.

**Event tracker sheet** — the Google Sheet where officers schedule events. The backend reads it
once a day and reconciles it into the calendar, so officers never touch the website to add an
event. **Each semester has its own sheet** — `SHEET_ID` must be switched to the spring sheet before
January 1.

**Membership sheet** — a different Google Sheet, tracking who has paid dues. A checked
"Payment Verified?" box there marks the member paid on the site, the same as a website
purchase. A row whose PSID has no account yet waits in the table until one exists.

## Codebase terms

**Alembic** — the tool that owns the database schema. The app does **not** create tables at
startup, so `alembic upgrade head` is a required setup and deploy step. See
[database.md](database.md).

**Migration** — one Alembic revision file describing a schema change. Generated with
`alembic revision --autogenerate`, then **read before applying** — autogenerate is a starting
point, not a guarantee, and it does not detect changed enum members at all.

**`seed.py` vs `bootstrap.py`** — two scripts that populate a database, for opposite situations.
`seed.py` is local-only and creates test accounts (all with `password123`); `bootstrap.py` is the
production installer and structurally cannot create an account. Never confuse them. See
[database.md](database.md#seed-data-vs-bootstrap).

**`chapter_data.py`** — the real chapter structure: committees, the org chart, the chair roster,
the dues product. Shared by both seeders. **Edit committees here**, not in either script.

**JWT** — the bearer token `/login` returns, carried on every authenticated request. There is no
refresh-token flow, so the token lifetime (`ACCESS_TOKEN_EXPIRE_MINUTES`, default 12 hours) is the
whole session.

**Soft delete** — marking a row hidden instead of removing it. Shop products are retired, not
deleted, so past orders still show what was bought and the image survives for a restore. Events
removed from the tracker sheet are hidden, not destroyed, so re-filling the row brings the same
event back.

**Dev-mode fallback** — the **unset = dev mode** rule. With an integration's credentials
unconfigured, the feature degrades to a safe local no-op: emails print to the console, checkout is
simulated, sheet sync is skipped. `ENVIRONMENT=production` flips all of these to fail closed, so
the live server can never silently run simulated.

**Rate-limit bucket** — the counter a rate limit is tracked against, keyed per IP (or per account
for committee joins). Behind a proxy, every request appears to come from the proxy's address, so
without `TRUST_PROXY_IP_HEADERS=1` all of them collapse into **one global bucket** shared by every
visitor.

**Square sandbox** — Square's fake-money test environment, with test card numbers. Where shop
development happens before switching to production credentials.

**Behold** — the third-party service providing the public JSON feed behind the home page's
Instagram grid. The only place the frontend calls something other than our own API.

**Reporting structure / org chart** — the editable tree of who oversees whom. It links **roles, not
people**, so it survives elections and chair handovers without re-entry. Purely organizational:
being someone's supervisor grants **no** extra permissions.

**Shop admin** — not a role of its own, but shorthand for a user whose role is **Communications
Director**, **Marketing Chair**, or **President**. Those three manage the shop.
