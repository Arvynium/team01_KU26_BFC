# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS dependencies

WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=cache,target=/root/.npm npm ci --no-audit --no-fund --prefer-offline --fetch-retries=5 --fetch-retry-mintimeout=2000 --fetch-retry-maxtimeout=30000

FROM dependencies AS builder

WORKDIR /app
COPY . .
RUN npm run build

FROM node:20-alpine AS runner

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

WORKDIR /app
COPY --from=builder --chown=node:node /app .

USER node
EXPOSE 3000
CMD ["npm", "run", "start"]
