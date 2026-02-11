#!/usr/bin/env bash
set -euo pipefail

cd /Users/bytedance/Codes/auto-accounting/web
pnpm run build

cd /Users/bytedance/Codes/auto-accounting
uv run python main.py
