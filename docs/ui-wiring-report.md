# UI Wiring Report

Truth-pass scope focused on end-to-end MVP wiring in mock mode. The audit looked for dead CTAs, missing routes, missing API wrappers, and silent fetch failures.

## Fixed During Truth Pass

| Route | Broken or missing element | Expected behavior | Actual before fix | Fix applied |
|---|---|---|---|---|
| `/onboarding` | Missing stable selector for start + pack step | Deterministic onboarding E2E flow | CTA existed but no stable automation hook | Added `tour-onboarding-create-org` and `tour-pack-select` test ids |
| `/campaigns` | Missing stable selector for plan + generate | Plan creation and draft generation should be scriptable | CTA existed but brittle text-only selection | Added `tour-campaign-create` and `tour-drafts-generate` |
| `/content` | Missing stable selector for approve + schedule | Draft approval/scheduling should be scriptable | CTA existed but no stable hook | Added `tour-drafts-approve` and `tour-publish-schedule` |
| `/inbox` | Missing stable selector for open thread, save draft, create lead | Inbox core journey should be scriptable | CTA existed but no stable hook | Added `tour-inbox-open-thread`, `tour-inbox-send-reply`, `tour-lead-create` |
| `/presence`, `/seo`, `/reputation` | Missing stable selectors for core CTAs | Operational flows should be scriptable | E2E had to depend on text ordering | Added `tour-presence-run`, `tour-seo-create-task`, `tour-reputation-draft-response` |
| `/audit`, `/analytics`, `/automations/agents` | Missing page-level hooks / run CTA hook | Governance/agents flows should be scriptable | No stable locator | Added `tour-audit-open`, `tour-analytics-open`, `tour-agent-run` |
| `/settings/integrations` | No dedicated diagnostics destination | Operators need explicit diagnostics page | Summary only on list page | Added `/settings/integrations/diagnostics` route and nav link |
| All API-backed pages | No consistent request-id surfaced for errors | UI and operator should be able to correlate failures | Mixed error payloads and silent generic failures | Standardized backend error JSON with `request_id` and propagated it through `apiFetch` |

## Remaining Notes

- Core journeys J1-J7 now have stable selectors and route-level fetch coverage in Playwright.
- The repo still intentionally uses mock-safe mode by default; live connector/account setup remains gated behind diagnostics and provider credentials.
- Empty-state and fallback handling already existed for most dashboard pages; truth pass standardized diagnostics and request-id handling rather than replacing all UI primitives.
