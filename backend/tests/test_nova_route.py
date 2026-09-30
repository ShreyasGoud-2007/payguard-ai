import os
import unittest
from unittest.mock import patch

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_KEY", "test-key")

from fastapi.testclient import TestClient
from pydantic import SecretStr

from app import main
from app.config import settings
from app.routes import nova as nova_route


class EmptyNova:
    def list_vendors(self):
        return []

    def list_purchase_orders(self):
        return []

    def list_goods_receipts(self):
        return []

    def list_purchase_bills(self):
        return []

    def list_approvals(self, **_filters):
        return []

    def close(self):
        pass


class EmptySupabase:
    def table(self, _name):
        raise AssertionError("Dry-run route must not write to Supabase")


class NovaRouteTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.previous_token = settings.payguard_sync_token

    def tearDown(self):
        settings.payguard_sync_token = self.previous_token

    def test_sync_is_disabled_without_a_configured_token(self):
        settings.payguard_sync_token = None
        response = self.client.post("/api/admin/nova/sync", json={"dry_run": True})
        self.assertEqual(response.status_code, 503)

    def test_invalid_sync_token_is_rejected(self):
        settings.payguard_sync_token = SecretStr("internal-test-token")
        response = self.client.post(
            "/api/admin/nova/sync",
            json={"dry_run": True},
            headers={"X-Sync-Token": "wrong-token"},
        )
        self.assertEqual(response.status_code, 401)

    def test_authorized_dry_run_does_not_write_to_supabase(self):
        settings.payguard_sync_token = SecretStr("internal-test-token")
        with (
            patch.object(nova_route, "create_nova_client", return_value=EmptyNova()),
            patch.object(nova_route, "supabase", EmptySupabase()),
        ):
            response = self.client.post(
                "/api/admin/nova/sync",
                json={"dry_run": True},
                headers={"X-Sync-Token": "internal-test-token"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(response.json()["dry_run"])
        self.assertEqual(response.json()["counts"]["purchase_bills"], 0)


if __name__ == "__main__":
    unittest.main()
