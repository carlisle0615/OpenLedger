from __future__ import annotations

from pathlib import Path

from openledger.api.app import create_app, main, serve

__all__ = ["create_app", "main", "serve"]


if __name__ == "__main__":
    main()
