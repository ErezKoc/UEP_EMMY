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

| Routes                                              | Owner    | Area |
| --------------------------------------------------- | -------- | ---- |
| `/`, `/dashboard`, `*` (404), shell, `components/ui` | Member 1 | Design system, layout, landing |
| `/login`, `/signup`, `/profile`, `/settings`         | Member 2 | Auth & profiles (`pages/auth/`) |
| `/pets`, `/pets/:petId`                              | Member 3 | Pet management (`pages/pets/`) |
| `/analyze`, `/analysis/history`                      | Member 4 | AI analysis flow (`pages/analysis/`) |
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
feed, posts/comments, and veterinarian directory (**done**). Keep
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

## Running with Docker (recommended)

The quickest way to start both the backend and frontend together:

```bash
docker compose up --build
```

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

Tables are created and demo data (a pet owner, a veterinarian, sample posts) is
seeded automatically on first startup. No PostgreSQL handy? Set
`DATABASE_URL=sqlite:///./uep_emmy.db` in `.env` for a throwaway local database.

> **Schema changed (July 2026):** `users` gained `password_hash`, `bio`, and
> `avatar_url` (auth); `animals` gained `birth_date`, `photo_url`, and thumbnail
> focus fields (pets); `ai_analysis_logs` gained `user_id` (history); `posts`
> gained `analysis_id` plus `image_url` (community sharing); and `users` gained
> `verification_status` alongside the new `vet_verifications` table (vet
> verification). There are no Alembic migrations yet. The newer thumbnail,
> analysis ownership, post attachment, and verification columns are added
> automatically at startup without deleting existing data.
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
| `GET /v1/posts`                | Paginated posts; supports `q` and `author_role`    |
| `POST /v1/posts`               | Create a signed-in user's post; optional analysis  |
| `GET /v1/posts/{id}`           | Post with comments                                 |
| `POST /v1/posts/{id}/comments` | Add a signed-in user's comment                     |
| `GET /v1/vets`                 | Public veterinarian directory; supports `q` and `verified_only`, verified listed first |
| `POST /v1/verification`        | Vet submits a licence document → status `pending`  |
| `GET /v1/verification/me`      | The caller's own submissions, newest first         |
| `GET /v1/verification`         | Admin review queue; `?status=pending` filters      |
| `PATCH /v1/verification/{id}`  | Admin approves (`verified`) or rejects/revokes with a note; re-deciding the latest submission reverses a mistake |
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
- Verification is a manual human review by design, and the licence document is
  served from the same public `/media` mount as pet photos. Before a real
  deployment, move these documents to private storage with presigned, expiring
  URLs available to admins only.
- Uploads are buffered in memory (bounded by `MAX_UPLOAD_MB`); stream to storage
  for larger files.
