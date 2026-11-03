# Production image for the Next.js site. NEXT_PUBLIC_* values are compiled into the bundle,
# so pass them as build args: docker build --build-arg NEXT_PUBLIC_SITE_URL=https://... frontend/
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:22-alpine AS build
WORKDIR /app
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_MAPTILER_KEY=""
ARG NEXT_PUBLIC_REFERRAL_WINDOW_DAYS=60
ARG NEXT_PUBLIC_LEGAL_STATUS=draft
ARG NEXT_PUBLIC_LEGAL_VERSION=draft-1
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_MAPTILER_KEY=$NEXT_PUBLIC_MAPTILER_KEY NEXT_PUBLIC_REFERRAL_WINDOW_DAYS=$NEXT_PUBLIC_REFERRAL_WINDOW_DAYS \
    NEXT_PUBLIC_LEGAL_STATUS=$NEXT_PUBLIC_LEGAL_STATUS NEXT_PUBLIC_LEGAL_VERSION=$NEXT_PUBLIC_LEGAL_VERSION
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN addgroup -S app && adduser -S app -G app -u 10001
COPY --from=build --chown=app:app /app/.next/standalone ./
COPY --from=build --chown=app:app /app/.next/static ./.next/static
USER app
EXPOSE 3000
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD wget -qO- http://127.0.0.1:3000/robots.txt >/dev/null || exit 1
CMD ["node", "server.js"]
