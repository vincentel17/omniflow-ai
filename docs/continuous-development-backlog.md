# Continuous Development Backlog

Last updated: 2026-03-11
Owner: Continuous Software Architect
Status: Active

## Current Baseline
- Repository root validated: `omniflow-ai-repo`
- Latest security/auth hardening committed and pushed on branch `chore/truth-pass-phase1-16` (`474a8bc`)
- Full gates previously green: `pnpm run check`, `pnpm run test`, `pnpm run release-check`

## Priority Queue

### CRITICAL
1. Production password reset delivery completion
- Problem: Password reset completion in production still depends on external channel implementation.
- Scope: Wire existing reset request/confirm flow to real outbound provider path (email/SMS) behind current architecture.
- Validation: Integration test for delivery handoff + E2E reset journey with production-safe toggles.

2. End-to-end journey regression guard expansion
- Problem: Core journeys pass, but route-level regressions can still slip if selectors/data drift.
- Scope: Add stable assertions for state transitions in J2/J3/J4 (draft->approved->scheduled, inbox->lead->scored->routed, presence->SEO->reputation).
- Validation: Playwright journey pack + API integration assertions remain green.

### IMPORTANT
3. Connector diagnostics truthfulness hardening
- Problem: Need stronger user-facing clarity between mock/live readiness and credential completeness.
- Scope: Tighten diagnostics payload rendering and explicit remediation messages without changing connector architecture.
- Validation: `/settings/integrations` + diagnostics E2E verifies status messaging and no dead CTAs.

4. Analytics and governance evidence completeness
- Problem: Ensure events emitted by workflows are always visible in analytics/audit surfaces.
- Scope: Fill any missing event->dashboard mapping gaps in existing pipelines.
- Validation: Integration tests asserting event emission and dashboard endpoint deltas.

5. Session UX continuity polish
- Problem: Security behavior is implemented; user continuity messaging can be clearer after timeout/logout.
- Scope: Improve minimal UX copy and post-expiry guidance on auth views.
- Validation: E2E auth-guard/logout/idle flow assertions.

### OPTIMIZATION
6. Developer runbook consolidation
- Scope: One concise runbook for local/staging gate + migration + smoke commands.
- Validation: Fresh run from clean checkout reproduces green gates.

7. Observability enrichment for background jobs
- Scope: Normalize structured fields for worker job_start/job_success/job_failure logs.
- Validation: Worker tests verify log context keys present.

## Execution Order (Strict)
1. CRITICAL #1 (password reset delivery completion)
2. CRITICAL #2 (journey regression guards)
3. IMPORTANT #3 (connector diagnostics clarity)
4. IMPORTANT #4 (analytics/audit mapping checks)
5. IMPORTANT #5 (session UX continuity)
6. OPTIMIZATION items

## Cycle Tracking
- Cycle 1 (this cycle): Establish backlog and confirm baseline gates remain green.
- Next implementation target: CRITICAL #1 with minimal-churn architecture-preserving changes.
