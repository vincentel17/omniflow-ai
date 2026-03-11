# Staging Hardening Report

Date: 2026-03-10
Repo: omniflow-ai-repo
Scope: Deployment reliability, environment safety, startup readiness, worker observability

## 1) Render blueprint validation
File reviewed: `infra/render/render.yaml`

Validated services:
- `omniflow-web` (`type: web`, Node runtime)
- `omniflow-api` (`type: web`, Python runtime)
- `omniflow-worker` (`type: worker`, Python runtime)
- `omniflow-postgres` (managed database)
- `omniflow-redis` (`type: keyvalue`)

Validated deployment behaviors:
- API `preDeployCommand` runs migrations via `bash scripts/render-migrate.sh`.
- API health gate uses `healthCheckPath: /ready`.
- Service dependencies use Render references (`fromDatabase`, `fromService`) for DB/Redis wiring.

Hardening updates applied to blueprint:
- Added `ADS_MODE=mock` for API and worker.
- Added `JWT_SECRET` env key (managed secret) for API and worker.

## 2) Environment variable schema validation (fail-fast)
File updated: `apps/api/app/settings.py`

Implemented validations:
- Enforced valid mode values for `CONNECTOR_MODE`, `AI_MODE`, `ADS_MODE` (`mock|live`).
- Non-development contract checks enforce presence of:
  - `DATABASE_URL`
  - `REDIS_URL`
  - `TOKEN_ENCRYPTION_KEY`
- Live safety checks retained/enforced:
  - `OAUTH_REDIRECT_URI` required when connector mode is live.
  - `OPENAI_API_KEY` required when AI mode is live.
- Production-only checks enforce:
  - `JWT_SECRET`
  - `APP_ENCRYPTION_KEY`

Secret safety:
- Validation errors report missing variable names only.
- No secret values are logged.

## 3) Migration safety
File reviewed: `scripts/render-migrate.sh`

Validated:
- Script fails fast if `DATABASE_URL` is missing.
- Runs `python -m alembic -c apps/api/alembic.ini upgrade head` before API health routing.
- Existing Render pre-deploy hook is correct for migration-before-ready behavior.

## 4) Health checks
Files reviewed: `apps/api/app/routers/health.py`, `infra/render/render.yaml`

Validated:
- `/health` returns liveness.
- `/ready` checks DB and Redis and returns `503` if either is down.
- Render API health check points to `/ready`.

## 5) Worker startup validation
File updated: `apps/worker/omniflow_worker/main.py`

Implemented:
- Startup self-check validates DB connectivity, Redis ping, and task registration.
- Worker exits with clear startup error (`SystemExit(1)`) on validation failure.
- Added startup readiness log event (`startup_ready`) and failure event (`startup_failed`).

## 6) Logging and observability
Files updated: `apps/api/app/main.py`, `apps/worker/omniflow_worker/main.py`

API structured logs now include:
- `request_id`
- `org_id` (from `X-Org-Id` header when present)
- `service`
- `event_type`
- method/path/status/duration

Worker structured logs now include:
- `service`
- `event_type`
- task execution lifecycle events:
  - `job_start`
  - `job_success`
  - `job_failure`

## 7) Connector safety
Validated/retained:
- Default mode remains safe (`mock`).
- Live mode enforces credential/environment readiness checks.
- Missing live requirements fail fast in settings validation.

## 8) Security validation
Validated/retained:
- Token/session secret derivation supports managed `JWT_SECRET` with fallback to token key.
- Secrets loaded from environment and not printed in logs.
- Existing RBAC checks remain in place; no bypass paths added.

## 9) Deployment verification script
File added: `scripts/render-smoke.sh`

Script validates:
- API `/health`
- API `/ready`
- basic API route (`/healthz`)
- worker queue ping (`worker.health.ping` via Celery broker)

Note:
- Script is Bash-based for Render/Linux runtime.
- Local Windows shell in this run had no `/bin/bash`; execution should be done in Render shell, Linux, or Git Bash.

## 10) Verification results
- `pnpm run check`: PASS
- `pnpm run test`: PASS
- `pnpm run release-check`: PASS

Conclusion:
- Staging deployment hardening changes are validated and release gates are green.
