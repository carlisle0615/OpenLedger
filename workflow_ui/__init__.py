"""Compatibility shim for OpenLedger.

This project originally exposed its local workflow UI server under the
`workflow_ui` package. The backend package has since been renamed to `openledger`
to match the project name.

New code should import from `openledger.*`.
"""

