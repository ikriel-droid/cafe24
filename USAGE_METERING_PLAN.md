# Usage Metering Plan

## What To Measure

Measure usage in a way that maps to cost and customer value.

- claims processed
- replies sent
- AI classify calls
- AI draft calls
- active operators
- live Cafe24 sync runs

## Metering Events

Suggested billable event keys:
- `claim.created`
- `claim.closed`
- `reply.sent`
- `ai.classify`
- `ai.draft_reply`
- `operator.active_daily`

## Aggregation Windows

- daily for diagnostics and support
- monthly for invoicing

## Data Sources

- claim records
- reply delivery attempts
- AI invocation logs
- authenticated operator actions

## Guardrails

- keep raw event capture append-only
- generate billing summaries from immutable event records
- do not derive billing from UI counters alone
