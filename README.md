# OmniFlow AI

OmniFlow AI is **a conversion-optimized, AI-assisted revenue operations layer for vertical SMBs that turns social engagement into attributable revenue outcomes**.

## Monorepo layout

- `apps/web`: Next.js App Router frontend
- `apps/api`: FastAPI backend
- `apps/worker`: Celery worker
- `packages/*`: shared modules (UI, schemas, policy, connectors, vertical packs)
- `infra`: deployment-oriented infra artifacts
- `scripts`: operational checks and guardrails
- `docs`: architecture and release documentation
- `tests`: cross-app test assets

## Local setup

1. Copy env file: `cp .env.example .env` (PowerShell: `Copy-Item .env.example .env`)
2. Run preflight: `powershell -ExecutionPolicy Bypass -File ./scripts/preflight.ps1`
3. Install dependencies: `pnpm install --frozen-lockfile`
4. Start stack: `docker compose up -d --build`

## CI overview

`/.github/workflows/ci.yml` enforces:

- lint + format checks
- web/api typechecks
- unit tests
- integration tests (api + postgres + redis)
- connector contract tests
- security scans (`npm audit`, `pip-audit`, `semgrep`)
- build verification
- migration forward/rollback test
- Playwright smoke e2e

## Release gates

Run `make release-check` before release. It chains static checks, tests, e2e, build, and security scans.

## Phase 1 usage

1. Apply migrations:
   - `make migrate`
2. Seed dev org/user/membership/default vertical pack:
   - `make seed`
3. Use dev auth headers in local requests (or enable API dev bypass):
   - `X-Omniflow-User-Id`, `X-Omniflow-Org-Id`, `X-Omniflow-Role`
4. Switch vertical pack:
   - `POST /verticals/select` with JSON `{ "pack_slug": "generic" | "real-estate" }`
5. View events:
   - `GET /events?limit=20&offset=0`
6. View audit logs:
   - `GET /audit?limit=20&offset=0`

## Phase 2 usage (mock connectors)

1. Set connector env vars:
   - `CONNECTOR_MODE=mock`
   - `TOKEN_ENCRYPTION_KEY=<fernet-key>`
   - `OAUTH_REDIRECT_URI=http://localhost:3000/api/auth/callback`
2. Start OAuth flow (mock):
   - `POST /connectors/{provider}/start`
3. Complete callback (mock token exchange):
   - `POST /connectors/{provider}/callback`
4. List tenant-scoped connector accounts:
   - `GET /connectors/accounts`
5. Run health checks:
   - `POST /connectors/{provider}/{account_ref}/healthcheck`
   - `GET /connectors/health`

See `docs/connectors.md` for architecture and extension guidance.

## Phase 4 usage (Unified Inbox + Lead Engine, mock mode)

1. Ingest a mock inbound thread:
   - `POST /inbox/ingest/mock`
2. Review inbox threads and messages:
   - `GET /inbox/threads?limit=20&offset=0`
   - `GET /inbox/threads/{id}/messages?limit=50&offset=0`
3. Generate structured reply suggestion and save an outbound draft:
   - `POST /inbox/threads/{id}/suggest-reply`
   - `POST /inbox/threads/{id}/draft-reply`
4. Convert thread to lead and run scoring/routing:
   - `POST /leads/from-thread/{thread_id}`
   - `POST /leads/{id}/score`
   - `POST /leads/{id}/route`
5. Suggest and apply nurture tasks:
   - `POST /leads/{id}/nurture/suggest`
   - `POST /leads/{id}/nurture/apply`
6. Manage SLA response windows:
   - `GET /sla/config`
   - `POST /sla/config`
7. Minimal UI pages:
   - `/inbox`, `/leads`, `/settings/sla`

## Phase 8 usage (Deployment readiness + ops controls)

1. Configure environment profile:
   - `APP_ENV=development|staging|production`
   - use `.env.staging.example` or `.env.production.example` for non-dev
2. Manage org kill switches:
   - `GET /ops/settings`
   - `PATCH /ops/settings`
3. Onboarding flow:
   - `POST /onboarding/start`
   - `GET /onboarding/status`
   - `POST /onboarding/step/{step_id}/complete`
4. Staging smoke/deploy checks:
   - `make smoke` or `pnpm smoke`
   - `pnpm deploy-check`
5. Operations runbook:
   - `docs/operations.md`

## Troubleshooting

- If preflight fails on env vars, ensure `.env` includes all keys in `.env.schema.json`.
- If docker health fails, run `docker compose ps` and inspect failing service logs.
- If Playwright fails in CI, run `pnpm --filter @omniflow/web test:e2e -- --trace=on`.

## E2E Verified Flows

- Onboarding (`/onboarding`): start session + complete steps
- Campaign/Content/Publish (`/campaigns`, `/content`, `/publish/jobs`): plan -> generate -> approve -> schedule -> publish status transitions
- Inbox/Leads (`/inbox`, `/leads`): ingest -> suggest/draft reply -> create lead -> score/route/nurture
- Presence/SEO/Reputation (`/presence`, `/seo`, `/reputation`): audits, work-item lifecycle, review-response draft
- Governance/Admin (`/audit`, `/events`, `/billing`, `/automations/agents`): action traceability and controls
- Connector diagnostics (`/settings/integrations`): mode, env checklist, account health summary

### Local Demo Runbook

1. `docker compose up -d --build`
2. `pnpm run migrate`
3. `make seed-demo` (or `ALLOW_QA_SEED=true pnpm run seed:demo`)
4. Optional clean reset: `make reset-demo` (or `ALLOW_QA_RESET=true ALLOW_QA_SEED=true pnpm run reset:demo`)
5. Optional deterministic simulator tick: `DEMO_SIMULATOR=true DEMO_SIM_SEED=1234 make simulator-demo-tick`
6. E2E run: `pnpm --filter @omniflow/web test:e2e`

### Live Connector Enablement (Safe Minimum)

1. Keep defaults in mock unless checklist is green.
2. In `/settings/integrations`, review Connector Diagnostics env checklist.
3. Required live env vars: `META_APP_ID`, `META_APP_SECRET`, `LINKEDIN_CLIENT_ID`, `LINKEDIN_CLIENT_SECRET`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `OAUTH_REDIRECT_URI`, `TOKEN_ENCRYPTION_KEY`.
4. Switch connector mode to `live` only after env requirements are present and use sandbox/test accounts.

## Run Demo Locally

1. `docker compose up -d --build`
2. `make migrate`
3. `ALLOW_QA_SEED=true make seed-demo`
4. Optional live mock activity:
   - `DEMO_SIMULATOR=true DEMO_SIM_SEED=1234 make simulator-demo-tick`
5. Smoke check:
   - `make smoke`

## E2E Verified Flows

The mock-mode MVP is verified for:

- readiness and health checks
- campaign plan -> content draft -> approval -> schedule publish
- inbox, leads, presence, SEO, reputation, analytics, audit, billing, agents
- preview demo org switching

To run the web E2E suite:

1. Ensure the stack is up and seeded.
2. Run `pnpm run test-e2e`

For Render staging and production deployment steps, see `docs/render-deploy.md`.
