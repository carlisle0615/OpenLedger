import tempfile
import unittest
from pathlib import Path

from openledger.state import resolve_under_root


class TestResolveUnderRoot(unittest.TestCase):
    def test_resolve_ok(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            p = resolve_under_root(root, "a/b/c.txt")
            # Use Path semantics instead of string-prefix to avoid macOS /var vs /private/var.
            p.relative_to(root.resolve())

    def test_resolve_rejects_escape(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            with self.assertRaises(ValueError):
                resolve_under_root(root, "../escape.txt")
