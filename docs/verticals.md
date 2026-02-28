# Verticals v2

Phase 15 introduces a manifest-driven vertical pack contract under `packages/verticals/<slug>/`.

## Required files

- `manifest.json`
- `pipelines.json`
- `scoring.json`
- `seo_archetypes.json`
- `workflows.runtime.json`
- `policy.rules.yaml`
- `optimization_config.json`
- `entitlement_overrides.json`

Packs are validated at load/activation time. Invalid packs are rejected.

## API

- `GET /verticals/available`
- `GET /verticals/{slug}/manifest`
- `POST /verticals/select`
- `GET /admin/verticals`
- `GET /admin/vertical-performance`

## Scaffolding

Create a pack scaffold:

`python scripts/create-vertical-pack.py <slug>`

Validate a pack:

`python scripts/validate-pack.py <slug>`

Or through make:

- `make create-vertical-pack slug=<slug>`
- `make validate-pack slug=<slug>`

## Monetization guardrails

Pack activation is plan-gated using `SubscriptionPlan.allowed_verticals_json`.
Blocked activations emit `PACK_ACTIVATION_BLOCKED` and are audited.
