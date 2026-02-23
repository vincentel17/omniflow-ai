# Architecture (Phase 0)

OmniFlow AI is organized as a pnpm workspace monorepo with three deployable apps (`web`, `api`, `worker`) and shared packages for schemas, policies, connectors, events, and vertical packs.

Core runtime topology for local development:

- Web (`Next.js`) -> API (`FastAPI`)
- API -> Postgres (`pgvector`) + Redis
- Worker (`Celery`) -> Redis + Postgres

Phase 0 establishes SDLC gates, deterministic tooling, and CI release checks before product feature development.
