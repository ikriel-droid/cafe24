# ClaimMate AI

ClaimMate AI is a local MVP skeleton for a Korean B2B SaaS that helps Cafe24 merchants manage cancellation, exchange, return, refund, delivery, and order inquiry workflows.

## Stack

- Frontend: Next.js App Router + TypeScript
- Backend: FastAPI + SQLAlchemy
- Database: PostgreSQL for the recommended local stack
- Cache placeholder: Redis
- Local infra: Docker Compose with `web`, `api`, `postgres`, and `redis`
- AI layer: deterministic offline mock provider with an OpenAI placeholder boundary

## Folder Structure

```text
claimmate-ai/
|- api/                    # FastAPI app, domain logic, seed data, tests
|- web/                    # Next.js app router frontend
|- docker-compose.yml      # Full local stack: web, api, postgres, redis
|- .env.example            # Docker Compose variables
|- api/.env.example        # Backend environment example
|- web/.env.example        # Frontend environment example
`- README.md
```

## Environment Setup

1. Copy root env for Docker Compose:

```powershell
Copy-Item .env.example .env
```

2. Copy backend env:

```powershell
Copy-Item api/.env.example api/.env
```

By default this example keeps `DATABASE_URL` empty, so the backend falls back to local SQLite. If you want to use PostgreSQL from Docker Compose, set `DATABASE_URL=postgresql+psycopg://claimmate:claimmate@127.0.0.1:5432/claimmate` in `api/.env`.
Optional Cafe24 placeholder vars are also included there: `CAFE24_CLIENT_ID`, `CAFE24_CLIENT_SECRET`, and `CAFE24_REDIRECT_URI`.

3. Copy frontend env:

```powershell
Copy-Item web/.env.example web/.env.local
```

The backend defaults to a local SQLite file if `DATABASE_URL` is blank or not set. For Docker Compose, the API container overrides this and connects to the `postgres` service automatically.

## Run Everything With Docker Compose

```powershell
docker compose up --build
```

This starts:

- web: [http://127.0.0.1:3000/dashboard](http://127.0.0.1:3000/dashboard)
- api: [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- postgres: `127.0.0.1:5432`
- redis: `127.0.0.1:6379`

Stop the stack with:

```powershell
docker compose down
```

If you want a clean rebuild including database volume reset:

```powershell
docker compose down -v
docker compose up --build
```

## Run Only PostgreSQL and Redis

```powershell
docker compose up -d postgres redis
```

## Run the Backend

```powershell
cd api
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e .[dev]
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
```

## Run the Frontend

```powershell
cd web
npm.cmd install
npm.cmd run dev
```

Open [http://127.0.0.1:3000/dashboard](http://127.0.0.1:3000/dashboard).
The root route redirects to `/dashboard`, and `/inbox` remains the working queue view.

The Cafe24 placeholder console is available at `/integrations/cafe24` and supports offline Mock Sync plus simulated OAuth callback testing.

## One-Command Local Start

If you want one command that starts the backend and serves the exported frontend through the same local server:

```powershell
.\start-claimmate.ps1
```

Then open [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/).

To stop the local listeners later:

```powershell
.\stop-claimmate.ps1
```

## Completion Runner

If you want one script that organizes the remaining local completion work and executes every automatable stage in order, use:

```powershell
.\complete-claimmate.ps1
```

If you prefer a plain command wrapper on Windows:

```powershell
.\complete-claimmate.cmd
```

That default `all` flow runs:

- `prepare`: copies env files if missing, creates the backend venv, installs backend/frontend dependencies
- `docker`: starts `postgres` and `redis` when Docker is available, otherwise falls back to SQLite
- `test`: runs backend pytest
- `build`: runs the frontend production build
- `start`: launches the app locally at [http://127.0.0.1:8000/dashboard/](http://127.0.0.1:8000/dashboard/)
- `smoke`: checks health, seeded claims, policy, mock sync, classify, and draft reply
- `roadmap`: prints the remaining manual blockers to reach a production-complete ClaimMate AI
- `report`: writes `run-artifacts/latest-completion-report.md` and `.json` with the run result, smoke summary, and remaining manual blockers

You can also run a subset of stages:

```powershell
.\complete-claimmate.ps1 -Stage prepare,test,build
.\complete-claimmate.ps1 -Stage start,smoke
.\complete-claimmate.ps1 -Stage roadmap
.\complete-claimmate.ps1 -Stage report
.\complete-claimmate.ps1 -Stage stop
```

If you want to skip Docker even when it is installed:

```powershell
.\complete-claimmate.ps1 -SkipDocker
```

After any run that includes `report`, inspect:

- `run-artifacts/latest-completion-report.md`
- `run-artifacts/latest-completion-report.json`

## Useful Commands

Backend tests:

```powershell
cd api
.\.venv\Scripts\python -m pytest
```

Frontend production build:

```powershell
cd web
npm.cmd run build
```

Docker logs:

```powershell
docker compose logs -f api
docker compose logs -f web
```

## Known Limitations

- Authentication and tenant isolation are intentionally omitted.
- Redis is provisioned but not actively used yet beyond the integration boundary placeholder.
- Cafe24 OAuth, webhooks, and sync are scaffolded only and do not perform live network calls.
- OpenAI integration is a stub and always falls back to the deterministic mock logic.
- The UI focuses on clarity and local runnability, not production-grade design coverage.
- Docker Compose has not been executed in this workspace because Docker is not installed here, so the container definitions were added conservatively and kept close to the already verified local commands.
- `complete-claimmate.ps1` automates everything that is local and deterministic, but Cafe24 partner approval, real endpoint mapping, auth, tenant isolation, and production deployment still require manual implementation work outside the current MVP.
