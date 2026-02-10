import os
import unittest
from contextlib import contextmanager

from openledger.settings import load_settings


@contextmanager
def temp_environ(update: dict[str, str | None]):
    old = dict(os.environ)
    try:
        for k, v in update.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        os.environ.clear()
        os.environ.update(old)


class TestSettings(unittest.TestCase):
    def test_legacy_env_vars_still_work(self) -> None:
        with temp_environ(
            {
                "OPENLEDGER_HOST": None,
                "AUTO_ACCOUNTING_HOST": "0.0.0.0",
                "OPENLEDGER_PORT": None,
                "AUTO_ACCOUNTING_PORT": "9999",
            }
        ):
            s = load_settings()
            self.assertEqual(s.host, "0.0.0.0")
            self.assertEqual(s.port, 9999)

    def test_max_upload_mb_default(self) -> None:
        with temp_environ({"OPENLEDGER_MAX_UPLOAD_MB": None}):
            s = load_settings()
            self.assertGreaterEqual(s.max_upload_bytes, 1)

