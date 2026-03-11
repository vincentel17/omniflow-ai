# Staging Readiness Report

## Ready
- Critical UI routes render without generic runtime failure shell.
- Core mock-mode user journeys are executable end-to-end.
- Auth now supports credential register/login/reset plus org option discovery.
- API error correlation via request IDs is in place.

## Must-Verify Before Real Live Usage
- Live env consistency between web and api (`NEXT_PUBLIC_*` vs API runtime vars).
- No `PLAYWRIGHT*` variables in production runtime context.
- Connector live prerequisites (OAuth redirect URIs, provider creds, encryption keys) verified in diagnostics.
- Worker throughput/retry behavior under non-mock staging traffic.

## Safety Gates
- Default modes remain mock until connector diagnostics and account health are green.
- Keep production reset delivery dependency explicit (mail/SMS channel required).

## Recommendation
- Proceed to staging hard gate with role-walk and connector healthcheck scenarios before broad production exposure.
