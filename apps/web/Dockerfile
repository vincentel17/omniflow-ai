FROM node:20.18.0-alpine AS base
WORKDIR /app
RUN corepack enable && corepack prepare pnpm@9.12.2 --activate

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/package.json
RUN pnpm install --frozen-lockfile

FROM base AS builder
ENV NEXT_OUTPUT_STANDALONE=1
COPY . .
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
RUN pnpm --filter @omniflow/web build
RUN set -eux; \
  dist_dir="$(ls -dt apps/web/.next-build-* | grep -v '\-ci$' | head -n1)"; \
  mkdir -p /tmp/web-standalone/.next; \
  cp -R "$dist_dir/standalone/." /tmp/web-standalone/; \
  cp -R "$dist_dir/static" /tmp/web-standalone/.next/static; \
  if [ -d apps/web/public ]; then cp -R apps/web/public /tmp/web-standalone/public; fi

FROM node:20.18.0-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup -S nextjs && adduser -S nextjs -G nextjs
COPY --from=builder --chown=nextjs:nextjs /tmp/web-standalone ./
USER nextjs
EXPOSE 3000
CMD ["node","apps/web/server.js"]
