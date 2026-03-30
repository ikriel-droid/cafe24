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
Auth and session vars are also included there: `SESSION_SECRET_KEY`, `SESSION_COOKIE_NAME`, `SESSION_MAX_AGE_SECONDS`.
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

The Cafe24 console is available at `/integrations/cafe24` and supports offline Mock Sync, simulated OAuth callback testing, live OAuth/token storage, live webhook verification, and manual Live Sync execution. Mock integration activity is now stored in the database instead of in-memory state, so status survives engine resets and app restarts.

## Demo Operator Accounts

The local seed now creates operator accounts with merchant isolation and role-based access:

- `manager@alpha-seller.local` / `demo1234`
- `agent@alpha-seller.local` / `demo1234`
- `viewer@alpha-seller.local` / `demo1234`
- `manager@beta-select.local` / `demo1234`

Role behavior in the local MVP:

- `manager`: full access including policy and Cafe24 integration settings
- `agent`: claim processing, classification, draft generation, and reply delivery
- `viewer`: read-only access to dashboard, inbox, and claim detail without audit log visibility

## Reply Delivery Modes

Reply delivery now has an explicit boundary instead of a pure placeholder.

- `REPLY_DELIVERY_MODE=manual_handoff`
  - Default local mode
  - Records that an operator handed off the reply through the merchant support channel
  - Marks the send as successful and stores a delivery attempt history row
- `REPLY_DELIVERY_MODE=webhook`
  - Sends the reply payload to `REPLY_DELIVERY_WEBHOOK_URL`
  - Stores success / failure / retry history in the database
  - Useful when wiring ClaimMate into a downstream outbound messaging adapter

Relevant backend env vars live in `api/.env.example`:

- `REPLY_DELIVERY_MODE`
- `REPLY_DELIVERY_WEBHOOK_URL`
- `REPLY_DELIVERY_WEBHOOK_TOKEN`
- `REPLY_DELIVERY_TIMEOUT_SECONDS`
- `REPLY_DELIVERY_MANUAL_CHANNEL_LABEL`

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

## Remaining Product Checklist

The tracked remaining work lives in:

- `PRODUCT_CHECKLIST.md`

This file is the source of truth for post-MVP work. As items are completed, they should be updated from `[ ]` to `[x]`.

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

- Authentication and tenant isolation are implemented for local operator accounts, but there is no production-grade identity provider, password reset flow, or MFA yet.
- Redis is provisioned but not actively used yet beyond the integration boundary placeholder.
- Cafe24 OAuth, live webhook verification, manual webhook retry, and manual Live Sync now perform real network calls when Cafe24 credentials are configured, but background jobs and full production hardening are still pending.
- OpenAI integration is a stub and always falls back to the deterministic mock logic.
- The UI focuses on clarity and local runnability, not production-grade design coverage.
- Docker Compose has not been executed in this workspace because Docker is not installed here, so the container definitions were added conservatively and kept close to the already verified local commands.
- `complete-claimmate.ps1` automates everything that is local and deterministic, but Cafe24 partner approval, real endpoint mapping, background jobs, production auth hardening, and deployment still require manual implementation work outside the current MVP.
