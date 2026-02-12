import unittest

from openledger.capabilities import (
    get_capabilities_payload,
    get_pdf_parser_health,
    list_source_support_matrix,
)


class TestSourceSupportMatrix(unittest.TestCase):
    def test_contains_core_sources(self) -> None:
        items = list_source_support_matrix()
        ids = {x["id"] for x in items}
        self.assertIn("wechat_xlsx", ids)
        self.assertIn("alipay_csv", ids)
        self.assertIn("cmb_credit_card_pdf", ids)
        self.assertIn("cmb_statement_pdf", ids)


class TestPdfParserHealth(unittest.TestCase):
    def test_cmb_parser_health(self) -> None:
        payload = get_pdf_parser_health()
        self.assertIn("summary", payload)
        self.assertIn("parsers", payload)
        parsers = payload["parsers"]
        cmb = next((x for x in parsers if x["mode_id"] == "cmb"), None)
        self.assertIsNotNone(cmb)
        assert cmb is not None
        self.assertIn(cmb["status"], {"ok", "warning", "error"})
        self.assertIn("cmb_credit_card", cmb["kinds"])
        self.assertIn("cmb_statement", cmb["kinds"])
        self.assertGreaterEqual(len(cmb["sample_checks"]), 1)


class TestCapabilitiesPayload(unittest.TestCase):
    def test_payload_shape(self) -> None:
        payload = get_capabilities_payload()
        self.assertIn("generated_at", payload)
        self.assertIn("source_support_matrix", payload)
        self.assertIn("pdf_parser_health", payload)
        self.assertIsInstance(payload["source_support_matrix"], list)
        self.assertIsInstance(payload["pdf_parser_health"], dict)

