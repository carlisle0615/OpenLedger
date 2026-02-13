# OpenLedger Open Source Checklist

This checklist is for preparing the repository for public open source release.

## Must-Do Before Going Public

- [ ] Rotate any leaked secrets immediately (API keys, tokens).
- [ ] Remove secrets from git history (not just from the working tree).
- [ ] Ensure no personal data is committed (bills, outputs, logs, screenshots, chat logs).
- [ ] Add/verify project license (`LICENSE`).
- [ ] Add contribution docs (`CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, `SECURITY.md`).
- [ ] Add CI to prevent obvious breakage (`.github/workflows/ci.yml`).
- [ ] Provide safe defaults:
  - Public template: `config/classifier.sample.json`
  - Local override (ignored): `config/classifier.local.json`
  - Secrets template: `.env.example` (keep `.env` ignored)

## Recommended Repo Hygiene

- [ ] Add issue templates and PR template under `.github/`.
- [ ] Add `CHANGELOG.md` and a simple release process (tags + notes).
- [ ] Add formatting/linting (Python + web) and keep it enforced in CI.
- [ ] Document privacy model clearly in `README.md` (local-first, sensitive files).
- [ ] Add a short "architecture / workflow" doc under `docs/`.

## History Rewrite (Secret Removal)

If a secret was ever committed (e.g. a real API key in `.env`), removing the file
in a new commit is not enough. You must rotate the secret and rewrite history.

Typical approach:
1. Rotate the key in the provider dashboard.
2. Rewrite git history to remove the secret file/content.
3. Force-push and ask all collaborators to re-clone.

Tools:
- `git filter-repo` (recommended) or BFG Repo-Cleaner.

Note: If the repo was already public, assume the secret is compromised even
after rewriting history.
