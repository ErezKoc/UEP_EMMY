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
| AI       | Deterministic mock analyzer (swap for AWS Rekognition/SageMaker later)  |

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
│   │   │   └── ai.py             # ImageAnalysisService ABC + MockImageAnalysisService
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
Member 4 — `GET /v1/analysis` history endpoint (**done**); Member 5 — vet
directory endpoint (posts/comments endpoints already exist). Keep
`frontend/src/types/index.ts` in sync with backend schemas — it is the shared
contract.

**Member 5, the share-to-community handoff is ready for you:** the analysis
result page navigates to `/community/new` with route state
`{ prefill: PostPrefill }` (see `types/index.ts`) — a suggested title, content,
`image_url`, and `analysis_id` to pre-fill the new-post form.

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
- Demo accounts (seeded): `demo.owner@uepemmy.com` and `demo.vet@uepemmy.com`,
  password `demo1234` for both.

## Running the backend

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
> focus fields (pets); `ai_analysis_logs` gained `user_id` (history). There are
> no Alembic migrations yet. Thumbnail crop columns and analysis ownership are
> added automatically at startup without deleting existing data. Databases that
> predate the auth or base pet-photo fields may still need to be recreated.

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
| `POST /v1/analysis/upload`     | Multipart image upload → stored + mock AI analysis; optional `animal_id` links it to your pet (auth required for linking) |
| `GET /v1/analysis`             | Your past analyses, newest first; `?animal_id=` filters by pet |
| `GET /v1/posts`                | Recent community posts (newest first, paginated)   |
| `POST /v1/posts`               | Create a post                                      |
| `GET /v1/posts/{id}`           | Post with comments                                 |
| `POST /v1/posts/{id}/comments` | Comment on a post                                  |
| `GET /healthz`                 | Health check                                       |

## Running the frontend

```bash
cd frontend
npm install
npm run dev                       # http://localhost:5173
```

The Vite dev server proxies `/v1` and `/media` to `http://localhost:8000`, so run
the backend first.

## Swapping the mocks for AWS

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
- `POST /v1/posts` still accepts an optional `author_id` and falls back to the
  seeded demo owner. Member 5: switch it to `Depends(get_current_user)` from
  `app/api/deps.py` and drop `author_id` from the payloads.
- Vet accounts are self-declared at signup; the license number is stored but not
  verified. A verification flow (document upload + admin review) is planned.
- Uploads are buffered in memory (bounded by `MAX_UPLOAD_MB`); stream to storage
  for larger files.
