# Merchant Onboarding Guide

## Purpose

Use this guide when a new merchant is about to start beta usage of ClaimMate AI.

The onboarding goal is simple:
- connect Cafe24 safely
- confirm the merchant policy is loaded
- validate the reply workflow with a real operator
- make sure diagnostics and support contacts are ready

## Entry Criteria

Before starting, confirm all of the following:
- the merchant has a named owner and a day-to-day operator
- Cafe24 app install permission is available
- refund, exchange, and exception policy text is ready
- the preferred reply-delivery path is decided
- alert routing destination is decided

## Onboarding Sequence

1. Create or confirm manager access.
2. Open `/onboarding` and confirm the merchant context.
3. Connect Cafe24 OAuth from `/integrations/cafe24`.
4. Run the first live sync.
5. Configure or confirm webhook secret handling.
6. Review `/settings/policy` and save the merchant policy.
7. Check `/admin/diagnostics` for rate limits, masking, and alerts.
8. Process three real or shadow claims end to end.
9. Confirm reply delivery and follow-up handling.
10. Start the beta validation window.

## Exit Criteria

Onboarding is complete when:
- Cafe24 is connected
- at least one live sync has completed successfully
- policy text is saved
- diagnostics are healthy enough for beta
- a manager can hand off to an agent without confusion
- the merchant can process a real claim from inbox to reply

## Evidence To Keep

Save the following for each onboarded merchant:
- merchant owner and operator names
- Cafe24 mall identifier
- reply delivery mode
- beta start date
- first sync timestamp
- support contact and escalation channel
