# Architecture

OpenLedger is a **local-first** accounting workflow system.
It does not call any bank/payment provider APIs directly; it processes user-exported files
(`PDF/CSV/XLSX`) locally and generates reproducible artifacts under `runs/`.

## Project Architecture (Technical)

### Frontend

- `web/`: React + TypeScript + Vite UI.
- Main entry: `web/src/App.tsx`.
- View-level structure:
  - `workspace`: run creation/upload/workflow/review/preview
  - `profiles`: user-period management and period review analytics
  - `capabilities`: source support matrix + parser health
  - `config`: visual configuration center for classifier config

### Backend

- `openledger/server.py`: FastAPI service (typed request/response models via Pydantic).
- `openledger/workflow.py`: run orchestration and stage execution.
- `openledger/profiles.py`: profile/bill/run-binding domain logic (SQLite-backed).
- `openledger/profile_review.py`: real-time period review aggregation and anomaly detection.
- `openledger/capabilities.py`: source support and parser health aggregation.

### Stages

- `stages/`: executable stage modules (Python + Node.js).
- Pipeline order:
  1. `extract_pdf`
  2. `extract_exports`
  3. `match_credit_card`
  4. `match_bank`
  5. `build_unified`
  6. `classify`
  7. `finalize`

### Storage Model (SSOT)

- **Run state and artifacts (file-as-state)**:
  - `runs/<run_id>/state.json`
  - `runs/<run_id>/inputs/`
  - `runs/<run_id>/output/`
  - `runs/<run_id>/logs/`
  - `runs/<run_id>/config/`
- **Profile and archive ownership (SQLite SSOT)**:
  - DB file: `profiles.db` (or `OPENLEDGER_PROFILES_DB_PATH`)
  - Tables: `profiles`, `bills`, `run_bindings`
  - Ownership/binding semantics are resolved by DB, not frontend transient state.

## Functional Architecture (Business)

### 1) Workspace (Main flow)

- Create/select run.
- Upload statements/export files.
- Execute or cancel workflow stages.
- Preview artifacts/logs.
- Review `review.csv` and finalize outputs.

### 2) Profiles (User domain)

- **Period Management**:
  - bind run to profile
  - manually archive run with optional year/month
  - re-import and delete archived periods
  - integrity check
- **Period Review**:
  - KPI cards
  - category donut chart
  - monthly trend with MoM/YoY
  - yearly summary
  - anomaly list + integrity issue panel

### 3) Capabilities

- Data source support matrix (what files are supported).
- PDF parser health status and smoke checks.

### 4) Config Center

- Visual editor for global classifier configuration.
- Edits are written to `config/classifier.local.json` by default.

## Execution Model (Runs)

Each run is isolated and reproducible. The backend orchestrates stage commands and writes stage logs.
Workflow status is tracked in `runs/<run_id>/state.json`.

## Classifier Config Layering

Priority (high -> low):

1. `runs/<run_id>/config/classifier.json` (per-run override)
2. `config/classifier.local.json` (local global override; gitignored)
3. `config/classifier.json` (repo default)

`lsp` inside classifier config controls provider/model/runtime parameters for LLM classification.

## Backend HTTP API (High Level)

### Run lifecycle and artifacts

- `GET /api/runs`
- `POST /api/runs`
- `GET /api/runs/{run_id}`
- `POST /api/runs/{run_id}/upload`
- `POST /api/runs/{run_id}/start`
- `POST /api/runs/{run_id}/cancel`
- `POST /api/runs/{run_id}/reset`
- `GET /api/runs/{run_id}/artifacts`
- `GET /api/runs/{run_id}/artifact`
- `GET /api/runs/{run_id}/preview`
- `GET /api/runs/{run_id}/preview/pdf/meta`
- `GET /api/runs/{run_id}/preview/pdf/page`
- `GET /api/runs/{run_id}/logs/{stage_id}`
- `GET /api/runs/{run_id}/stages/{stage_id}/io`
- `GET /api/runs/{run_id}/stats/match`

### Profiles and period archive

- `GET /api/profiles`
- `POST /api/profiles`
- `GET /api/profiles/{profile_id}`
- `PUT /api/profiles/{profile_id}`
- `GET /api/profiles/{profile_id}/check`
- `GET /api/profiles/{profile_id}/review`
- `POST /api/profiles/{profile_id}/bills`
- `POST /api/profiles/{profile_id}/bills/remove`
- `POST /api/profiles/{profile_id}/bills/reimport`
- `GET /api/runs/{run_id}/profile-binding`
- `PUT /api/runs/{run_id}/profile-binding`

### Capability and config

- `GET /api/sources/support`
- `GET /api/parsers/pdf`
- `GET /api/parsers/pdf/health`
- `GET /api/capabilities`
- `GET /api/config/classifier`
- `PUT /api/config/classifier`
- `GET /api/runs/{run_id}/config/classifier`
- `PUT /api/runs/{run_id}/config/classifier`

## Security / Privacy Boundaries

Do not commit:

- `.env` (secrets)
- bills/exports/derived artifacts (`bills/`, `output/`, `runs/`, `tmp/`)
- personal classifier overrides (`config/classifier.local.json`, `config/classifier.private.json`)
- private notes (`private/`)

Refer to `.gitignore` and `README.md` for operational guidance.
