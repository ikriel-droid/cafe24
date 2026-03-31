# ClaimMate AI Product Checklist

This checklist tracks the work required to move from the local MVP to a production-ready commercial product.

Important distinction:
- Sections 0 through 11 mostly track what is implemented in the repository and locally verified.
- Section 12 tracks what still requires real external validation, partner coordination, or business sign-off before this can honestly be called production-ready.

Working rules:
- Use `[ ]` for open items.
- Use `[x]` for completed items.
- Update this file immediately when a task is finished.

## 0. Current Baseline

- [x] Local MVP run path stabilized
- [x] Dashboard / inbox / claim detail / policy / Cafe24 console implemented
- [x] Mock AI classification and draft reply flow implemented
- [x] Mock Cafe24 sync / webhook / OAuth placeholder implemented
- [x] Backend tests / frontend build / local run scripts organized

## 1. Live Cafe24 Integration

- [x] Implement real Cafe24 OAuth authorize / callback / token exchange
- [x] Persist and refresh Cafe24 access tokens
- [x] Implement real Cafe24 order / shipment / claim sync
- [x] Connect real Cafe24 webhook endpoint
- [x] Add webhook signature verification and tamper protection
- [x] Add webhook dedupe key handling
- [x] Define webhook failure retry policy
- [x] Replace mock integration state with real integration state models

## 2. Reply Delivery

- [x] Decide real customer reply delivery channel
- [x] Implement reply delivery API
- [x] Add delivery success / failure / retry state model
- [x] Improve delivery history in claim detail
- [x] Define resend policy
- [x] Add retry flow for failed deliveries

## 3. Auth And Tenant Isolation

- [x] Implement operator login
- [x] Isolate data by merchant scope
- [x] Separate roles and permissions
- [x] Add API session / authentication handling
- [x] Separate merchant policies and integration settings
- [x] Restrict audit log access by role

## 4. Background Jobs And Reliability

- [x] Use a Redis-backed job queue in the real flow
- [x] Move sync into asynchronous jobs
- [x] Move webhook processing into asynchronous jobs
- [x] Add job retry / dead-letter handling
- [x] Track real-time job status
- [x] Connect operations buttons to live job state

## 5. Database And Data Lifecycle

- [x] Introduce Alembic migrations
- [x] Organize the production PostgreSQL schema
- [x] Separate seed/demo data from live data
- [x] Define soft delete and retention policy
- [x] Document backup and recovery basics
- [x] Split demo reset commands from normal operations

## 6. AI Productionization

- [x] Implement a real OpenAI provider
- [x] Organize prompt and system rule management
- [x] Improve merchant-policy-aware prompting
- [x] Keep deterministic fallback for AI failures
- [x] Record model cost and token usage
- [x] Define draft quality evaluation criteria
- [x] Make human-review rules explicit

## 7. Operations UX

- [x] Finalize dashboard KPI definitions
- [x] Improve operator notes and handoff UX
- [x] Add audit log search and filtering
- [x] Show audit diff details
- [x] Decide bulk action support
- [x] Define SLA and urgency guidance

## 8. Observability And Safety

- [x] Add structured error logging
- [x] Collect API / webhook / job metrics
- [x] Add alert channel integration
- [x] Define rate limit / timeout / circuit breaker policies
- [x] Apply sensitive-data masking rules
- [x] Add a manager-only diagnostics page

## 9. Deployment And Release

- [x] Prepare production Docker images
- [x] Organize deployment environment templates
- [x] Separate staging and production assets
- [x] Add HTTPS / domain / reverse proxy configuration
- [x] Add CI build / test / release workflows
- [x] Document deployment and incident response

## 10. Commercial Readiness

- [x] Add merchant onboarding flow
- [x] Add installation and operations guides
- [x] Define pricing and packaging
- [x] Define usage metering design
- [x] Review privacy and retention policy
- [x] Define beta customer validation scenario

## 11. Optional Polish

- [x] Add manager launch-kit hub page
- [x] Add copyable onboarding readiness summary

## 12. External Validation And Go-Live Reality Check

- [ ] Validate Cafe24 OAuth end to end with a real merchant app install
- [ ] Validate Cafe24 live sync against real order / shipment / claim payloads
- [ ] Validate Cafe24 live webhook handling with real signed deliveries
- [ ] Decide and validate the real reply-delivery channel beyond manual handoff and generic webhook
- [ ] Run a real staging deployment and complete an operator smoke test there
- [ ] Complete legal / privacy / contract review for commercial release
- [ ] Complete first beta-customer onboarding and capture measured success metrics
