FROM node:20-alpine AS deps
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci

FROM node:20-alpine AS build
WORKDIR /app
# NEXT_PUBLIC_* values are baked into the browser bundle at build time, so they are build arguments.
# Add further NEXT_PUBLIC_LEGAL_* values the same way (see .env.local.example).
ARG NEXT_PUBLIC_API_BASE_URL
ARG NEXT_PUBLIC_SITE_URL
ARG NEXT_PUBLIC_MAPTILER_KEY
ARG NEXT_PUBLIC_LEGAL_STATUS=draft
ARG NEXT_PUBLIC_LEGAL_VERSION=draft-1
ENV NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL \
    NEXT_PUBLIC_SITE_URL=$NEXT_PUBLIC_SITE_URL \
    NEXT_PUBLIC_MAPTILER_KEY=$NEXT_PUBLIC_MAPTILER_KEY \
    NEXT_PUBLIC_LEGAL_STATUS=$NEXT_PUBLIC_LEGAL_STATUS \
    NEXT_PUBLIC_LEGAL_VERSION=$NEXT_PUBLIC_LEGAL_VERSION \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:20-alpine AS run
WORKDIR /app
ENV NODE_ENV=production PORT=3000 HOSTNAME=0.0.0.0 NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
USER node
EXPOSE 3000
CMD ["node", "server.js"]
