# syntax=docker/dockerfile:1.6

FROM node:20-slim AS frontend
WORKDIR /app/web
COPY web/package.json web/pnpm-lock.yaml ./
RUN corepack enable && pnpm install --frozen-lockfile
COPY web/ .
RUN pnpm build

FROM python:3.13-slim AS backend
WORKDIR /app
COPY pyproject.toml uv.lock ./
COPY openledger/ openledger/
COPY stages/ stages/
COPY tools/ tools/
COPY config/ config/
COPY main.py ./
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir uv \
    && uv sync --locked --no-dev

FROM caddy:2.7.6 AS caddy

FROM python:3.13-slim
ENV PATH="/app/.venv/bin:$PATH" \
    OPENLEDGER_HOST=0.0.0.0 \
    OPENLEDGER_PORT=8000 \
    OPENLEDGER_OPEN_BROWSER=false

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends poppler-utils ca-certificates \
    && rm -rf /var/lib/apt/lists/*

COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
COPY --from=backend /app /app
COPY --from=frontend /app/web/dist /app/web/dist
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/Caddyfile /etc/caddy/Caddyfile
RUN chmod +x /entrypoint.sh

EXPOSE 8000 5173

ENTRYPOINT ["/entrypoint.sh"]
