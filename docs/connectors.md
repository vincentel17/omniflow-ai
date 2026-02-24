# Connectors Architecture

## Goals

- Keep app logic vendor-agnostic via stable contracts and normalized DTOs.
- Keep CI deterministic with `CONNECTOR_MODE=mock` and provider flags disabled.
- Enforce org-scoped connector operations, encrypted tokens, and audited actions.

## Runtime Control Model

Connector behavior is controlled by org settings:

- `connector_mode`: `mock` or `live`
- `providers_enabled_json` flags:
  - `gbp_publish_enabled`, `meta_publish_enabled`, `linkedin_publish_enabled`
  - `gbp_inbox_enabled`, `meta_inbox_enabled`, `linkedin_inbox_enabled`

If mode is not `live` or a provider flag is off, the connector manager forces mock adapter behavior and records an audit event (`LIVE_BLOCKED`).

## OAuth Broker Guardrails

- OAuth state is stored in Redis with TTL and consumed once.
- Redirect URI must match `ALLOWED_OAUTH_REDIRECT_URIS`.
- Granted scopes are persisted per account and validated in diagnostics.
- Tokens are encrypted at rest using `TOKEN_ENCRYPTION_KEY` and are never returned by API.

## Diagnostics and Recovery

Use:

- `GET /connectors/accounts/{id}/diagnostics`
- `POST /connectors/accounts/{id}/healthcheck`
- `POST /connectors/accounts/{id}/breaker/reset`
- `POST /connectors/accounts/{id}/revoke`

Diagnostics include sanitized health and breaker data only. No token values are exposed.

## Live Provider Status

- GBP: minimal live publish path implemented with retry/taxonomy scaffolding.
- Meta: minimal live publish path scaffolded.
- LinkedIn: minimal live publish path scaffolded.

If provider API access is missing, diagnostics and error taxonomy return a safe unsupported/auth-required status without breaking the publish pipeline.

## Error Taxonomy

Provider errors are normalized into:

- `auth`
- `rate_limit`
- `validation`
- `network`
- `unknown`

Worker publish flow records connector live attempt/success/fail events using sanitized category values.
