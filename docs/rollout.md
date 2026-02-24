# Phase 9 Live Connector Rollout

## Staged Rollout Sequence

1. Staging with `connector_mode=mock` and all provider flags disabled.
2. Staging with GBP live enabled for one test org/account.
3. Production pilot org with GBP live enabled only.
4. Enable Meta live for pilot org after diagnostics and breaker validation.
5. Enable LinkedIn live for pilot org after diagnostics and breaker validation.

## Acceptance Checklist Per Provider

- OAuth account linked and diagnostics show required scopes.
- Healthcheck succeeds in current environment.
- Breaker state is `closed` and failure count is stable.
- Publish job runs end-to-end with idempotent behavior.
- AuditLog and Event entries are present for live call attempt/result.

## Safety Checklist Before Enabling Live

- `connector_mode` set to `live` for target org only.
- Provider-specific publish flag enabled for target provider only.
- `enable_auto_posting` remains controlled by org policy.
- On-call operator knows breaker reset and revoke procedures.

## Rollback Procedure

1. Set org `connector_mode` back to `mock`.
2. Disable provider publish flag in `providers_enabled_json`.
3. Revoke affected connector account if auth issues persist.
4. Review diagnostics and ConnectorHealth history before retrying live.
