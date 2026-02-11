#!/usr/bin/env bash
set -euo pipefail

python /app/main.py &
BACKEND_PID=$!

caddy run --config /etc/caddy/Caddyfile --adapter caddyfile &
CADDY_PID=$!

cleanup() {
  kill -TERM "$BACKEND_PID" "$CADDY_PID" 2>/dev/null || true
  wait "$BACKEND_PID" "$CADDY_PID" 2>/dev/null || true
}

trap cleanup SIGINT SIGTERM

wait -n "$BACKEND_PID" "$CADDY_PID"
cleanup
