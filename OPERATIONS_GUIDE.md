# Operations Guide

## Daily Routine

- check `/dashboard` for backlog, automation queue, and follow-up queue
- check `/admin/diagnostics` for alerts and recent errors
- review Cafe24 sync and webhook health
- handle urgent claims first
- confirm reply delivery failures are retried or escalated

## Weekly Routine

- review AI fallback rate and human-review rate
- review response times against SLA
- review failed webhooks and dead-letter jobs
- review follow-up queue aging
- review policy changes requested by merchants

## Operator Handoff

When handing off a claim:
- leave an internal note with the current status
- explain what the customer is waiting for
- link any external dependency such as Cafe24 or delivery issues
- note whether a reply was already sent

## Escalation Cases

Escalate to a manager when:
- refund or exception policy is unclear
- a live Cafe24 sync fails repeatedly
- reply delivery keeps failing
- sensitive-data or diagnostics alerts appear
- the merchant asks for configuration changes during beta
