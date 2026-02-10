# Contributing

Thanks for your interest in contributing to OpenLedger.

## Development Setup

Prerequisites:
- Python 3.13+
- [uv](https://github.com/astral-sh/uv)
- Node.js 20+
- pnpm (see `web/package.json` `packageManager`)

Backend (Python):
```bash
uv sync
uv run python main.py
```

Frontend (React):
```bash
cd web
pnpm install
pnpm dev
```

## Checks

Python (syntax check):
```bash
uv run python -m compileall main.py stages tools openledger tests
```

Python (unit tests):
```bash
uv run python -m unittest discover -s tests
```

Web build:
```bash
cd web
pnpm build
```

## Pull Requests

- Keep changes focused and small.
- If you change the workflow outputs or file formats, update `README.md` accordingly.
- Avoid committing any private data: `.env`, bills, run artifacts, logs, exported CSV/XLSX/PDF, etc.
