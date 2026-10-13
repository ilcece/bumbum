# syntax=docker/dockerfile:1@sha256:4edf897a3ffa55b89f906fc8cc78afdb3f1834cc9c7083565e611a8a7d5fe99e
FROM scratch AS npm_cache
FROM node:24.19.0-bookworm-slim@sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN --mount=type=secret,id=build_ca --mount=type=bind,from=npm_cache,target=/offline-cache \
    if [ -f /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    if [ -d /offline-cache/_cacache ]; then mkdir -p /tmp/npm-cache; cp -a /offline-cache/_cacache /tmp/npm-cache/; npm ci --offline --cache /tmp/npm-cache; else npm ci --cache /tmp/npm-cache; fi
COPY tsconfig.json ./
COPY src ./src
RUN npm run build && npm prune --omit=dev --offline --cache /tmp/npm-cache
FROM node:24.19.0-bookworm-slim@sha256:a9f5f7c91a432850b2a8a7797adf5eadb6c733ceed61167806cee7ea7fbc29df
ENV NODE_ENV=production PORT=3000
WORKDIR /app
COPY --from=build --chown=node:node /app/node_modules ./node_modules
COPY --from=build --chown=node:node /app/dist ./dist
COPY --chown=node:node package.json package-lock.json ./
COPY --chown=node:node public ./public
COPY --chown=node:node migrations ./migrations
USER node
EXPOSE 3000
CMD ["node","dist/server.js"]
