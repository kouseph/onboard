# FastAPI Backend

## Environment Variables

Set the following for GitHub operations:

- `GITHUB_TOKEN`: a classic PAT or GitHub App installation token with repo scope
- `GITHUB_TARGET_OWNER`: org or user where candidate repos will be created

Database:

- `SUPABASE_DB_URL` (preferred) or `DATABASE_URL`: Postgres DSN (Supabase or local)
  - Local example: `postgresql+psycopg2://postgres:postgres@localhost:5432/candidate_code`
  - Supabase example: `postgresql+psycopg2://postgres:[PASSWORD]@db.[project-ref].supabase.co:5432/postgres?sslmode=require`

Email:

- `RESEND_API_KEY`: API key for Resend
- `EMAIL_FROM`: onboarding@resend.dev (this is the free option, otherwise put in your own domain)

Frontend URL used in emails:

- `PUBLIC_APP_BASE_URL`: e.g. `http://localhost:3000` or your Vercel URL

## Install and Run

```bash
pip install -r requirements.txt
python -m app.main
```

## CORS

`app.main` enables CORS for these origins by default:

- `https://afterquery-test.vercel.app`
- `http://localhost:3000`
- `http://127.0.0.1:3000`

If your frontend URL differs, update the `origins` list in `app/main.py` (or wire it to an env var).

## API Overview

- `POST /api/assessments` create assessment
- `GET /api/assessments` list assessments
- `POST /api/invites` create invite for candidate
- `GET /api/invites` list invites
- `GET /api/candidate/start/{slug}` view start page metadata
- `POST /api/candidate/start/{slug}` start assessment (creates repo, token entry)
- `POST /api/candidate/submit/{slug}` submit assessment (revokes tokens, snapshot)

## Deployment (Railway)

This service relies on `git` for repository provisioning. The backend has a `Dockerfile` that installs `git` and `openssh-client` to ensure it works on Railway.

Steps:

1. In Railway, create a service from this repo and set the project root to the `backend/` folder (or select the backend service if using monorepo).
2. Ensure Railway uses the provided `Dockerfile` in `backend/`.
3. Set env vars: `SUPABASE_DB_URL` (or `DATABASE_URL`), `GITHUB_TOKEN`, `GITHUB_TARGET_OWNER`, `RESEND_API_KEY`, `EMAIL_FROM`, `PUBLIC_APP_BASE_URL`.
4. Deploy. Railway will start with `python -m app.main`.

Troubleshooting:

- 502 on `POST /api/candidate/start/{slug}` with error mentioning `git`: confirm the Dockerfile is used (must install `git`).
- CORS errors: verify your frontend origin is listed in `origins` inside `app/main.py` and redeploy.
