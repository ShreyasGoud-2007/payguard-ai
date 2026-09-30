from __future__ import annotations

import sys
import traceback
from pathlib import Path
from uuid import UUID

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.config import settings
from app.main import verify_invoice
from app.services.nova_client import NovaClient
from app.services.nova_sync import NovaSyncService


TESTS_DIR = BACKEND_DIR / "tests"
sys.path.insert(0, str(TESTS_DIR))
from test_nova_sync import FakeSupabase


def main() -> int:
    if settings.nova_api_key is None:
        print("Nova API key is not configured")
        return 2

    client = NovaClient(
        settings.nova_api_key.get_secret_value(),
        settings.nova_base_url,
        timeout_seconds=settings.nova_timeout_seconds,
        page_size=settings.nova_page_size,
        max_retries=settings.nova_max_retries,
        retry_backoff_seconds=settings.nova_retry_backoff_seconds,
    )
    database = FakeSupabase()

    try:
        sync_result = NovaSyncService(client, database).sync()
        first_counts = {
            table: len(rows)
            for table, rows in database.tables.items()
            if table != "audit_logs"
        }
        repeat_result = NovaSyncService(client, database).sync()
        repeat_counts = {
            table: len(rows)
            for table, rows in database.tables.items()
            if table != "audit_logs"
        }
        imported_audits = sum(
            row.get("action") == "BILL_IMPORTED"
            for row in database.tables.get("audit_logs", [])
        )
        if first_counts != repeat_counts or repeat_result["counts"]["new_purchase_bills"] != 0:
            print("real_nova_sync_idempotent=false")
            return 4

        candidate = next(
            (
                row for row in database.tables["invoices"]
                if row.get("po_id") and row.get("grn_id") and row.get("total_amount") is not None
            ),
            None,
        )
        if candidate is None:
            print("No source bill with both PO and GRN was available for verification")
            return 3

        import app.main as payguard_app

        payguard_app.supabase = database
        result = verify_invoice(UUID(candidate["id"]))
        print("real_nova_bill_checked=true")
        print("dry_run_database=in_memory_only")
        print("source_counts=", sync_result["counts"])
        print("second_sync_idempotent=true")
        print("second_sync_new_bills=", repeat_result["counts"]["new_purchase_bills"])
        print("bill_import_audit_events=", imported_audits)
        print("verification_status=", result["status"])
        print("verification_passed=", result["passed"])
        print("checks=", len(result["checks"]))
        print("failed_checks=", sum(check["status"] == "failed" for check in result["checks"]))
        print("warnings=", sum(check["status"] == "warning" for check in result["checks"]))
        print("issue_count=", len(result["issues"]))
        return 0
    except Exception as exc:
        print("real_nova_verification_failed_type=", type(exc).__name__)
        if isinstance(exc, AttributeError):
            print("missing_attribute=", getattr(exc, "name", None))
            print("attribute_owner_type=", type(getattr(exc, "obj", None)).__name__)
        for frame in traceback.extract_tb(exc.__traceback__):
            print("failure_location=", Path(frame.filename).name, frame.lineno, frame.name)
        return 1
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
