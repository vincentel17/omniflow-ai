# Render deploy

This repo is ready for Render in mock mode only:

- `CONNECTOR_MODE=mock`
- `AI_MODE=mock`
- no live ads
- no live connector OAuth flows enabled by default

The Blueprint file lives at `infra/render/render.yaml`. Render supports custom Blueprint paths, so point the Blueprint setup flow at that file instead of the repo root.

## Service layout

The Blueprint defines:

- `omniflow-web`
- `omniflow-api`
- `omniflow-worker`
- `omniflow-postgres`
- `omniflow-redis`
- `omniflow-seed-demo` cron
- `omniflow-demo-simulator-tick` cron

`omniflow-api` uses `preDeployCommand: bash scripts/render-migrate.sh`, so every successful deploy runs migrations before the new revision becomes live.

## Before you start

1. Use the verified baseline branch or tag you actually want to deploy.
2. Keep Node pinned to `20.18.0` and Python pinned to `3.12.8`.
3. Do not enable live connectors, live AI, or live ads in Render until credentials and approvals exist.
4. Keep `CONNECTOR_MODE=mock` and `AI_MODE=mock` in both staging and production for this deployment shape.

## Staging deploy checklist

1. In Render, create a new Blueprint from this repo.
2. Set the Blueprint file path to `infra/render/render.yaml`.
3. Apply the Blueprint to create the stack.
4. Populate the required env vars:
   - `APP_ENV=staging`
   - `TOKEN_ENCRYPTION_KEY=<base64-or-random-string>`
   - `API_BASE_URL=https://<api-service>.onrender.com`
   - `NEXT_PUBLIC_API_BASE_URL=https://<api-service>.onrender.com`
   - `NEXT_PUBLIC_APP_URL=https://<web-service>.onrender.com`
5. Leave these off or blank in staging unless you are explicitly testing them:
   - `APP_ENCRYPTION_KEY`
   - `OPENAI_API_KEY`
   - connector OAuth client ids and secrets
6. Enable deterministic demo behavior:
   - `ALLOW_QA_SEED=true` on `omniflow-seed-demo`
   - `DEMO_SIMULATOR=true` on `omniflow-demo-simulator-tick`
   - `NEXT_PUBLIC_DEMO_SIMULATOR=true` on `omniflow-web`
   - `DEMO_SIM_SEED=1234` on `omniflow-demo-simulator-tick`
7. Trigger a manual deploy of `omniflow-api`. Confirm the pre-deploy migration step succeeds.
8. Run the seed cron once manually from the Render dashboard.
9. Run the simulator cron once manually from the Render dashboard.
10. Verify health:
    - `GET https://<api-service>.onrender.com/healthz`
    - `GET https://<api-service>.onrender.com/healthz/db`
    - `GET https://<api-service>.onrender.com/ready`
11. Run the smoke script:
    - `BASE_URL=https://<api-service>.onrender.com bash scripts/render-smoke.sh`
12. Open the web app and verify:
    - dashboard loads
    - preview org selector works
    - `/settings/integrations/diagnostics` loads
    - simulator badge appears on the dashboard

## Production deploy checklist

Production should use the same Blueprint file, but with stricter settings:

1. Create a second Blueprint or environment from the same `infra/render/render.yaml`.
2. Set:
   - `APP_ENV=production`
   - `TOKEN_ENCRYPTION_KEY=<required>`
   - `APP_ENCRYPTION_KEY=<required>`
   - `API_BASE_URL=https://<api-service>.onrender.com`
   - `NEXT_PUBLIC_API_BASE_URL=https://<api-service>.onrender.com`
   - `NEXT_PUBLIC_APP_URL=https://<web-service>.onrender.com`
3. Keep:
   - `CONNECTOR_MODE=mock`
   - `AI_MODE=mock`
   - `ALLOW_QA_SEED=false`
   - `DEMO_SIMULATOR=false`
   - `NEXT_PUBLIC_DEMO_SIMULATOR=false`
4. Do not run the seed cron in production.
5. Do not run the simulator cron in production.
6. Deploy `omniflow-api` and confirm migrations succeed.
7. Verify:
   - `/healthz`
   - `/healthz/db`
   - `/ready`
8. Run:
   - `BASE_URL=https://<api-service>.onrender.com bash scripts/render-smoke.sh`

Note: production in mock mode is infrastructure validation, not a live customer deployment. If you do not seed preview users and org memberships, the full UI journey is intentionally limited until a real auth rollout exists.

## Staging E2E option

If you want to run Playwright against staging:

1. Point `apps/web/playwright.config.ts` or CI env at the staging web URL.
2. Keep the stack in mock mode.
3. Seed staging first.
4. Run the existing mock-safe E2E suite from CI or locally.

## Rollback

1. Roll back the failing service in the Render dashboard to the previous healthy deploy.
2. Do not manually downgrade the database schema.
3. Fix the migration or app issue in Git, then redeploy forward.

## Filesystem and exports

This deployment path does not rely on persistent local filesystem state.

- API exports used by the current MVP are transient HTTP responses or database-backed JSON references.
- The compliance DSAR export reference is stored in the database, not on local disk.
- There is no S3-backed export implementation in this repo today, so do not assume durable object storage for generated artifacts yet.

## Operator notes

- `/ready` is the Render health gate because it verifies both Postgres and Redis.
- Render Key Value uses `type: keyvalue` in Blueprints. The older `redis` alias is deprecated.
- `omniflow-seed-demo` and `omniflow-demo-simulator-tick` are safe in production because they no-op unless the corresponding env flags are enabled, but the expected operator setting is to keep them disabled there.
