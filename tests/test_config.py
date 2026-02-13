import tempfile
import unittest
from pathlib import Path

from openledger.config import (
    global_classifier_write_path,
    resolve_global_classifier_config,
)


class TestConfigPaths(unittest.TestCase):
    def test_prefers_local_override_if_present(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "config").mkdir(parents=True, exist_ok=True)
            sample = root / "config" / "classifier.sample.json"
            local = root / "config" / "classifier.local.json"
            sample.write_text("{}", encoding="utf-8")
            local.write_text("{}", encoding="utf-8")
            self.assertEqual(resolve_global_classifier_config(root), local)

    def test_uses_sample_when_local_missing(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "config").mkdir(parents=True, exist_ok=True)
            sample = root / "config" / "classifier.sample.json"
            sample.write_text("{}", encoding="utf-8")
            self.assertEqual(resolve_global_classifier_config(root), sample)

    def test_write_path_is_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(
                global_classifier_write_path(root),
                root / "config" / "classifier.local.json",
            )
