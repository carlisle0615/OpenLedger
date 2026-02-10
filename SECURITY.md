# Security Policy

OpenLedger is a local-first tool that processes highly sensitive personal
financial data (PDF/CSV/XLSX exports, derived outputs, logs).

## Supported Versions

Security fixes are provided on the latest `main` branch only.

## Reporting a Vulnerability

Please report vulnerabilities privately:
- Preferred: use GitHub Security Advisories ("Report a vulnerability") if the
  repository has it enabled.
- If private reporting is not available, open an issue without sensitive
  details and ask maintainers to contact you privately.

Do not include secrets, personal data, or exported statements in public issues.

## Sensitive Data Hygiene

- Never commit `.env`, bills, run artifacts, logs, exported statements, or
  anything containing personal information.
- Rotate any leaked API keys immediately.

