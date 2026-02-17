import tempfile
import unittest
from pathlib import Path

from openledger.server import create_app

try:
    from fastapi.testclient import TestClient
except Exception:  # pragma: no cover
    TestClient = None


class ApiV2ContractTests(unittest.TestCase):
    def test_health_and_error_envelope(self) -> None:
        if TestClient is None:
            self.skipTest("fastapi TestClient 不可用（缺少 httpx）")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = create_app(root)
            with TestClient(app) as client:
                health = client.get("/api/v2/health")
                self.assertEqual(health.status_code, 200)
                payload = health.json()
                self.assertIn("data", payload)
                self.assertIn("meta", payload)
                self.assertTrue(payload["data"]["ok"])
                self.assertTrue(payload["meta"]["request_id"])

                not_found = client.get("/api/v2/not-found")
                self.assertEqual(not_found.status_code, 404)
                error_payload = not_found.json()
                self.assertIn("error", error_payload)
                self.assertIn("request_id", error_payload)
                self.assertEqual(error_payload["error"]["code"], "not_found")

    def test_runs_profiles_and_capabilities_envelope(self) -> None:
        if TestClient is None:
            self.skipTest("fastapi TestClient 不可用（缺少 httpx）")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            app = create_app(root)
            with TestClient(app) as client:
                created = client.post("/api/v2/runs", json={"name": "demo"})
                self.assertEqual(created.status_code, 200)
                run_state = created.json()["data"]
                run_id = str(run_state["run_id"])
                self.assertTrue(run_id)
                self.assertEqual(run_state["name"], "demo")

                runs = client.get("/api/v2/runs")
                self.assertEqual(runs.status_code, 200)
                runs_payload = runs.json()["data"]
                self.assertIn(run_id, runs_payload["runs"])

                options = client.put(
                    f"/api/v2/runs/{run_id}/options",
                    json={
                        "classify_mode": "dry_run",
                        "period_mode": "billing",
                        "period_day": 20,
                        "period_year": 2026,
                        "period_month": 1,
                    },
                )
                self.assertEqual(options.status_code, 200)
                self.assertTrue(options.json()["data"]["ok"])

                legacy_options = client.put(
                    f"/api/v2/runs/{run_id}/options",
                    json={"profile_id": "legacy_should_fail"},
                )
                self.assertEqual(legacy_options.status_code, 422)
                legacy_payload = legacy_options.json()
                self.assertEqual(legacy_payload["error"]["code"], "validation_error")

                created_profile = client.post("/api/v2/profiles", json={"name": "Alice"})
                self.assertEqual(created_profile.status_code, 200)
                profile_id = str(created_profile.json()["data"]["id"])
                self.assertTrue(profile_id)

                bind = client.put(
                    f"/api/v2/runs/{run_id}/profile-binding",
                    json={"profile_id": profile_id},
                )
                self.assertEqual(bind.status_code, 200)
                self.assertTrue(bind.json()["data"]["ok"])

                binding = client.get(f"/api/v2/runs/{run_id}/profile-binding")
                self.assertEqual(binding.status_code, 200)
                binding_payload = binding.json()["data"]["binding"]
                self.assertEqual(binding_payload["profile_id"], profile_id)

                capabilities = client.get("/api/v2/capabilities")
                self.assertEqual(capabilities.status_code, 200)
                cap_payload = capabilities.json()["data"]
                self.assertIn("generated_at", cap_payload)
                self.assertIn("source_support_matrix", cap_payload)
                self.assertIn("pdf_parser_health", cap_payload)


if __name__ == "__main__":
    unittest.main()
