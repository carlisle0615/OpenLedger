import tempfile
import unittest
from pathlib import Path

from openledger.config import (
    card_alias_write_path,
    global_classifier_write_path,
    resolve_card_alias_config,
    resolve_global_classifier_config,
)


class TestConfigPaths(unittest.TestCase):
    def test_prefers_local_override_if_present(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "config").mkdir(parents=True, exist_ok=True)
            public = root / "config" / "classifier.json"
            local = root / "config" / "classifier.local.json"
            public.write_text("{}", encoding="utf-8")
            local.write_text("{}", encoding="utf-8")
            self.assertEqual(resolve_global_classifier_config(root), local)

    def test_write_path_is_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(
                global_classifier_write_path(root),
                root / "config" / "classifier.local.json",
            )

    def test_card_alias_prefers_local_override_if_present(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "config").mkdir(parents=True, exist_ok=True)
            default_cfg = root / "config" / "card_aliases.json"
            local_cfg = root / "config" / "card_aliases.local.json"
            default_cfg.write_text("{}", encoding="utf-8")
            local_cfg.write_text("{}", encoding="utf-8")
            self.assertEqual(resolve_card_alias_config(root), local_cfg)

    def test_card_alias_falls_back_to_default(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "config").mkdir(parents=True, exist_ok=True)
            default_cfg = root / "config" / "card_aliases.json"
            default_cfg.write_text("{}", encoding="utf-8")
            self.assertEqual(resolve_card_alias_config(root), default_cfg)

    def test_card_alias_write_path_is_local_override(self) -> None:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            self.assertEqual(
                card_alias_write_path(root),
                root / "config" / "card_aliases.local.json",
            )
