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
        ├── api/client.ts         # Typed fetch client
        ├── lib/format.ts         # Display helpers
        ├── components/           # ImageUpload, AnalysisCard, CommunityFeed
        └── pages/Dashboard.tsx
```

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

API docs: <http://localhost:8000/docs>

| Endpoint                       | Description                                        |
| ------------------------------ | -------------------------------------------------- |
| `POST /v1/analysis/upload`     | Multipart image upload → stored + mock AI analysis |
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

- No authentication yet: `POST /v1/posts` accepts an optional `author_id` and falls
  back to the seeded demo owner. Replace with a real auth dependency.
- Uploads are buffered in memory (bounded by `MAX_UPLOAD_MB`); stream to storage
  for larger files.
