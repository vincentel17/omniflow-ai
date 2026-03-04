# OmniFlow Phase 1-16 Coverage Matrix (Initial QA Baseline)

## Scope Note
This matrix is an execution-focused baseline for immediate E2E QA.  
Rows are mapped from currently implemented app surface (API routers, worker jobs, web routes, and tests).  
To declare 100% "according to original plan", reconcile each row with the original phase prompt text and mark `REQ-VERIFIED`.

## Status Legend
- `GREEN`: implemented + at least one automated check exists
- `YELLOW`: implemented but missing comprehensive automated proof
- `RED`: not yet implemented or no evidence found

| Phase | Capability Area | Implementation Evidence (Current) | Automated Evidence (Current) | Status | Gap To Close |
|---|---|---|---|---|---|
| 1 | Platform/API foundation | API app boot, tenancy/context, health/org/admin routers present | Existing API tests in repo (beyond this matrix baseline) | YELLOW | Map exact phase-1 acceptance criteria to tests |
| 2 | Auth + org scoping + roles | Role checks and org-scoped query patterns used across routers | Integration behavior exists in route tests | YELLOW | Add explicit cross-org negative-path pack |
| 3 | Audit + event pipeline | Audit/event services used broadly by workflows/agents/routes | Event side-effects covered partially | YELLOW | Add event contract assertions for each critical flow |
| 4 | Leads + pipeline operations | Leads API/UI surfaces present, lead statuses and lifecycle in models | Existing app tests + UI routes compile | YELLOW | Add full lead lifecycle E2E script with assertions |
| 5 | Inbox + SLA | Inbox routes/models and SLA-related events are present | Worker/API tests partial | YELLOW | Add SLA breach simulation and response-time KPI checks |
| 6 | Content + publishing core | Content/publish routes + publish worker execution paths present | Build/lint/typecheck + job paths in worker | YELLOW | Add publish happy/failure/circuit-breaker E2E |
| 7 | Presence + SEO | Presence/SEO routes and models exist | UI routes/build validations | YELLOW | Add quality KPI assertions across presence + SEO |
| 8 | Reputation + response | Reputation models/routes and review-response flow exist | Partial automated coverage | YELLOW | Add negative-review ingestion to response E2E |
| 9 | Campaigns + analytics | Campaign/analytics routes present in app and web | Web build includes route generation | YELLOW | Add analytics data-consistency cross-checks |
| 10 | Workflows engine baseline | Workflow models/routes/worker action execution paths exist | Worker pipeline behavior tested partially | YELLOW | Add deterministic workflow replay/idempotency suite |
| 11 | Connectors + live/mock control | Connector settings and live/mock gating in services/worker | Runtime guards present | YELLOW | Add connector contract tests per provider |
| 12 | Billing/compliance/ops controls | Billing/compliance routes and org status handling in worker | Status sync/background tasks exist | YELLOW | Add suspension/reactivation end-to-end assertions |
| 13 | Optimization + model loop | Optimization routes and training/usage tasks in worker | Background task paths implemented | YELLOW | Add metric drift and model freshness assertions |
| 14 | Vertical packs + specialization | Vertical validation and pack-aware behavior present | Startup pack validation exists | YELLOW | Add per-vertical acceptance suite and fixtures |
| 15 | Approvals + governance hardening | Approval entities/routes + enforcement hooks in workflow and agents | Approval paths covered in integration | YELLOW | Add rejection/rollback and audit completeness suite |
| 16 | Agent orchestration | Agents API/router/service + worker run/execute/schedule + web pages | `test_phase16_unit`, `test_phase16_integration`, `test_phase16_worker`, `agents.spec.ts` pass | GREEN | Reconcile against original phase-16 prompt checklist line-by-line |

## Cross-Phase End-to-End Gate (Target)
To call full Phase 1-16 QA `GREEN`, require all:
1. Requirement traceability (every original prompt requirement linked to test ID)
2. Deterministic seed data loaded successfully
3. API integration pack passes
4. Worker async flow pack passes
5. Web critical-path E2E pack passes
6. Cross-org isolation/security pack passes
7. Live-safe shadow/canary pack passes (if live connectors enabled)

## Immediate Next Action
Use `docs/qa/standard-seed-dataset-spec.md` to seed deterministic data, then execute the QA runs in this order:
1. API integration
2. Worker background flow
3. Web E2E critical paths
4. Cross-service end-to-end scenarios
