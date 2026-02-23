# Deployment Readiness (Phase 8)

## Topology
- `web`: Vercel (Next.js app)
- `api`: container deploy
- `worker`: container deploy
- shared `postgres` + `redis`

## Environment Profiles
- `development`: local docker-compose, `DEV_AUTH_BYPASS=true` optional
- `staging`: `.env.staging.example` baseline, `DEV_AUTH_BYPASS=false`
- `production`: `.env.production.example` baseline, `DEV_AUTH_BYPASS=false`

## Staging Bring-up
1. Copy `.env.staging.example` to `.env` and fill secrets.
2. Build images:
   - `docker build -f apps/api/Dockerfile -t omniflow-api:staging .`
   - `docker build -f apps/worker/Dockerfile -t omniflow-worker:staging .`
3. Run migrations:
   - `python -m alembic -c apps/api/alembic.ini upgrade head`
4. Run smoke:
   - `pnpm smoke` or `make smoke`

## Deployment Gate
- Run `pnpm deploy-check` before every staging deploy.
- `deploy-check` validates env, image build, migration, and smoke endpoints.

## Safety Defaults
- Keep org-level `connector_mode=mock` and `ai_mode=mock` until pilot validation.
- Keep `enable_auto_posting=false` and `enable_auto_reply=false` in staging/prod.
