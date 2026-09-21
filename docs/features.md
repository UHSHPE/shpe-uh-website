# Features

What the site actually does, feature by feature. This is the reference version — the
[README](../README.md) has the short summary. For the endpoints behind each of these, see
[api.md](api.md); for where the code lives, see [architecture.md](architecture.md).

## Everything at a glance


- **Authentication** — Secure sign-up and login with JWT tokens and Argon2 password hashing. Passwords must be 10–128 characters and are checked against the Have I Been Pwned breached-password database (no composition rules, no forced expiry — per NIST guidance); accounts lock temporarily after repeated failed logins. The five-step signup form validates each step before letting you continue, so every format rule the API enforces (name characters, 7-digit PSID, 10-digit US phone, at least one country of origin) is caught where the field is, not as a server error at the end. Uniqueness — one account per CougarNet email and one per PSID — can only be checked against the database, so those two are reported when you submit the form
- **Password Reset** — "Forgot password?" flow: a single-use reset link (valid 1 hour) is emailed to the member's CougarNet address; resetting signs out all existing sessions. Login and reset requests are rate-limited
- **Events Calendar** — Public calendar displaying upcoming chapter events
- **Event Sheet Sync** — The calendar populates itself from the chapter's event-tracker Google Sheet, re-read once a day, so officers add events in the sheet they already maintain and never touch the website
- **Email Reminders** — Members can request an email reminder for any upcoming event (sent 24h before, handled by a background loop)
- **Dashboard** — Personalized member dashboard with upcoming events and notifications
- **Profile** — Members can view their profile details and upload a PDF resume (view, replace, or remove it); resumes can be mirrored to a chapter Google Drive folder. Only the member — plus the president and both VPs, read-only, from the Members page — can open it
- **Committees** — Browse, join, and leave committees; chairs and co-chairs can view rosters and broadcast messages to members
- **Notifications** — In-app notification system for committee activity (joins, messages)
- **Merch Shop** — Public storefront with cart and checkout (card, **Apple Pay**, and **Google Pay** payments via **Square**; runs in a simulated dev mode until Square credentials are configured). Buyers pay online and pick up in person at a chapter event. The comms director, marketing chair, and president manage products, orders, and shop settings from the Shop Manager page and are notified of every new order; buyers get an emailed receipt at checkout and another email when their order is ready for pickup
- **President & VP Tools** — The chapter president has full admin access everywhere (shop manager plus every committee's chair tools). The president and both vice presidents share a **Members** page with four tabs: **All**, **E-Board**, and **Chairs** show chapter-wide stats (total accounts, dues paid vs. not, national members, classification and shirt-size breakdowns), member lookup by name/email/PSID, and role assignment; **Structure** holds the chapter org chart. Assigning or removing a chair role automatically updates that committee's chair membership. VPs can assign every role except President and the two VP seats, which only the president manages
- **Reporting Structure** — An editable org chart of who oversees whom: officers report to a vice president, chairs report to a vice president or an officer. It links *roles*, not people, so it survives elections and chair handovers without re-entry. Purely organizational — being someone's supervisor grants no extra permissions
- **Email Verification** — signing up creates an account that stays inactive until the member clicks a verification link emailed to their CougarNet address; only then can they log in. This also prevents someone from registering an email they don't control.
- **Chapter Dues at Signup** — right after verifying their email, new members are routed straight into paying their $20 "T-Shirt Dues" (t-shirt included) through the Square checkout, pre-sized with the shirt size from their signup form. Dues are **one per member per membership year** (server-enforced, sign-in required) and **final once paid** — a dues order can't be cancelled. They **reset every May 30**, when `reset_dues.py` runs, so members re-pay each year; signed-in members who haven't paid the current year see a site-wide red banner listing the benefits that ride on dues (Slack access, National convention sponsorship, $10,000+ in scholarships, MentorSHPE, the Resume Book, and the chapter shirt). The dues receipt carries the Slack invite link when the member said at signup that they aren't in Slack yet
- **Gallery** — Public photos are grouped by Spring/Fall semester and year. Any signed-in member can submit a PNG or JPEG up to 2 MB; it stays private until the president, either VP, communication director, or marketing chair approves it. Reviewers can correct the semester/year, reject or later approve a submission, and delete it. The first approval awards the submitter one point, which is never awarded twice or revoked by a later status change
- **Instagram Feed** — Home-page grid of the chapter's latest Instagram posts, pulled live from a public Behold feed
- **Points** — Member points tracking
- **QR Event Attendance** — Every event gets a sign-in and a sign-out QR code. Members scan with their phone's normal camera — there's no app to install and no in-app scanner — and points are awarded on the spot based on the event's pillar, matching the chapter point-system chart: 4 for signing in to a Community Outreach event, 3 for any other pillar, and 2 when no pillar is set on the event; sign-out is 2 throughout, general meetings award at least 3, and bringing a new member adds 2. An event tagged with several pillars awards the highest of them, not the sum. Scanning the same code twice never awards twice, a code doesn't work until roughly an hour before the event starts, and it stops working once the event is over. Chairs and E-Board present the QR (in a modal or fullscreen at the door) from their **Events** page, watch a live scan counter, and review a read-only attendance roster for each event they host. E-Board members can present the QR for **any** chapter event from the All Events tab, since officers often cover the door at an event another committee organized
- **Event Statistics** — Any chair or E-Board member can open a statistics panel on any event from the Events page: how many attended, how many scanned out, the average time people stayed, how many were attending their first chapter event ever, how many guests were brought, and breakdowns by classification (freshman through graduate), college, membership year, and the top five majors. These are counts and averages only — no attendee is named, which is why the panel is readable across committees while the named attendance roster stays limited to the event's own hosts


## President, VPs, and role assignment

The **President** role is the site-wide admin: shop manager access, every committee's chair tools (roster + messages on all committees), and the **Members** page (`/members`) backed by the `/admin/*` endpoints. From there they can look up any account, see who has and hasn't paid dues for the current membership year, and assign roles — vice presidents, e-board, committee chairs, or plain member. Clicking a member opens their full profile: contact details, academics, membership and background answers from signup, the committees they're in, and their resume. The president and both VPs are the only people who can read another member's resume — resumes are otherwise private to the member, and this view is read-only, so only the member can replace or delete their own file.

**Both Vice Presidents share the Members page**, so role fixes don't wait on one person. Two limits keep the top of the chapter out of reach: a VP can't assign the President or either VP role (none appear in their dropdown), and a VP can't change the role of anyone who currently holds one. That covers both directions of the same risk — without it a VP could demote the president or their fellow VP, or promote an ally into a VP seat, and the chapter could end up with nobody holding full admin.


### Reporting structure

The **Structure** tab draws the chapter org chart as a tree — the president at the top, each VP branching beneath, their officers below that, and the chairs as leaves, with each card showing who currently holds the role (or **Vacant**). Change a reporting line with the dropdown on any card. The president sits at the top and both VPs report to them (fixed). Each e-board officer reports to one VP, and each committee chair reports to a VP or an officer — the president and both VPs can rearrange either.

It links **roles rather than people**: "Academic Chair reports to Treasurer" keeps working when a new person is elected, so nothing needs re-entering after a handover. Co-chairs of one committee share a role and therefore share a supervisor.

The chapter's current chart is preloaded from `backend/chapter_data.py` (`DEFAULT_REPORTS`), by `seed.py` locally and `bootstrap.py` in production: the New Member Representative, Treasurer, and Regional Representative report to the VP External; the Communications Director, Secretary, and Director of Internal Affairs report to the VP Internal; and all 14 chairs sit beneath those officers. Both **skip the structure entirely once any link exists**, so re-running either never overwrites changes made on the Structure tab. To reload the chart from the file, clear it first:

```bash
docker compose exec db psql -U shpe -d shpe -c "DELETE FROM rolereport;" && python backend/seed.py
```

> The structure is organizational only. Being listed as someone's supervisor grants **no** extra permissions — role assignment stays with the president and VPs.

Nobody can change their own role. To hand off the presidency, the sitting president promotes their successor first — two presidents can coexist briefly — and the successor then demotes them.

Every role change asks for confirmation, naming both the old and new role, and warns when the change will also move someone on or off a committee's chair listing.

**Every role change also emails the sitting president and both VPs**, naming who changed, from which role to which, and who did it. Nobody with database or server access can be *prevented* from escalating privileges — but this makes sure it can't happen quietly, and the top tier are the only people who can undo it. The notice is best-effort: a mail outage never fails the role change.

> **Assigning a chair role updates the Committees page, not the About page.** The new chair appears on their committee card automatically, keeping the shared committee address (e.g. `academics@shpeuhchair.org`) rather than their personal one. The About page roster is maintained by hand — update `frontend/src/pages/about.jsx` after a chair handover.


## Committees and chairs

Committees support **co-chairs** — a committee can have one or two chairs, and every chair:

- Appears as a contact (name + email) on the committee card
- Can view the member roster and broadcast messages
- Is notified when a member joins

Chair permissions are tied to the user's `Role` (e.g. `academic_chair`) matching the committee's `chair_role`, plus an `is_chair` membership row. Both are set up by the seed.

## Merch shop

The shop sells chapter apparel (with sizes) and items like stickers. Anyone can browse and buy — no account needed; signed-in members get checkout prefilled and an order history under their profile.

- **Payment is by card, Apple Pay, or Google Pay through Square** (see [Square setup](integrations.md#square-shop-payments)). Without Square credentials configured the "Pay" step stays simulated — it instantly succeeds and no real money moves — which is how local dev runs.
- **Fulfillment is in-person pickup** at chapter events (no shipping). Every order gets a short code (e.g. `SHPE-A1B2`); the buyer brings it to pickup.
- Order lifecycle: `paid → ready → picked_up` (or `cancelled`). Marking an order **ready** emails the buyer; new orders notify all shop admins in-app and by email.
- **No inventory is tracked.** Each product is either **Active** (listed in the shop) or **Hidden** (kept in the admin table, off the storefront), and every order is limited to a configurable number of units per item (default 5).
- **Carts are re-priced against the live catalog** when the cart drawer opens and again at checkout, so a cart left sitting for days can't show one price while a different one is charged. If a price moved, the buyer sees an "A price changed since you added it" notice with the old and new figures, and the Pay button stays disabled until they acknowledge it. If a product was retired or one of its sizes withdrawn while in someone's cart, that line is marked **No longer available** with a Remove button and is left out of the total.
- **Products are never deleted.** Retiring one takes it off the storefront and files it under **Retired** in the Shop Manager, where it can be restored at any time (a restored product comes back Hidden, so an admin republishes it deliberately). Past orders keep showing exactly what was bought, and the product image is kept too. The **T-Shirt Dues** product can't be retired — newly verified members are sent straight to it.
- Shop administration belongs to the **Communication Director**, **Marketing Chair**, and **President** roles: they manage products (create/edit, images, show/hide, retire/restore), the order queue, and shop settings (storefront tagline + the per-item order cap) from the **Shop Manager** page at `/shop-manager`.

## Gallery submissions

The public gallery at `/gallery` combines the existing frontend assets with approved member
submissions. Each Spring/Fall section initially shows eight photos and can be expanded with
**Show all**. Signed-out visitors can browse approved photos; a signed-in member can upload a PNG
or JPEG no larger than 2 MB from the same page.

New submissions are private and start as **pending**. The semester and year are assigned from the
submission date (August through December is Fall; January through July is Spring), so members do
not have to categorize their photos. A reviewer can correct either value before approving or
rejecting the submission.

The **Gallery Manager** at `/gallery-manager` is available to the President, both Vice Presidents,
Communication Director, and Marketing Chair. It has Pending, Approved, Rejected, and All filters,
shows authenticated thumbnails plus submitter/reviewer names and timestamps, and paginates eight
photos at a time. Reviewers may move a photo between approved and rejected at any time or delete
it. Deletion removes the image file and soft-deletes its database record.

The first time a photo is approved, its submitter receives one point. A separate points record
makes that award idempotent: rejecting, re-approving, or deleting the photo does not revoke or
award the point again.

## QR event attendance

Chairs and E-Board members generate QR codes from the **Events** page (`/my-events`) and present them at the door — in a modal, or fullscreen for projecting. Members scan with their phone's regular camera, which opens `/attend/<code>` on the site; there's no in-app scanner and nothing to install.

Points are awarded on the spot based on the event's pillar, matching the chapter point-system
chart:

| Action | Points |
|---|---|
| Sign in to a Community Outreach event | 4 |
| Sign in to any other pillar | 3 |
| Sign in to an event with no pillar set | 2 |
| Sign out (any event) | 2 |
| General meeting | at least 3 |
| Bringing a new member | +2 |

An event tagged with several pillars awards the **highest** of them, not the sum.

Three rules keep the codes from being abused: scanning the same code twice never awards twice, a
code doesn't work until roughly an hour before the event starts, and it stops working once the
event is over.

Chairs and E-Board present the QR from their **Events** page — in a modal or fullscreen at the
door — watch a live scan counter, and review a read-only attendance roster for each event they
host. E-Board members can present the QR for **any** chapter event from the All Events tab, since
officers often cover the door at an event another committee organized.

To test a real phone scan against your local machine, see
[testing.md](testing.md#testing-a-real-phone-scan).

### Event statistics

Any chair or E-Board member can open a statistics panel on any event from the Events page:
turnout, sign-outs, average time people stayed, first-time attendees, guests brought, and
breakdowns by classification, college, membership year, and top five majors.

These are **counts and averages only — no attendee is named**, which is why the panel is readable
across committees while the named attendance roster stays limited to the event's own hosts.
