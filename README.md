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

## Troubleshooting

- If preflight fails on env vars, ensure `.env` includes all keys in `.env.schema.json`.
- If docker health fails, run `docker compose ps` and inspect failing service logs.
- If Playwright fails in CI, run `pnpm --filter @omniflow/web test:e2e -- --trace=on`.
