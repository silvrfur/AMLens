# AMLens frontend. Build from this folder:  docker build -t amlens-frontend frontend
# One image for every environment: service URLs are runtime settings of the
# server-side proxy (AMLENS_BACKEND_URL, AMLENS_RAG_URL, AMLENS_PROXY_KEY), not build args.
FROM node:20-alpine AS base
WORKDIR /app
RUN corepack enable

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS builder
ENV NEXT_TELEMETRY_DISABLED=1
# The only value baked into the browser bundle. Live services by default; pass
# --build-arg NEXT_PUBLIC_USE_MOCKS=true for a self-contained demo image.
ARG NEXT_PUBLIC_USE_MOCKS=false
ENV NEXT_PUBLIC_USE_MOCKS=$NEXT_PUBLIC_USE_MOCKS
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN pnpm build

FROM node:20-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/public ./public
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static
USER nextjs
EXPOSE 3000
ENV PORT=3000 HOSTNAME=0.0.0.0
CMD ["node", "server.js"]
