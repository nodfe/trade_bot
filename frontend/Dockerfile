FROM node:20-alpine AS base
RUN corepack enable && corepack prepare pnpm@9.15.0 --activate
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml turbo.json ./
COPY apps/admin/package.json ./apps/admin/package.json
COPY packages/ui/package.json ./packages/ui/package.json
COPY packages/charts/package.json ./packages/charts/package.json
COPY packages/api-client/package.json ./packages/api-client/package.json
COPY packages/hooks/package.json ./packages/hooks/package.json
COPY packages/tsconfig/package.json ./packages/tsconfig/package.json
RUN pnpm install --frozen-lockfile

FROM base AS builder
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/admin/node_modules ./apps/admin/node_modules
COPY --from=deps /app/packages ./packages
COPY . .
RUN pnpm build --filter=@quant/admin

FROM base AS runner
ENV NODE_ENV=production
RUN addgroup --system --gid 1001 nodejs && adduser --system --uid 1001 nextjs
COPY --from=builder /app/apps/admin/public ./apps/admin/public
COPY --from=builder --chown=nextjs:nodejs /app/apps/admin/.next/standalone ./
COPY --from=builder --chown=nextjs:nodejs /app/apps/admin/.next/static ./apps/admin/.next/static
USER nextjs
EXPOSE 5001
ENV PORT=5001
ENV HOSTNAME="0.0.0.0"
CMD ["node", "apps/admin/server.js"]
