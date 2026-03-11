# API Integration Report

## Contract Audit Scope
Reviewed key web pages and action components against backend router decorators for:
- campaigns/content/publish
- inbox/leads
- presence/seo/reputation
- analytics/audit/billing
- onboarding/auth/connectors diagnostics

## Verified Matches
- Campaigns: `/campaigns`, `/campaigns/plan`, `/campaigns/{id}/generate-content`, `/campaigns/{id}/approve`.
- Content: `/content`, `/content/{id}/approve`, `/content/{id}/schedule`.
- Inbox/Leads: thread/message/reply/draft/lead-create/score/route/nurture endpoints align.
- Presence/SEO/Reputation/Billing/Audit/Analytics endpoint families align with web usage.
- Error contract: API includes `X-Request-Id` and JSON `request_id` on HTTP/validation errors.

## Gaps Found
- Login org choice lacked discoverable contract endpoint.

## Fixes Applied
- Added `POST /auth/org-options` (credential-validated) returning org list + role for sign-in selection.
- Wired auth UI to consume endpoint and populate org dropdown.

## Tenancy/RBAC Notes
- Session cookie carries org/user/role context.
- Membership checks enforce org scope in auth session creation and org-specific operations.
- Additional RBAC deep-walk (Admin/Manager/Viewer) should still run in staging for privileged write paths.
