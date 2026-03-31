# ClaimMate AI Database Runbook

## Scope

This runbook defines the operational baseline for ClaimMate AI database lifecycle work.

- Primary production database: PostgreSQL
- Recommended schema name: `claimmate`
- Local fallback database: SQLite
- Schema changes: managed with Alembic

## Required Environment

Backend environment variables:

- `DATABASE_URL`
- `DATABASE_SCHEMA`
- `AUTO_CREATE_TABLES`
- `SEED_DEMO_DATA`
- `CLAIM_RETENTION_DAYS`

Recommended production values:

```env
APP_ENV=production
DATABASE_URL=postgresql+psycopg://claimmate:***@db-host:5432/claimmate
DATABASE_SCHEMA=claimmate
AUTO_CREATE_TABLES=false
SEED_DEMO_DATA=false
CLAIM_RETENTION_DAYS=90
```

## Migration Workflow

Apply the latest schema:

```powershell
cd api
.\.venv\Scripts\alembic upgrade head
```

Create a new migration after model changes:

```powershell
cd api
.\.venv\Scripts\alembic revision --autogenerate -m "describe_change"
```

Roll back one revision:

```powershell
cd api
.\.venv\Scripts\alembic downgrade -1
```

## PostgreSQL Schema Organization

- App tables live in `DATABASE_SCHEMA`
- Alembic stores `alembic_version` in the same schema
- The app sets PostgreSQL `search_path` to `DATABASE_SCHEMA`
- Local SQLite ignores `DATABASE_SCHEMA`

## Demo Data Commands

Seed demo data when it is missing:

```powershell
cd api
.\.venv\Scripts\python -m app.scripts.data_lifecycle seed-demo
```

Reset only demo merchants and reseed them:

```powershell
cd api
.\.venv\Scripts\python -m app.scripts.data_lifecycle reset-demo
```

Windows shortcut:

```powershell
.\reset-claimmate-demo.ps1
```

Demo reset removes only merchants marked with `data_origin=demo`. Live merchants are preserved.

## Soft Delete And Retention

Claim records now support:

- `deleted_at`
- `deleted_by`
- `delete_reason`
- `retention_until`

Policy:

- Claims are hidden from normal inbox/detail queries after soft delete
- Claim child rows remain until the retention window expires
- Default retention window is controlled by `CLAIM_RETENTION_DAYS`
- Hard purge is allowed only after `retention_until`

Soft delete a claim manually:

```powershell
cd api
.\.venv\Scripts\python -m app.scripts.data_lifecycle soft-delete-claim --claim-id 1 --actor ops_script --reason "manual cleanup"
```

Purge claims whose retention date has passed:

```powershell
cd api
.\.venv\Scripts\python -m app.scripts.data_lifecycle purge-soft-deleted
```

## Backup And Restore

Backup PostgreSQL schema:

```powershell
pg_dump --format=custom --schema=claimmate --file=claimmate.backup postgresql://claimmate:***@db-host:5432/claimmate
```

Restore PostgreSQL schema:

```powershell
pg_restore --clean --if-exists --schema=claimmate --dbname=postgresql://claimmate:***@db-host:5432/claimmate claimmate.backup
```

SQLite fallback backup:

```powershell
Copy-Item .\api\claimmate.db .\api\claimmate.db.bak
```

SQLite fallback restore:

```powershell
Copy-Item .\api\claimmate.db.bak .\api\claimmate.db -Force
```
