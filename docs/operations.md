# Operations Runbook (Phase 8)

## Incident Response
1. Verify `GET /ready`, `GET /healthz/db`, and Redis connectivity.
2. Check Sentry errors for API and worker.
3. If automation is causing risk, disable org toggles via `PATCH /ops/settings`:
   - `enable_auto_posting=false`
   - `enable_auto_reply=false`
   - `enable_auto_nurture_apply=false`
4. Capture incident timeline from `/audit` and `/events`.

## Rollback
1. Roll app image back to previous tag.
2. Run alembic downgrade one step if needed:
   - `python -m alembic -c apps/api/alembic.ini downgrade -1`
3. Validate with smoke checks.

## Connector Outage Procedure
1. Switch affected org/provider to mock mode:
   - `PATCH /ops/settings` with `"connector_mode":"mock"`
2. Pause high-risk automation:
   - `enable_auto_posting=false`
3. Run healthcheck endpoint for impacted account:
   - `POST /connectors/{provider}/{account_ref}/healthcheck`

## Backup and Restore Rehearsal
- Backup:
  - `scripts/db-backup.sh <optional-output-file>`
- Restore:
  - `scripts/db-restore.sh <backup-file>`
- Rehearsal cadence:
  - weekly in staging
  - monthly in production-like environment
