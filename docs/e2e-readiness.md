# E2E Readiness Checklist (Truth Pass)

This checklist is the execution baseline to verify end-to-end behavior in mock-safe mode (`CONNECTOR_MODE=mock`, `AI_MODE=mock`, `ADS_MODE=mock`).

## Preconditions
1. Start stack: `docker compose up -d --build`
2. Migrate DB: `make migrate` (or `pnpm run migrate`)
3. Seed deterministic demo data: `make seed-demo` (or `ALLOW_QA_SEED=true pnpm run seed:demo`)
4. Optional clean reset: `make reset-demo` (or `ALLOW_QA_RESET=true ALLOW_QA_SEED=true pnpm run reset:demo`)
5. Optional simulator tick loop: `DEMO_SIMULATOR=true DEMO_SIM_SEED=1234 make simulator-demo-tick`
6. Web preview: `http://localhost:13000`

## J1 Onboarding
1. Open `/onboarding`
2. Click `Start Onboarding`
3. Complete at least one step
4. Verify progress bar and completed status update
5. Pass criteria: onboarding session persists after refresh

## J2 Campaign + Content + Publish
1. Open `/campaigns`, create or use seeded weekly plan
2. Click `Generate Content`, then `Approve`
3. Open `/content`, click `Approve` and `Schedule` on a draft
4. Open `/publish/jobs`, confirm queued/running/succeeded lifecycle (or use simulator tick)
5. Open `/analytics`, verify counters are non-zero and update after actions
6. Pass criteria: content can move from draft to published via queued job path

## J3 Inbox + Leads
1. Open `/inbox`, click `Ingest Mock`
2. Select thread, click `Suggest Reply`, then `Save Draft`
3. Click `Create Lead`
4. Open `/leads`, select lead, click `Score`, `Route`, `Apply Nurture`
5. Pass criteria: status banners update and nurture tasks appear

## J4 Presence + SEO + Reputation
1. Open `/presence`, click `Run Presence Audit`
2. Mark one finding done
3. Open `/seo`, click `Generate SEO Plan`, then `Generate` and `Approve` on a work item
4. Open `/reputation`, click `Import Mock Review`, then `Draft Response`
5. Pass criteria: each action writes visible state changes in list/status

## J5 Governance
1. Open `/audit`, verify recent actions exist
2. Open `/events`, verify emitted events for campaign/inbox/lead/reputation actions
3. Validate RBAC by using a non-admin role on restricted action (expected 403/blocked UI)
4. Validate restricted entitlement screen shows fallback/upsell state, not dead page
5. Pass criteria: critical actions are traceable in audit and events

## J6 Admin + Billing (implemented subset)
1. Open `/billing`, verify plan and subscription state visible
2. Confirm usage counters are non-zero
3. If org suspension flow is enabled in environment, suspend org and verify read-only behavior
4. Pass criteria: billing state visible and reflected in usage views

## J7 Optimization + Agents (implemented subset)
1. Open `/optimization`, verify next-best-action cards are visible
2. Open `/automations/agents`, run agent in mock
3. Open `/automations/agents/runs`, inspect run detail
4. If approval-gated run appears, approve then execute
5. Pass criteria: proposed plan and resulting run status transitions are visible

## Connector Live Readiness
1. Open `/settings/integrations`
2. Verify connector diagnostics panel shows mode, env checklist, and account health signals
3. If live env vars are present, switch mode to `live` and connect at least one provider in sandbox scope
4. If live env vars are missing, keep mock mode and verify diagnostics explain missing requirements

## Repro Notes
- Seed pack identity: `qa-standard-v1`
- Demo simulator controls:
  - `DEMO_SIMULATOR=true`
  - `DEMO_SIM_SEED=1234`
- Keep tenant headers aligned with seeded org/user ids in `.env`.

## Current Pass/Fail Snapshot (2026-03-05)
- Seed reset + seed + smoke: `PASS`
- Demo simulator tick: `PASS`
- Truth-pass Playwright execution (`tests/e2e/truth-pass.spec.ts`): `PASS`
- Full gate (`pnpm run release-check` under pinned Node `20.18.0`): `PASS`

## Seed Expectations
- Demo orgs: `OmniFlow Generic Demo`, `OmniFlow Real Estate Demo`, `OmniFlow Home Care Demo`
- Seed includes campaigns, drafts, publish jobs, inbox threads, leads, presence findings, SEO tasks, reviews, audit rows, and events.
- `DEMO_SEED=1234` / `DEMO_SIM_SEED=1234` are the deterministic defaults for ordering and simulator behavior.

## Troubleshooting
- If the shell blocks at preflight, verify Node matches `.node-version` (`20.18.0`).
- If API integration tests fail on database connectivity, confirm Postgres/Redis ports from `docker compose ps`.
- If the UI looks empty after a rebuild, rerun `make seed-demo` and then one simulator tick.
- If Playwright shows sparse data after route interception changes, rerun `make reset-demo`, `make seed-demo`, then `DEMO_SIMULATOR=true DEMO_SIM_SEED=1234 make simulator-demo-tick`.
