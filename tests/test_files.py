import unittest

from openledger.files import safe_filename


class TestSafeFilename(unittest.TestCase):
    def test_drops_path_components(self) -> None:
        self.assertEqual(safe_filename("../a/b/c.pdf"), "c.pdf")

    def test_rejects_dot_names(self) -> None:
        self.assertEqual(safe_filename("."), "upload.bin")
        self.assertEqual(safe_filename(".."), "upload.bin")

    def test_strips_nulls_and_unsafe_chars(self) -> None:
        self.assertEqual(safe_filename("a\x00b?.csv"), "ab_.csv")

