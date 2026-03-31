# Live Cafe24 OAuth Validation Runbook

## Goal

Validate the first item in section 12 with a real Cafe24 merchant app install:

- OAuth authorize opens correctly
- callback returns to ClaimMate
- token exchange succeeds
- ClaimMate persists the connection state

## Preconditions

Before running:
- fill `CAFE24_CLIENT_ID`, `CAFE24_CLIENT_SECRET`, and `CAFE24_REDIRECT_URI` in `api/.env`
- make sure the local app is reachable at `http://127.0.0.1:8000`
- have access to a real Cafe24 merchant that can install the app

## One-Command Runner

```powershell
cd c:\Users\Administrator\.vscode\cli\cafe24\claimmate-ai
.\validate-cafe24-live-oauth.ps1
```

What the runner does:
- starts the app if it is down
- logs in as the local manager account
- fetches the live Cafe24 authorize URL
- opens the browser
- waits for OAuth to complete
- writes result artifacts to `run-artifacts/latest-live-oauth-validation.md` and `.json`

## Manual Step You Still Need

The only manual step is the real Cafe24 browser authorization itself:
- sign in to Cafe24
- approve the app install
- wait for the callback to return to ClaimMate

## Success Criteria

The validation is successful when the report shows:
- `status: validated`
- `connected_after: true`
- a non-empty `access_token_expires_at`

## Failure Modes

- `blocked_missing_env`
  - Cafe24 credentials are still missing in `api/.env`
- `blocked_app_unavailable`
  - the local app could not be reached
- `blocked_missing_authorize_url`
  - the API did not return an authorize URL
- `pending_manual_auth`
  - the browser OAuth step was not completed within the timeout window
