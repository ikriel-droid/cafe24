# Installation Guide

## Local Evaluation Install

1. Copy the example environment files.
2. Start the local stack with Docker Compose or the local scripts.
3. Log in with a demo operator account.
4. Open `/dashboard` and `/onboarding`.

Recommended order:
- `Copy-Item .env.example .env`
- `Copy-Item api/.env.example api/.env`
- `Copy-Item web/.env.example web/.env.local`
- `docker compose up --build`

## Hosted Install Outline

For a hosted environment:
- provision PostgreSQL
- provision Redis
- configure HTTPS and a reverse proxy
- set Cafe24 credentials and webhook secret
- set OpenAI credentials if live AI is required
- run database migrations before traffic is enabled

## Required Environment Groups

- application: app name, environment, session settings
- database: connection URL and schema
- queue: Redis URL and worker settings
- Cafe24: client id, client secret, redirect URI, webhook secret
- AI: OpenAI API key, model, cost settings
- observability: alert webhook, rate limits, circuit breaker settings

## Post-Install Checks

After install, verify:
- `/health`
- operator login
- `/admin/diagnostics`
- `/integrations/cafe24`
- one sync job and one reply-delivery flow
