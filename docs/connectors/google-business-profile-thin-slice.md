# Google Business Profile Thin Slice

## Scope
This thin slice enables one safe live-capable connector operation for Google Business Profile while preserving full mock parity in CI and local release checks.

Implemented slice:
- One-page review sync into `ReputationReview`
- Manual trigger via connector account diagnostics
- Mock mode by default
- Live mode only when explicitly enabled and fully configured

## Environment flags
Required flags and settings:
- `CONNECTOR_MODE=mock|live`
- `PROVIDER_ENABLE_GBP=true|false`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `OAUTH_REDIRECT_URI`
- `TOKEN_ENCRYPTION_KEY`

Behavior:
- `CONNECTOR_MODE=mock` forces mock sync regardless of provider env state.
- `CONNECTOR_MODE=live` with `PROVIDER_ENABLE_GBP=false` still forces mock mode.
- `CONNECTOR_MODE=live` with `PROVIDER_ENABLE_GBP=true` fails fast at startup if any required GBP env vars are missing.

## Mock vs live behavior
### Mock
- Deterministic review payloads are generated from the connector `account_ref`
- No outbound provider calls occur
- Used in CI and release-check

### Live
- Reads one page of GBP reviews from the provider API
- Validates token presence and required inbox scopes before calling the provider
- Refreshes access token when needed
- Sanitizes all provider failures before persisting to health/audit/event records

## Sync pipeline
Entry point:
- Worker task: `worker.connectors.gbp.sync_reviews`

Pipeline behavior:
- Creates or reuses a `ConnectorWorkflowRun` by idempotency key
- Emits `CONNECTOR_SYNC_ATTEMPT`
- Syncs one review page into `ReputationReview`
- Emits `CONNECTOR_SYNC_SUCCESS` on completion
- Writes audit log `connector.reviews_synced`
- Stores `last_ok_at` and sanitized `last_error_msg` in `ConnectorHealth`

Idempotency:
- Existing `ConnectorWorkflowRun` rows are reused by `idempotency_key`
- Existing GBP reviews are deduplicated by `(org_id, source, external_id)`

Retries:
- Celery task retries on `rate_limit` and `network` connector errors
- Retry backoff is enabled on the task definition

## Failure modes
### 401 / token refresh failure
- Classified as `auth` or `reauth_required`
- Marks connector health error
- Sets re-auth required on connector failure tracking
- Does not log raw token material

### 403 / missing scopes
- Classified as `auth`
- Returns sanitized `missing scopes` error

### 429 / rate limit
- Classified as `rate_limit`
- Updates rate-limit timestamp on health record
- Retries with backoff

### Breaker open
- Worker blocks sync before provider call
- Records dead-letter and sanitized failure metadata

## Diagnostics UI
Route:
- `/settings/integrations/diagnostics`

Displayed GBP-specific fields:
- connector mode (`mock` or `live`)
- provider enabled status
- env readiness checklist (presence only)
- last successful sync timestamp
- last sanitized error

Account-level diagnostics also show:
- last successful sync timestamp
- sync trigger button for GBP accounts

## Staging validation steps
1. Set staging env:
   - `CONNECTOR_MODE=live`
   - `PROVIDER_ENABLE_GBP=true`
   - `GOOGLE_CLIENT_ID`
   - `GOOGLE_CLIENT_SECRET`
   - `OAUTH_REDIRECT_URI`
   - `TOKEN_ENCRYPTION_KEY`
2. Redeploy API and worker.
3. Confirm API boot succeeds. If not, missing env validation should identify the missing keys.
4. Connect a GBP account through the existing connector flow.
5. Open `/settings/integrations/diagnostics` and confirm GBP env readiness shows `ready`.
6. Open the GBP account diagnostics page and trigger `Sync GBP reviews`.
7. Verify:
   - `last_ok_at` updates
   - sanitized error remains empty on success
   - imported reviews appear in reputation data
   - audit log contains `connector.sync_requested` and `connector.reviews_synced`
   - events contain `CONNECTOR_SYNC_REQUESTED` and `CONNECTOR_SYNC_SUCCESS`

## CI expectations
- CI stays in mock mode
- No live GBP calls are made in tests
- Contract and integration coverage is provided through deterministic mock review sync
