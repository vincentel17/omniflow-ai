# API Contract Report

This report documents the UI-to-API contracts currently exercised by the MVP shell. It is based on `apiFetch(...)` calls in `apps/web/app` plus the backend request/response schemas used by the corresponding routers.

## Cross-Cutting Contract Rules

- Auth/tenancy headers for local/demo mode: `X-Omniflow-User-Id`, `X-Omniflow-Org-Id`, `X-Omniflow-Role`.
- List endpoints currently use query parameters such as `?limit=50&offset=0` and generally return JSON arrays rather than envelope pagination.
- Error responses are standardized during truth pass to:
  - HTTPException -> `{ "detail": string, "request_id": string }`
  - Validation error -> `{ "detail": "Validation failed", "errors": [...], "request_id": string }`
- The backend also returns `X-Request-Id` on responses.

## Route Group Contracts

| UI Route | API Endpoint(s) | Expected JSON shape |
|---|---|---|
| `/dashboard` | `/events?limit=6&offset=0`, `/healthz` | `Event[]`; `{ status }` |
| `/campaigns` | `/campaigns?limit=50&offset=0`, `/campaigns/plan`, `/campaigns/{id}/generate-content` | `CampaignPlan[]`; `CampaignPlan`; generation summary object |
| `/content` | `/content?limit=50&offset=0`, `/content/{id}/approve`, `/content/{id}/schedule` | `ContentItem[]`; approved content item; queued publish job |
| `/publish/jobs` | `/publish/jobs?limit=50&offset=0`, `/ops/settings` | `PublishJob[]`; ops settings object |
| `/inbox` | `/inbox/threads`, `/inbox/threads/{id}/messages`, `/inbox/ingest/mock`, `/inbox/threads/{id}/suggest-reply`, `/inbox/threads/{id}/draft-reply`, `/leads/from-thread/{id}` | `Thread[]`; `Message[]`; `{ ok }`; suggestion/draft objects; lead object |
| `/leads` | `/leads`, `/leads/{id}/score`, `/leads/{id}/route`, `/leads/{id}/nurture/*`, `/optimization/next-best-action/{entity}/{id}` | `Lead[]`; scoring object; assignment object; nurture tasks/created count; next-best-action object |
| `/presence` | `/presence`, `/presence/findings`, `/presence/tasks`, `/presence/audits/run` | latest audit run; finding/task arrays; created run |
| `/seo` | `/seo/work-items`, `/seo/plan`, `/seo/work-items/{id}/generate`, `/seo/work-items/{id}/approve` | work item array; plan object; generated/approved work item |
| `/reputation` | `/reputation/reviews`, `/reputation/campaigns`, `/reputation/reviews/import`, `/reputation/reviews/{id}/draft-response` | review array; campaign array; import summary; response draft object |
| `/analytics/*` | `/analytics/overview`, `/analytics/content`, `/analytics/funnel`, `/analytics/sla`, `/analytics/presence`, `/analytics/workload` | dashboard-specific aggregate objects |
| `/settings/integrations` | `/connectors/accounts`, `/ops/settings`, `/connectors/diagnostics/summary`, `/connectors/accounts/{id}/diagnostics` | connector account array; ops settings; diagnostics summary; account diagnostics |
| `/billing` | `/billing/subscription`, `/billing/plans` | subscription object; plan array |
| `/automations/workflows` | `/workflows`, `/workflows/runs`, `/approvals` | workflow array; run array; approval array |
| `/automations/agents*` | `/agents/context`, `/agents/definitions`, `/agents/run`, `/agents/runs`, `/agents/runs/{id}`, `/agents/runs/{id}/execute` | context snapshot; agent definitions; run object(s) |
| `/optimization*` | `/optimization/models`, `/optimization/leads`, `/optimization/campaigns`, `/optimization/nurture/recommendations`, `/optimization/ads`, `/optimization/workflows`, `/optimization/next-best-action/...` | optimization aggregate arrays/objects documented in `apps/web/lib/api.ts` |

## Contract Fixes Applied in Truth Pass

- Added request-id propagation to `apps/web/lib/api.ts`.
- Added backend exception handlers in `apps/api/app/main.py` so UI/API failures carry a consistent `request_id`.
- Added integration test coverage for 404 and 422 request-id behavior.
