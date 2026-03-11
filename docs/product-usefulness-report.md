# Product Usefulness Report

## What Works Well
- Core console navigation routes render without 404/runtime shell failures (critical route Playwright pass).
- Mock-mode journeys are end-to-end clickable and complete for onboarding, campaigns/content/publish, inbox/leads, presence/SEO/reputation, analytics/audit, billing, agents, and diagnostics.
- API request errors include `request_id` via middleware/handlers, improving supportability.
- Connector diagnostics clearly expose mode/readiness and env presence without leaking secret values.

## What Prevents Full Usefulness
- Org selection at sign-in was previously manual UUID entry; this was a high-friction blocker for multi-org users.
- Production password-reset completion depends on external delivery (email/SMS); without delivery integration, users cannot complete reset from production UI.
- Some E2E coverage relies on mocked API routes, so contract drift can be masked unless full non-mocked checks are run regularly.

## Fix Now vs Later
### Critical (Fix Now)
- Deliver usable org-selection at login with account-scoped org discovery.
- Keep route-render and auth regression checks in release gate.

### Important (Next)
- Implement/reset-token delivery integration for production password reset.
- Add non-mocked staging API contract smoke to complement mocked UI E2E.

### Polish (Later)
- Improve explanatory helper copy for live connector gating and failed actions.

## Priority Ranking
- Critical: org selection usability, contract verification hygiene.
- Important: password reset delivery, staging contract smoke.
- Polish: microcopy improvements.
