# Standard Seed Dataset Spec (Phase 1-16 E2E QA)

## Purpose
Provide deterministic, reusable data for end-to-end QA across all major flows (API, worker, web).  
This is the first "standard" pack: realistic enough for behavior validation, small enough for fast iteration.

## Safety Profile
- No direct production writes
- Supports local/dev/staging preview only
- PII is synthetic or masked
- Connector defaults: `mock` mode unless explicitly overridden

## Dataset Identity
- Seed version: `qa-standard-v1`
- Org count: `2` primary test orgs + `1` isolation control org
- Time anchor: fixed UTC reference timestamp for deterministic scheduling assertions

## Entities and Volumes

### 1. Organizations and Settings
- `org_alpha_homecare` (pack: `home-care`)
- `org_beta_realestate` (pack: `real-estate`)
- `org_gamma_control` (pack: `generic`, used for cross-org isolation negative tests)

Per-org settings baseline:
- `enable_agents=true`
- `ai_mode=mock`
- `connector_mode=mock`
- `agent_autonomy_max_tier`:
  - alpha: `1`
  - beta: `2`
  - gamma: `0`
- `agent_max_plans_per_day=10`
- `agent_max_steps_per_plan=10`
- `agent_cooldown_minutes=0`
- `agent_schedule_enabled=true`
- `agent_schedule_hour_local=8`

### 2. Users/Roles
- `1 admin` per org
- `1 operator/member` per org
- Optional `1 read-only` user for permission negative tests

### 3. Leads
Per primary org:
- `20 NEW`
- `10 QUALIFIED`
- `10 NURTURE`
- `5 CLOSED_WON`
- `5 CLOSED_LOST`
- Include `5 stale` leads (`updated_at` older than stale threshold)

Attributes mix:
- source: manual, web, connector import
- varied tags and scores
- at least 3 leads with high-risk characteristics for approval gating scenarios

### 4. Inbox + SLA
Per primary org:
- `15 open` threads
- `10 closed` threads
- `60` messages total with mixed direction
- `3` simulated SLA breach events in last 24h (alpha)

### 5. Content + Publish
Per primary org:
- `12` content drafts (mixed channels)
- `8` scheduled publish jobs
- `2` failed publish jobs for retry/circuit-breaker paths
- provider/account references should be deterministic

### 6. Presence + SEO
Per primary org:
- `3` presence audit runs
- latest score:
  - alpha: `65` (triggers improvement logic)
  - beta: `82`
- `10` SEO work items, including `3` pending drafts

### 7. Reputation
Per primary org:
- `20` reviews total
- `4` negative unresponded reviews (alpha)
- `2` negative unresponded reviews (beta)
- include sentiment payloads

### 8. Workflows/Approvals
Per primary org:
- `5` workflow definitions (cover event + scheduled triggers)
- `10` workflow runs (mix: queued/succeeded/failed)
- `8` action runs with idempotency keys
- `4` pending approvals
- `2` approved
- `2` rejected

### 9. Agents (Phase 16)
Per primary org:
- seed default agent definitions enabled
- `6` agent runs (mix: proposed/approved/blocked/succeeded)
- plans include:
  - at least one `SCHEDULE_PUBLISH`
  - one `DRAFT_REPLY`
  - one approval-gated high-risk plan
  - one disallowed-target filtered plan

### 10. Billing/Compliance/Optimization
Per primary org:
- active subscription row
- usage metrics for current month
- optimization settings enabled
- at least one model metadata/training event
- one retention policy for dry-run test path

## Determinism Rules
1. Fixed UUID seeds by namespace + entity index
2. Fixed created/updated timestamps relative to time anchor
3. Stable idempotency keys for workflow/agent action runs
4. Seed script must be re-runnable (`upsert`, not duplicate)

## QA Scenarios Unlocked by This Dataset
1. Cross-org isolation checks (alpha user cannot access gamma artifacts)
2. Agent plan generation + approval gating + execution
3. Inbox/SLA triggered automation behavior
4. Publish success/failure + connector guardrails
5. Presence/SEO/Reputation feedback loops
6. Workflow idempotency and retries
7. Billing/compliance state transitions

## Acceptance Criteria for Seed Pack
1. Seed command exits `0`
2. Re-running seed command is idempotent (no duplicate growth)
3. Entity counts match expected envelope within +/-0 for fixed entities
4. Smoke checks validate critical join integrity
5. Data cleanup command can remove all `qa-standard-v1` artifacts safely

## Minimal Implementation Plan
1. Add seed loader entrypoint: `scripts/seed/qa_standard.py`
2. Add environment-safe guard (`ALLOW_QA_SEED=true`)
3. Add `make seed-standard` or `pnpm qa:seed:standard` wrapper
4. Add `scripts/qa/smoke_standard.py` for count/integrity assertions
5. Add `make qa-standard` to run seed + smoke + targeted E2E pack

## Live-Data Path (Later, Safe)
After `qa-standard-v1` is stable:
1. Add `masked-prod-like` import profile
2. Run in shadow mode (read/ingest enabled, mutating actions blocked)
3. Promote specific scenarios to canary write mode with strict approvals
