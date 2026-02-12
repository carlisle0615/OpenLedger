# syntax=docker/dockerfile:1.6

ARG APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian
ARG APT_SECURITY_MIRROR=https://mirrors.tuna.tsinghua.edu.cn/debian-security
ARG NPM_REGISTRY=https://registry.npmmirror.com
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple
ARG UV_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

FROM node:20-slim AS frontend
ARG NPM_REGISTRY
ENV COREPACK_NPM_REGISTRY=${NPM_REGISTRY}
WORKDIR /app/web
COPY web/package.json web/pnpm-lock.yaml ./
RUN corepack enable \
    && pnpm config set registry "${NPM_REGISTRY}" \
    && pnpm install --frozen-lockfile
COPY web/ .
RUN pnpm build

FROM python:3.13-slim AS backend
ARG PIP_INDEX_URL
ARG UV_INDEX_URL
ENV PIP_INDEX_URL=${PIP_INDEX_URL} \
    UV_INDEX_URL=${UV_INDEX_URL}
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
ARG APT_MIRROR
ARG APT_SECURITY_MIRROR
ENV PATH="/app/.venv/bin:$PATH" \
    OPENLEDGER_HOST=0.0.0.0 \
    OPENLEDGER_PORT=8000 \
    OPENLEDGER_OPEN_BROWSER=false

WORKDIR /app

RUN set -eux; \
    sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g; s|http://deb.debian.org/debian-security|${APT_SECURITY_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    apt-get -o Acquire::Retries=5 -o Acquire::ForceIPv4=true update; \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      -o Acquire::Retries=5 -o Acquire::ForceIPv4=true \
      poppler-utils ca-certificates; \
    rm -rf /var/lib/apt/lists/*

COPY --from=caddy /usr/bin/caddy /usr/bin/caddy
COPY --from=backend /app /app
COPY --from=frontend /app/web/dist /app/web/dist
COPY docker/entrypoint.sh /entrypoint.sh
COPY docker/Caddyfile /etc/caddy/Caddyfile
RUN chmod +x /entrypoint.sh

EXPOSE 8000 5173

ENTRYPOINT ["/entrypoint.sh"]
