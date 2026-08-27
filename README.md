# UEP EMMY — AI-Assisted Veterinary Platform (MVP)

A platform connecting **pet owners** (pet info, community advice) with **veterinary
professionals** (collaboration, expert feedback), with an AI layer that analyzes pet
photos to estimate species, breed, and age.

## Stack

| Layer    | Technology                                                             |
| -------- | ---------------------------------------------------------------------- |
| Frontend | React 18, TypeScript, Vite, Tailwind CSS v4                            |
| Backend  | Python 3.11+, FastAPI, SQLAlchemy 2.0                                   |
| Database | PostgreSQL (SQLite fallback for quick local demos)                      |
| Storage  | Local filesystem service that mimics S3 (swap for boto3/S3 later)       |
| AI       | ONNX Runtime with MLP classifiers (breed + age); mock fallback          |

## Repository layout

```
UEP_EMMY/
├── backend/
│   ├── app/
│   │   ├── main.py               # FastAPI entry point (CORS, /media mount, lifespan)
│   │   ├── core/config.py        # Settings via pydantic-settings (.env)
│   │   ├── db/                   # Engine/session, declarative base, demo seed
│   │   ├── models/               # SQLAlchemy models: User, Animal, Post, Comment, AIAnalysisLog
│   │   ├── schemas/              # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── storage.py        # StorageService ABC + LocalS3Storage
│   │   │   └── ai.py             # ImageAnalysisService ABC + ONNXImageAnalysisService
│   │   └── api/v1/               # Routers: /v1/analysis, /v1/posts
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    └── src/
        ├── types/index.ts        # TS mirrors of backend schemas
        ├── api/client.ts         # Typed fetch client (+ session token storage)
        ├── auth/                 # SessionContext (useSession) + RequireAuth guard
        ├── lib/format.ts         # Display helpers
        ├── components/
        │   ├── ui/               # Shared component library (see below)
        │   ├── layout/           # AppLayout (navbar/footer shell), PlaceholderPage
        │   └── ...               # ImageUpload, AnalysisCard, CommunityFeed
        └── pages/                # One folder per feature area (see route map)
```

## Frontend: routes, ownership, and shared components

`App.tsx` registers every route inside the shared `AppLayout` shell. Each page
lives in its owner's folder — replace the stub inside your page file; you should
rarely need to touch `App.tsx`.

`/` is the public promotional page **only for signed-out visitors**: with a valid
session it redirects to `/dashboard`, and the navbar logo points at `/dashboard`
too (signed-out visitors get bounced to `/login` and land there afterwards).
`/dashboard` requires a session. `/community`, `/community/:postId` and `/vets`
stay open to everyone so the social side can be browsed without an account.

| Routes                                              | Owner    | Area |
| --------------------------------------------------- | -------- | ---- |
| `/`, `/dashboard`, `*` (404), shell, `components/ui` | Member 1 | Design system, layout, landing |
| `/login`, `/signup`, `/profile`, `/settings`         | Member 2 | Auth & profiles (`pages/auth/`) |
| `/pets`, `/pets/:petId`                              | Member 3 | Pet management (`pages/pets/`) |
| `/analyze`, `/analysis/history`, `/analysis/:analysisId` | Member 4 | AI analysis flow (`pages/analysis/`) |
| `/community`, `/community/new`, `/community/:postId`, `/vets` | Member 5 | Community & vets (`pages/community/`) |

Shared UI lives in `src/components/ui` (import from `../components/ui`):
`Button`, `Card`, `Badge` (has a `vet` variant for verified-vet markers),
`Avatar`, `Input`/`Textarea`/`Select`, `Modal`, `Spinner`, `EmptyState`, and a
`useToast()` hook (provider already mounted in `App.tsx`). Use these instead of
hand-rolling equivalents so the app stays visually consistent. Brand colors are
the `primary-*` Tailwind classes, defined once in `src/index.css`.

Backend work each member owns alongside their pages: Member 2 — `/v1/auth` +
`/v1/users` (**done**); Member 3 — `/v1/animals` CRUD (**done**);
Member 4 — `GET /v1/analysis` history endpoint (**done**); Member 5 — community
feed, posts/comments, and veterinarian directory (**done**); shared — `/v1/reports`
moderation (**done**). Keep
`frontend/src/types/index.ts` in sync with backend schemas — it is the shared
contract.

The analysis result page's **Share to community** action navigates to
`/community/new` with a `PostPrefill`. The composer uses its suggested title,
content, analyzed image, and analysis ID; the API verifies that the attached
analysis belongs to the signed-in author.

### Auth & session (Member 2 — done)

- `SessionProvider` / `useSession()` (`src/auth/SessionContext.tsx`) exposes
  `user`, `login`, `signup`, `logout`; the token persists in localStorage and the
  session is restored via `GET /v1/auth/me` on page load.
- Wrap signed-in-only pages with `RequireAuth` (`src/auth/RequireAuth.tsx`) in
  `App.tsx` — it redirects to `/login` and returns the user afterwards.
- On the backend, protect routes with
  `current_user: User = Depends(get_current_user)` from `app/api/deps.py`
  (or `get_optional_user` where anonymous access is allowed). The frontend
  client sends the `Authorization: Bearer` header automatically.
- Demo accounts (all seeded with password `demo1234`):

  | Account | Role | Notes |
  | ------- | ---- | ----- |
  | `demo.owner@uepemmy.com` | Pet owner | Owns Buddy the Labrador |
  | `demo.vet@uepemmy.com` | Veterinarian | Already verified — shows the badge |
  | `demo.newvet@uepemmy.com` | Veterinarian | Unverified, for demoing the request flow |
  | `admin@uepemmy.com` | Admin | Reviews licence documents |

  These four are marked email-confirmed on every boot, so they can sign in
  without a readable inbox. Accounts you create yourself must confirm their
  address first — see the outbox section below.

### Email: verification, password resets, and notifications

Every email the platform sends is transactional — the consequence of something
the reader or somebody they deal with did. There are no marketing emails and no
mailing list.

**Nothing in a request talks to a mail server.** An endpoint that wants an email
writes a row into `email_messages` and returns; a background sweep
(`_email_sweep` in `main.py`, every `EMAIL_SWEEP_SECONDS`) delivers it and
records what happened. A slow or unreachable relay makes a message late, never
an API call slow.

#### Local development: the outbox

With `SMTP_HOST` empty — for example when `backend/.env` is absent or still has
the placeholder values — **nothing is sent**. Each message is written to
`backend/storage/outbox/<timestamp>-<id>.eml` as a complete, valid email and
recorded as `unavailable`, never as `sent`. The interface says so too: Settings
reads `GET /v1/auth/email-delivery` and states plainly that this server cannot
send email, and each alert in the notification bell says "email unavailable on
this server" rather than claiming delivery.

Read what would have gone out:

```bash
cd backend
python -m app.scripts.outbox            # newest first, one line each
python -m app.scripts.outbox --show 1   # one message: both bodies, and its links
python -m app.scripts.outbox --links    # just the links from the newest message
```

`--show` is the one worth knowing: verification and reset links are long, and a
mail file read with `cat` wraps them across two lines in quoted-printable —
which is exactly the part you opened the file for.

**This is how you sign in as a new account in development.** Confirming the
address is required, so after signing up locally: `python -m app.scripts.outbox
--links`, open the link, then sign in. The seeded demo accounts skip this — they
are marked confirmed on boot.

To see real inboxes without real credentials, run a local capture server —
[Mailpit](https://github.com/axllent/mailpit) or MailHog — and point SMTP at it.
Everything then follows the real SMTP path, including retries:

```bash
docker run -p 1025:1025 -p 8025:8025 axllent/mailpit
```

```dotenv
# backend/.env
SMTP_HOST=localhost
SMTP_PORT=1025
SMTP_USE_TLS=false
```

The web inbox is at <http://localhost:8025>.

#### Team development: real inboxes through Docker

Docker Compose automatically loads `backend/.env` when that file is present.
It is optional, ignored by Git, and excluded from the backend image, so a secret
cannot be recovered from the repository or built image. For a trusted team that
needs real verification and password-reset messages locally, prepare one
`backend/.env` using a dedicated development sender and share that file through
a password manager or another encrypted channel. Each teammate places it at
exactly `backend/.env`; they do not edit the Compose file.

For the Docker setup, the file must use:

```dotenv
FRONTEND_BASE_URL=http://localhost:8080
```

The rest of the SMTP values are the provider settings documented below. After
placing the file, the ordinary command is enough:

```bash
docker compose up --build
```

New accounts can then register with any real recipient address. Mail is sent
from the shared development sender to that address. Verification links contain
`localhost:8080`, so they should be opened on the same computer that is running
Docker. Never commit the shared file or copy a personal mailbox password into
it; use a revocable App Password for the dedicated sender.

#### Production SMTP

Set these in `backend/.env` (see `.env.example`; every value there is a
placeholder — **no real credentials are in this repository**):

| Variable | Notes |
| --- | --- |
| `SMTP_HOST` | Non-empty is what switches real sending on. |
| `SMTP_PORT` | 587 with STARTTLS, or 465 with implicit TLS. |
| `SMTP_USERNAME` / `SMTP_PASSWORD` | Omitted for a relay that authenticates by IP. |
| `SMTP_USE_TLS` | STARTTLS after EHLO. The 587 case. |
| `SMTP_USE_SSL` | TLS from the first byte. The 465 case; wins if both are set. |
| `SMTP_FROM` | `UEP EMMY <no-reply@yourdomain>`. Must be a domain you may send for. |
| `FRONTEND_BASE_URL` | **Every link in every email is built against this.** |

`FRONTEND_BASE_URL` is the one that is easy to forget and impossible to work
around: the queue runs in a background task with no request to read a `Host`
header off, so there is nothing to derive it from. Left at its default, every
verification and reset link in a real inbox points at `http://localhost:5173`
and goes nowhere.

**Check the settings before testing the app through them:**

```bash
cd backend
python -m app.scripts.check_smtp                     # connect, secure, log in
python -m app.scripts.check_smtp --send you@you.com  # and send one real message
```

It performs the same three steps the queue does and names the setting behind
whichever one failed. Without it, a wrong app password, a blocked port and a
rejected `SMTP_FROM` are indistinguishable from inside the application: messages
just sit in `email_messages` with `state = failed`. The password is read from
`.env` — never passed as an argument, which would put it in shell history — and
is never printed back, only its length.

### Gmail

Gmail needs an **App Password**, not the account password, and App Passwords
only exist once 2-Step Verification is on (Google Account → Security → 2-Step
Verification → App passwords):

```dotenv
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USE_SSL=false
SMTP_USERNAME=you@gmail.com
SMTP_PASSWORD=your16charapppassword
SMTP_FROM=UEP EMMY <you@gmail.com>
```

`SMTP_FROM` has to match the authenticated account — Gmail refuses to send as
anybody else. Paste the App Password without the spaces Google displays it in.
Gmail also caps sending at roughly 500 messages a day, which is fine for a
demo and not a production relay.

#### Authentication email flows

| Flow | Endpoint | Link lifetime |
| --- | --- | --- |
| Confirm an address after signup | queued by `POST /v1/auth/signup` | `VERIFY_EMAIL_TTL_HOURS` (48) |
| Send that link again | `POST /v1/auth/verify-email/resend` | 48 h |
| Confirm a **changed** address | queued by `PATCH /v1/users/me` with a new `email` | 48 h |
| Spend any confirmation link | `POST /v1/auth/verify-email` | — |
| Ask for a password reset | `POST /v1/auth/forgot-password` | `PASSWORD_RESET_TTL_MINUTES` (60) |
| Spend a reset link | `POST /v1/auth/reset-password` | — |

The frontend screens are `/verify-email`, `/resend-verification`,
`/forgot-password` and `/reset-password`, all public — a link from an email is
usually opened in a browser that is not the one holding the session.

**An account cannot sign in until its address is confirmed.** This is the rule
everything else here serves:

- `POST /v1/auth/signup` creates the account and returns **no session** — just
  `{email, verification_required, detail}`. Handing back a token while `/login`
  refuses the same account would be two rules disagreeing, and the one that let
  people in would be the one that mattered.
- `POST /v1/auth/login` answers **403** with
  `{"code": "email_unverified", "message": …}` for an unconfirmed account. The
  code is there because `/login` also answers 403 for a ban, and the two need
  opposite endings — a ban is final, an unconfirmed address is one click from
  being fixed. The sign-in form branches on the code, not the wording.
- The check runs **after** the password, deliberately. Refusing on the address
  alone would tell anybody who typed an address whether it has an unconfirmed
  account here, which is the enumeration hole the rest of this section avoids.
- It runs **after the ban check** too: a banned account is not owed a
  verification link, and "confirm your address" would be a false lead.
- Completing a password reset also confirms the address. Clicking a link in the
  inbox proves the inbox, whichever link it was.

**Nobody gets locked out by this**, which takes two pieces of care:

- `ensure_seeded_accounts_verified` (in `db/seed.py`, run on every boot) marks
  the four fixture accounts confirmed. Their inboxes are at `@uepemmy.com` and
  nobody can read them, so without it a fresh checkout would have no way in and
  the admin queue would be unreachable.
- `_grandfather_existing_accounts` (in `main.py`) runs **once**, on the boot
  that adds `email_verified_at`, and confirms every account that predates the
  column. An existing deployment upgrading into this rule would otherwise lock
  out every one of its users, including the administrator who would have to fix
  it. It is the only backfill in this codebase; grandfathered rows are the ones
  where `email_verified_at` equals `created_at` exactly.

Neither shortcut touches a real account, and neither guesses. A heuristic like
"confirm everybody if nobody is confirmed yet" would, on a fresh deployment,
silently admit the first person who signed up and never clicked — the rule
undone by its own migration.

Three more properties worth knowing, because they look like bugs if you do not:

- **A changed address does not change until the link is clicked.** `PATCH
  /v1/users/me` with a new `email` sets `pending_email` and sends a link to the
  new address; the account keeps signing in with the old one until it is used.
  A typo saved straight onto the account would send every future password reset
  to an inbox the owner cannot read.
- **Links are one-use and superseding.** Asking for a second reset kills the
  first, and spending one kills every other outstanding reset for that account.
  An expired or spent link answers `410`, a link that was never valid answers
  `400`, and the pages say different things for each.
- **Neither `/forgot-password` nor `/verify-email/resend` reveals whether an
  address is registered.** Both always answer `202` with the same body. The
  interface keeps that promise too — "if that address has an account with us".
  `/verify-email/resend` is the way out of a blocked sign-in, so it works
  without a session by design.

Rate limits (in-process, `app/core/rate_limit.py`): three emails per address per
hour, twenty requests per caller per hour, ten reset attempts per caller per
fifteen minutes.

#### Which events send email

Reminder due · appointment requested, confirmed, declined, cancelled · a new
time suggested, accepted, or turned down · a new message on an appointment · a
note added by the practice · veterinary verification approved, rejected, or
revoked · a moderation decision that changes what an account can do.

Every one of these is an in-app notification first; the email carries the same
words plus the pet, the date, the practice and a link back. Messages containing
clinical wording carry one sentence saying they are a record, not a diagnosis.
Health-record content beyond the note itself is never included.

#### Preferences, and the delivery states

`notify_email` silences **notification** email only. Verification and
password-reset messages are `SECURITY` category and are never suppressed —
turning notifications off is not consent to be locked out of your own account.

Each notification carries an `email_state`, and they are shown differently
because they mean different things:

| State | What it means | What the bell says |
| --- | --- | --- |
| `not_requested` | The reader has email switched off. | nothing |
| `queued` | Written down, waiting for the sweep. | "email on its way" |
| `sent` | Accepted by the mail server. | nothing |
| `failed` | Refused, and out of retry attempts. | "email could not be delivered" |
| `unavailable` | No SMTP here; written to the outbox. | "email unavailable on this server" |

The old interface printed "not emailed" for everything that was not `sent`,
which covered a message queued two seconds ago, a message a server refused, and
a deployment with no mail server — two of which are not problems at all.

#### Retries and deduplication

A refused message is retried after 1 minute, 5 minutes, 30 minutes and 2 hours,
then given up on as `failed` at `EMAIL_MAX_ATTEMPTS` (5). A message that went to
the outbox is **never** retried: there is nothing to retry against, and the file
is already written.

Deduplication is a unique `dedupe_key` on `email_messages`, carrying the same
keys the notification layer already uses (`email:reminder:<id>:<date>`). That is
what makes a scheduler running every fifteen minutes safe to run every fifteen
minutes.

Reminder email respects the reader's timezone, their chosen hour, and every lead
time they have set — `notify_leads` allows several ("a week before" *and* "the
day before"), each announced separately under its own key, and a reminder with
its own `notify_lead_days` overrides the list.

#### Troubleshooting

Start with `python -m app.scripts.check_smtp`, which answers most of these
directly.

| Symptom | Where to look |
| --- | --- |
| Nothing arrives, and Settings says the server cannot send email | `SMTP_HOST` is empty. Expected in dev — read `python -m app.scripts.outbox`. |
| "Username and Password not accepted" | Gmail: you used the account password, not an App Password. |
| Connects and negotiates TLS, then every message fails | `SMTP_USERNAME` set with an empty `SMTP_PASSWORD`. `check_smtp` refuses this configuration rather than reporting success. |
| Alerts stuck at "email on its way" | The sweep is not running. `NOTIFICATION_SWEEP_ENABLED=false` stops both sweeps; check the boot log for `Email: SMTP at ...`. |
| "email could not be delivered" | `email_messages.detail` holds the last SMTP error (type and message, bounded). Common causes: wrong port for the TLS mode, an unauthenticated relay, a `SMTP_FROM` domain the relay will not send for. |
| Links in emails point at localhost | `FRONTEND_BASE_URL` is still the default. |
| A verification link says "already used" straight away | Some mail scanners pre-fetch links. Ask for a new one; tokens are one-use by design. |
| Reset emails stop arriving after a few tries | The per-address limit is three an hour. |

Logs never contain a body, a token, or a password, and recipients are masked to
`al***@example.com` — a reset link in an application log is a reset link in
every system that log is shipped to.

### Veterinarian verification

Signing up as a veterinarian is only a claim; the teal **Verified vet** badge
appears only after an administrator approves a licence document. Unverified
veterinarian accounts get a plain "Veterinarian" badge instead — the whole point
of the flow is that the badge means something.

- A veterinarian submits proof from their own profile page
  (`pages/auth/VerificationCard.tsx`), which needs a licence number on the
  profile first. Statuses: `unverified → pending → verified | rejected`, and a
  rejected vet can resubmit.
- Administrators review at `/admin/verifications`
  (`pages/admin/VerificationQueuePage.tsx`), approving or rejecting with a note
  the veterinarian sees. The admin link appears in the account menu for admins.
- **Approving is guarded, and reversible.** Granting the badge vouches for
  someone to the whole community, so every decision goes through a confirmation
  dialog naming the veterinarian and spelling out the consequence — a stray
  click cannot verify anyone. Rejections and revocations additionally require a
  written reason before the confirm button enables. If an approval was still
  given by mistake, open the **Approved** filter and use **Revoke
  verification**: the badge disappears everywhere immediately. Decisions record
  which administrator made them (`reviewed_by`), shown on every decided card.
- Only a veterinarian's **most recent** submission can be decided; an older,
  superseded one returns 409 so the account status always matches the newest record.
- Every submission is kept in `vet_verifications` as history; the decision is
  mirrored onto `users.verification_status` so badges render without a join.
- **Use `<RoleBadge user={...} />`** (`components/ui`) wherever an author is
  labelled — it is the single place that decides verified vs. unverified vs. owner.
  `UserRead` exposes `verification_status` and the convenience flag `is_verified_vet`.
- The admin role can never be self-registered: `SignupRequest` accepts only
  `owner` and `veterinarian`, and `ensure_admin_account()` creates the admin at
  startup if the database has none.

### Community reporting & moderation

Members report each other's content; administrators review it and can suspend or
ban the account. The flow deliberately mirrors vet verification — same guarded
dialogs, same attributable and reversible decisions.

- **Reporting.** `<ReportButton target={...} authorId={...} />`
  (`components/ReportButton.tsx`) is the single entry point, already placed on
  posts and comments (`PostDetailPage`) and on profiles in the vet directory
  (`VetsPage`). It renders nothing for signed-out visitors, on your own content,
  or for admins. It opens `ReportDialog`, which collects a **reason checklist**
  (offensive language, harassment, spam, pretending to be a vet, dangerous
  medical advice, animal welfare, graphic content, something else) plus an
  optional written explanation — required when "Something else" is ticked.
- **The reported account is derived server-side** from the post/comment, so a
  reporter cannot aim a report at someone who did not write it. Self-reports and
  reports against admins are refused, and one reporter gets one *open* report per
  target (a second returns 409) so the queue cannot be flooded.
- **A snapshot of the reported text is stored with the report**, so the review
  still makes sense if the author edits or deletes it afterwards — the same
  reason verification keeps the licence number as submitted.
- **Administrators review at `/admin/reports`**
  (`pages/admin/ReportQueuePage.tsx`), which shows the checklist, the reporter's
  explanation, the snapshot, a link to the discussion, and the account's current
  moderation state. Four outcomes: **dismiss** (no penalty), **suspend** (choose
  3/7/30/90 days), **ban** (indefinite), and **reinstate**.
- **Penalties are guarded and reversible.** Suspending, banning, and reinstating
  each go through a confirmation dialog and require a written reason before the
  confirm button enables; `reviewed_by` records which administrator decided.
- **What a penalty does:** suspended and banned members can still *read* the
  platform, but posting, commenting, and reporting are refused with the reason.
  A ban additionally blocks signing in. A suspension lapses on its own
  (`User.is_suspended` checks `suspended_until`) — no job needed. Restricted
  members see a banner in the layout explaining the restriction and the note.
- `users` carries the current state (`account_status`, `suspended_until`,
  `moderation_note`) while `user_reports` keeps the full history, exactly like
  `verification_status` / `vet_verifications`.
- The suspension deadline and moderator note are returned **only to the account
  they concern** (`CurrentUserRead` via `/v1/auth/me`), never on a public author
  profile.

## Running with Docker (recommended)

The quickest way to start both the backend and frontend together is:

```bash
docker compose up --build
```

If `backend/.env` exists, Compose injects it into the backend container at
runtime. This is how the privately shared team SMTP configuration reaches
Docker; the file is not copied into the image. Without the file, the application
still starts and uses its local email outbox. See **Email: verification,
password resets, and notifications** above.

This builds and starts two containers:

| Container | URL | Description |
|-----------|-----|-------------|
| **frontend** | <http://localhost:8080> | React app served by nginx; proxies API calls to the backend |
| **backend** | <http://localhost:8000> | FastAPI + ONNX inference; API docs at <http://localhost:8000/docs> |

Data (SQLite database + uploaded files) is stored in the `backend_db` Docker
volume so it persists across container restarts. To reset everything:

```bash
docker compose down -v            # -v removes the data volume
docker compose up --build
```

## Running locally (without Docker)

### Backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env              # then point DATABASE_URL at your PostgreSQL

uvicorn app.main:app --reload --port 8000
```

Tables are created and demo data (a pet owner, two veterinarians, sample posts,
and one pending report waiting in the moderation queue) is seeded automatically
on first startup — but only into an *empty* database, so an existing volume will
not gain the demo report. No PostgreSQL handy? Set
`DATABASE_URL=sqlite:///./uep_emmy.db` in `.env` for a throwaway local database.

> **Schema changed (July 2026):** `ai_analysis_logs` gained `intake`, `triage`,
> and `triage_level` (symptom triage); `users` gained `password_hash`, `bio`, and
> `avatar_url` (auth); `animals` gained `birth_date`, `photo_url`, and thumbnail
> focus fields (pets); `ai_analysis_logs` gained `user_id` (history); `posts`
> gained `analysis_id` plus `image_url` (community sharing); `users` gained
> `verification_status` alongside the new `vet_verifications` table (vet
> verification); and `users` gained `account_status`, `suspended_until` and
> `moderation_note` alongside the new `user_reports` table (community
> reporting); `comments` gained `source_url` and `source_title` alongside the
> new `comment_votes` table (community citations and helpful marks); and
> `appointments` gained `preferred_time`, `scheduled_time`, `proposed_date`,
> `proposed_time`, `proposed_by_id` and `proposed_note` alongside the new
> `appointment_messages` table (exact appointment times, rescheduling, and
> clinic messaging); `reminders` gained `notify_lead_days` alongside the new
> `reminder_occurrences` table (marking instances done and snoozing them); and
> `users` gained `notify_time` and `notify_timezone` (choosing when alerts go
> out); and `users` gained `clinic_hours_grid`, `clinic_timezone`,
> `clinic_latitude`, `clinic_longitude`, `specialties`, `consultation_fee_min`,
> `consultation_fee_max` and `fee_currency`, with `appointments.slot_id`
> alongside the new `availability_slots` table (finding a vet by distance,
> specialty, opening status, price and published availability). There are no
> Alembic migrations yet. The newer thumbnail,
> analysis ownership, post attachment, verification, moderation, comment-source
> appointment-time, reminder-scheduling and vet-directory columns are added
> automatically at startup without deleting existing data. The directory
> columns are all nullable with no backfill, deliberately: a practice that has
> published nothing must read as "not listed", never as far away, closed, or
> free. The new appointment columns are all nullable with no
> backfill: an appointment confirmed before exact times existed genuinely has
> none, and the interface says so on the row rather than inventing one.
> Databases that predate the auth or base pet-photo fields may still need to be
> recreated.

API docs: <http://localhost:8000/docs>

| Endpoint                       | Description                                        |
| ------------------------------ | -------------------------------------------------- |
| `POST /v1/auth/signup`         | Create an account (owner or veterinarian) → token  |
| `POST /v1/auth/login`          | Email + password → token                           |
| `GET /v1/auth/me`              | User for the presented Bearer token                |
| `PATCH /v1/users/me`           | Update profile (name, bio, email, clinic, license) |
| `POST /v1/users/me/password`   | Change password                                    |
| `POST /v1/users/me/avatar`     | Multipart profile-photo upload                     |
| `GET/POST /v1/animals`         | List / create the signed-in user's pets            |
| `GET/PATCH/DELETE /v1/animals/{id}` | Pet detail / update / remove (owner only)     |
| `POST /v1/animals/{id}/photo`  | Multipart pet-photo upload                         |
| `POST /v1/analysis/upload`     | Multipart image upload → stored + ONNX AI analysis; optional `animal_id` links it to your pet (auth required for linking) |
| `GET /v1/analysis`             | Your past analyses, newest first; `?animal_id=` filters by pet |
| `GET /v1/analysis/{id}`        | Full owner-only analysis, symptoms, and triage details |
| —                              | Every analysis read carries `conflicts[]`: where the result contradicts the linked pet's profile (species, breed, age). Computed per request, never stored, so correcting the analysis or fixing the profile clears it |
| `POST /v1/triage`              | Assess reported symptoms; stores nothing (handy for testing the rules) |
| `GET /v1/posts`                | Paginated posts; supports `q` and `author_role`    |
| `POST /v1/posts`               | Create a signed-in user's post; optional analysis  |
| `GET /v1/posts/{id}`           | Post with comments                                 |
| `POST /v1/posts/{id}/comments` | Add a signed-in user's comment                     |
| `GET /v1/vets`                 | Public directory. Filters: `q`, `verified_only`, `accepting_only`, `lat`+`lng`+`radius_km`, `specialty` (repeatable), `open_now`, `max_fee`, `has_availability`; `sort=relevance\|distance\|price\|soonest`. **Every filter excludes practices that have not published that detail** — unknown is never treated as "no" |
| `GET /v1/vets/specialties`     | The specialty catalogue, so clients never hold their own copy |
| `GET /v1/vets/{id}/slots`      | Openings the practice has published here (not a view of their diary) |
| `POST /v1/vets/me/slots`       | A practice publishes an opening, optionally repeating it weekly |
| `DELETE /v1/vets/me/slots/{id}` | Withdraw one; refused once somebody is confirmed into it |
| `POST /v1/verification`        | Vet submits a licence document → status `pending`  |
| `GET /v1/verification/me`      | The caller's own submissions, newest first         |
| `GET /v1/verification`         | Admin review queue; `?status=pending` filters      |
| `PATCH /v1/verification/{id}`  | Admin approves (`verified`) or rejects/revokes with a note; re-deciding the latest submission reverses a mistake |
| `POST /v1/reports`             | Report a post, comment, or profile (reason checklist + optional explanation) |
| `GET /v1/reports/me`           | Reports the caller has filed, newest first          |
| `GET /v1/reports`              | Admin moderation queue; `?status=pending` filters   |
| `PATCH /v1/reports/{id}`       | Admin dismisses, or suspends/bans/reinstates the reported account |
| `GET /v1/dashboard`            | The whole owner dashboard in one request: a health summary per pet, a ranked task list, and the next appointment. Assembled and ranked server-side so this page and the calendar cannot disagree about what is urgent |
| `GET /v1/reminders`            | The caller's reminders; `include_finished=false` drops ones with nothing left to do |
| `POST /v1/reminders`           | Create one; **409 if an identical reminder already exists** (same pet, type, date and title) |
| `GET /v1/reminders/occurrences` | Every dated instance in `start`..`end`, after completions and snoozes — what the month grid draws |
| `POST/DELETE /v1/reminders/{id}/occurrences/{date}/complete` | Tick off one instance, or undo it. Keyed on the SCHEDULED date |
| `POST/DELETE /v1/reminders/{id}/occurrences/{date}/snooze` | Push one instance back (`days` or `until`), or put it back |
| `GET /v1/reminders/duplicates` | Groups of identical reminders, oldest marked to keep |
| `POST /v1/reminders/duplicates/resolve` | Delete named copies; each is re-checked against the live groups first |
| `GET/POST /v1/appointments`    | Both sides of the caller's appointments / send a request (optional `preferred_time`) |
| `POST /v1/appointments/{id}/respond` | The practice confirms or declines; **`scheduled_time` is required to confirm** |
| `POST /v1/appointments/{id}/reschedule` | Either side suggests a new day and time for a confirmed appointment |
| `POST /v1/appointments/{id}/reschedule/respond` | The other side accepts or keeps the original |
| `POST /v1/appointments/{id}/cancel` | Either side calls it off; removes the calendar entry |
| `GET/POST /v1/appointments/{id}/messages` | The thread on one appointment; reading it marks the other side's messages read |
| `GET /healthz`                 | Health check                                       |

### Frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

The Vite dev server proxies `/v1` and `/media` to `http://localhost:8000`, so run
the backend first.

## AI models (ONNX)

The platform ships with two self-contained ONNX classifiers in `backend/`:

| Model file | Input | Output | Labels |
|------------|-------|--------|--------|
| `pet_breed_model.onnx` | `[1, 3, 224, 224]` RGB image | 37-class logits | 37 breeds (12 cat + 25 dog) |
| `pet_age_model.onnx` | `[1, 3, 224, 224]` RGB image | 3-class logits | Puppy/Kitten, Adult, Senior |

On startup the backend loads both models via ONNX Runtime (`ONNXImageAnalysisService`).
If the `.onnx` files are missing or fail to load, it falls back to a deterministic
mock analyzer (`MockImageAnalysisService`).

To regenerate the models (requires `onnx`, `numpy`, and `onnxruntime` — all in
`requirements.txt`):

```bash
cd backend
python generate_real_onnx_models.py
```

## Symptom triage (rule engine)

The photo classifier answers *"what animal is this"*. The triage engine answers
*"should I be worried"*, from a short structured symptom intake. It is a
**knowledge-based system, not a model**: no training data, no accuracy claim we
cannot support, and every verdict is explainable down to the rule that produced it
and the publication that rule came from.

`backend/app/services/triage/` holds the whole thing:

| File | What it is |
|------|-----------|
| `sources.py` | Every publication we read, with URL, access date, and species scope |
| `rules.py` | **The entire clinical logic**, in one readable table |
| `candidates.py` | Rules we could NOT source — parked, not loaded, affect nothing |
| `conditions.py` | Declarative conditions that describe themselves in English |
| `citations.py` | Provenance types and their validation |
| `engine.py` | Two-tier evaluation + the review report |

Two tiers: an **emergency rule** short-circuits the assessment, so a red flag can
never be outweighed by reassuring answers. Everything else contributes a
**weight**; a score of `AMBER_THRESHOLD` or more means "see a vet soon". Ties
round up — an unnecessary check-up costs far less than a missed problem, and that
bias is deliberate and documented.

### Where the rules come from

Every rule traces to a page that was fetched and read on the date recorded in
`sources.py`. Nineteen pages so far, from Merck Veterinary Manual, ASPCA, Cornell
(Feline Health Center and Riney Canine Health Center), the American College of
Veterinary Surgeons, University of Missouri Veterinary Health Center, and VCA
Animal Hospitals — covering emergencies, heatstroke, GDV, feline and canine
anorexia, diarrhoea, urinary obstruction, lameness, polydipsia, urgent eye signs,
uveitis, glaucoma, ocular medication safety, and external, middle, and inner ear
disease.

Species scope is enforced in code. A cat-only or dog-only citation cannot be
attached to a broader rule: constructing that rule raises an error, and matching
also checks the selected pet or image-analysis species before clinical advice is
generated.

Deliberately **not** cited, because the pages could not be read: the AVMA
emergency-care page (renders empty without JavaScript), AAHA (HTTP 403), and
VIN/Veterinary Partner (blocked). If you can access them, they are the obvious
next sources to add.

The evidence is strong for emergencies — publishers agree with each other almost
word for word — and thinner for the graded middle. The current table has 25
emergency rules and 8 graded rules. Heuristics
that felt sensible but had no published source sit in
`candidates.py`, unused, waiting for a veterinarian to accept or reject them. A
test enforces that they cannot leak into the live table.

A second research round measurably improved the rules rather than just adding to
them. It closed a real gap (a dog off its food matched nothing and returned a
confident "monitor at home"), corrected a rule that was simply wrong (lameness
fired identically whether a dog had limped for an hour or a week — VCA's threshold
is 24 hours), and replaced a guess with published eye guidance instead of
extrapolating from Merck's eye-injury rule.
Vomiting and diarrhoea were also split into separate answers, because the sources
give them different thresholds.

A third audit removed the feline corneal-ulcer citation from the cross-species eye
rule. A new red or watery eye now recommends contacting a clinic today and an
examination within 24 hours, while pain, clouding, pupil or vision change, bulging,
abnormal discharge, chemical exposure, or rapid worsening escalates to same-day
urgent care. The result also warns against unsupervised eye medication and links
directly to every source.

A fourth audit added dog-and-cat ear guidance. Ear problems lasting several days,
getting worse, or showing redness, pain, odor, discharge, scratching, or head
shaking now recommend contacting a clinic today for an examination within 24-48
hours. Head tilt, balance or hearing changes, nystagmus, facial weakness, major
swelling, severe discharge, self-injury, or possible foreign material escalate to
same-day urgent care. The 24-48 hour timing is deliberately marked as an
extrapolation requiring veterinary review; the sources support examination and
cause-directed treatment but do not establish one universal time threshold.

### Citation states

1. **Retrieved** — the page was read, URL and access date recorded, and the rule
   records in `supports` what the source actually says. Every rule is here.
2. **Verified** — a named person on the team independently opened the source and
   confirmed it supports the exact claim. **Nothing is here yet.**

`TRIAGE_REQUIRE_VERIFIED_RULES=true` refuses to start the engine until every rule
reaches state 2. Keep it false in development; turn it on before real users.

**To verify a rule:** open its URL, confirm the claim, set `verified_by` on the
citation. *If the source does not support the claim, change the rule — never the
citation.*

### Getting the rules reviewed

The complete clinical logic prints as plain English, including the open questions
and the unsourced candidates:

```bash
cd backend
python -m app.services.triage.report
```

Hand that to a veterinarian (university faculty, a local clinic, your mentor's
network). The report highlights every open reviewer question and any rule marked
**EXTRAPOLATION**, so those are the first things a reviewer can challenge.

### Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest
```

- `tests/test_triage_provenance.py` — integrity: every rule cited, every citation
  carries a real URL and access date, **no rule may cite a page not in
  `sources.py`**, every rule stays inside its citations' species scope, unsourced
  candidates cannot reach the engine, and the strict-mode production gate
  provably blocks unverified rules.
- `tests/test_triage_vignettes.py` — accuracy: 31 realistic cases with an expected
  urgency assigned *before* running the engine, each recording the source-based
  rationale for its label. **Under-triage must be zero**; over-triage is reported,
  not hidden. Current result: 31 vignettes, 31 agreement, 0 over-triage, 0 under-triage.

Labels are team-assigned from the cited sources and still pending veterinary
review. When a reviewer disagrees with a label, change the label rather than the
engine — the one exception is when a *weight* was our arbitrary choice rather than
the source's claim, which is how `increased_thirst` was corrected from 2 to 3.
## Swapping services for AWS

- **Storage** — implement `StorageService` (`backend/app/services/storage.py`) with
  boto3 and return it from `get_storage_service()`. Keys are already generated in
  S3 style (`uploads/YYYY/MM/DD/<uuid>.<ext>`); `object_url` becomes a presigned
  or CloudFront URL and the local `/media` mount in `main.py` goes away.
- **AI** — implement `ImageAnalysisService` (`backend/app/services/ai.py`) against
  Rekognition/SageMaker and return it from `get_analysis_service()`. As long as it
  produces an `AnalysisResult`, no route or frontend code changes.
- **Migrations** — `main.py` currently calls `Base.metadata.create_all` on startup;
  introduce Alembic before evolving the schema.

## MVP simplifications to revisit

- Auth is deliberately minimal (`app/core/security.py`): PBKDF2 password hashes
  and HMAC-signed tokens, standard library only. Before any real deployment,
  swap for a vetted stack (passlib/bcrypt + JWT library, or Amazon Cognito) and
  set a real `SECRET_KEY` in `.env`.
- Reports are reviewed entirely by hand: there is no rate limiting beyond the
  one-open-report-per-target rule, no automated filtering, and content from a
  banned member stays visible in the feed (the account is stopped, its history
  is not purged).
- Verification is a manual human review by design, and the licence document is
  served from the same public `/media` mount as pet photos. Before a real
  deployment, move these documents to private storage with presigned, expiring
  URLs available to admins only.
- Uploads are buffered in memory (bounded by `MAX_UPLOAD_MB`); stream to storage
  for larger files.
- **Email delivery has never been tested against a real inbox.** No SMTP
  credentials exist for this project, so every path up to and including
  `smtplib.SMTP.send_message` is exercised — against the local outbox, and
  against a fake sender in the test suite — and the final hop is not. What
  remains dependent on real deployment credentials, and can only be confirmed
  once they exist: that the relay accepts `SMTP_FROM`; that SPF, DKIM and DMARC
  are aligned for that domain so messages are not filed as spam; that the port
  and TLS mode match the relay; and that the HTML renders acceptably in the mail
  clients the audience actually uses. The retry path is covered by tests with a
  fake sender; it has not been watched against a real server going down.
- The rate limiter is in-process and resets on restart (`app/core/rate_limit.py`).
  Behind more than one instance the effective limit multiplies by the instance
  count; a shared store is the fix, and is deliberately not here for a
  single-container deployment.
