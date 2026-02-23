# Connectors Architecture (Phase 2)

## Goals

- Keep app logic vendor-agnostic via stable contracts.
- Run safely in `CONNECTOR_MODE=mock` by default.
- Enforce strict org scoping for all connector resources.
- Encrypt tokens at rest and never expose them through API responses.

## Components

- `apps/api/app/routers/connectors.py`
  - OAuth broker endpoints and connector account/health APIs.
- `apps/api/app/services/token_vault.py`
  - Symmetric encryption/decryption and token persistence.
- `apps/api/app/services/oauth_state.py`
  - CSRF state generation/consumption in Redis.
- `apps/api/app/services/connector_manager.py`
  - Provider manager with mock-first publisher and health check surface.

## Runtime Modes

- `CONNECTOR_MODE=mock` (default)
  - No external provider calls.
  - Callback stores deterministic mock tokens (encrypted).
- `CONNECTOR_MODE=live`
  - Reserved for provider-specific implementations.
  - Current behavior returns `501 Not Implemented` for token exchange.

## Security Notes

- Token encryption key: `TOKEN_ENCRYPTION_KEY` (Fernet key).
- Access/refresh token plaintext is never stored in DB.
- Connector APIs are tenant-scoped via request context org id.
- AuditLog and Event rows are written for link/unlink/health operations.

## How to Add a Provider Safely

1. Add provider id to `SUPPORTED_PROVIDERS`.
2. Add env-based config checks in `_provider_is_configured`.
3. Implement live token exchange behind `CONNECTOR_MODE=live`.
4. Keep normalized response models stable; isolate vendor fields inside adapter code.
5. Add/extend contract and integration tests for tenant isolation and token handling.

