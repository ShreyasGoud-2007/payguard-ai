import json

import pytest

from paygard_ai.config import DB_PATH
from paygard_ai.database import DatabaseManager
from paygard_ai.data_import import (
    LiveDatabaseWriteDisabled,
    SourceMappingNotConfirmed,
    import_normalized_records,
)
from paygard_ai.verification import verify_invoice


def normalized_records():
    return {
        "purchase_orders": [
            {
                "po_number": "PO-NORMALIZED-1",
                "vendor": "Example vendor",
                "status": "approved",
                "quantity": "2",
                "unit_price": "3.25",
                "amount": "6.50",
                "source_record_id": "source-po-1",
                "source_provenance": {"original_key": "source-po-1", "note": "test-only canonical payload"},
            }
        ],
        "goods_receipts": [
            {
                "receipt_number": "GR-NORMALIZED-1",
                "po_number": "PO-NORMALIZED-1",
                "quantity": "2",
                "received_on": "2026-09-30",
                "line_items": [{"description": "Item", "quantity": "2"}],
                "source_record_id": "source-gr-1",
                "source_provenance": {"original_key": "source-gr-1"},
            }
        ],
    }


def test_normalized_import_preview_validates_and_preserves_provenance():
    result = import_normalized_records(normalized_records(), source="TEST")

    assert result["persisted"] is False
    assert result["imported"] == 0
    assert result["prepared"] == 2
    assert result["invalid"] == 0
    po = result["records"]["purchase_orders"][0]
    assert po["data_source"] == "TEST"
    assert po["source_record_id"] == "source-po-1"
    assert po["source_provenance"]["original_key"] == "source-po-1"
    assert po["status"] == "APPROVED"


def test_preview_with_database_does_not_write_any_records(tmp_path):
    manager = DatabaseManager(str(tmp_path / "preview-only.db"))
    manager.setup_database()
    before = manager.data_source_summary()

    result = import_normalized_records(normalized_records(), source="TEST", database=manager)

    assert result["prepared"] == 2
    assert result["imported"] == 0
    assert manager.get_purchase_order("PO-NORMALIZED-1") is None
    assert manager.data_source_summary() == before


def test_missing_fields_invalid_amount_date_and_status_are_reported():
    records = {
        "purchase_orders": [
            {"po_number": "PO-MISSING", "vendor": "Example vendor", "status": "APPROVED"},
            {
                "po_number": "PO-AMOUNT",
                "vendor": "Example vendor",
                "status": "APPROVED",
                "quantity": 2,
                "unit_price": "not-money",
                "amount": 6,
            },
            {
                "po_number": "PO-STATUS",
                "vendor": "Example vendor",
                "status": "PENDING",
                "quantity": 2,
                "unit_price": 3,
                "amount": 6,
            },
        ],
        "goods_receipts": [
            {
                "receipt_number": "GR-DATE",
                "po_number": "PO-MISSING",
                "quantity": 2,
                "received_on": "not-a-date",
            }
        ],
    }

    result = import_normalized_records(records, source="TEST")

    assert result["prepared"] == 0
    assert result["invalid"] == 4
    assert all(issue["reason"] for issue in result["issues"])


def test_duplicate_keys_within_input_batch_are_not_prepared():
    records = normalized_records()
    records["purchase_orders"].append(dict(records["purchase_orders"][0]))

    result = import_normalized_records(records, source="TEST")

    assert result["prepared"] == 2
    assert result["duplicate"] == 1


def test_unmapped_currency_is_rejected_not_discarded():
    records = normalized_records()
    records["purchase_orders"][0]["currency"] = "USD"

    result = import_normalized_records(records, source="TEST")

    assert result["prepared"] == 0
    assert result["invalid"] == 2
    assert any("currency" in issue["reason"] for issue in result["issues"])


def test_import_does_not_overwrite_a_demo_purchase_order(tmp_path):
    manager = DatabaseManager(str(tmp_path / "source-collision.db"))
    manager.setup_database()
    manager.insert_demo_data()
    records = normalized_records()
    records["purchase_orders"][0]["po_number"] = "PO500"
    records["goods_receipts"][0]["po_number"] = "PO500"

    result = import_normalized_records(records, source="TEST", database=manager, persist=True)

    assert result["imported"] == 0
    assert result["duplicate"] == 1
    assert result["skipped"] == 1
    existing = manager.get_purchase_order("PO500")
    assert existing["vendor"] == "ABC Traders"
    assert existing["amount"] == 1000
    assert existing["data_source"] == "DEMO"


def test_conflicting_source_identifier_does_not_overwrite_or_import_receipt(tmp_path):
    manager = DatabaseManager(str(tmp_path / "source-id-conflict.db"))
    manager.setup_database()
    manager.add_purchase_order({
        "po_number": "PO-EXISTING",
        "vendor": "Existing vendor",
        "quantity": 1,
        "unit_price": 2,
        "amount": 2,
        "status": "APPROVED",
        "data_source": "TEST",
        "source_record_id": "shared-source-id",
    })
    records = normalized_records()
    records["purchase_orders"][0]["source_record_id"] = "shared-source-id"

    result = import_normalized_records(records, source="TEST", database=manager, persist=True)

    assert result["imported"] == 0
    assert result["duplicate"] == 1
    assert result["skipped"] == 1
    assert manager.get_purchase_order("PO-EXISTING")["vendor"] == "Existing vendor"
    assert manager.get_purchase_order("PO-NORMALIZED-1") is None
    assert manager.get_goods_receipts("PO-NORMALIZED-1") == []


def test_conflicting_same_source_po_values_block_dependent_receipt(tmp_path):
    manager = DatabaseManager(str(tmp_path / "same-source-po-conflict.db"))
    manager.setup_database()
    manager.add_purchase_order({
        "po_number": "PO-NORMALIZED-1",
        "vendor": "Different vendor",
        "quantity": 2,
        "unit_price": 3.25,
        "amount": 6.50,
        "status": "APPROVED",
        "data_source": "SYNTHETIC_TEST",
    })
    records = normalized_records()
    records["purchase_orders"][0].pop("source_record_id")

    result = import_normalized_records(
        records,
        source="SYNTHETIC_TEST",
        database=manager,
        persist=True,
    )

    assert result["duplicate"] == 1
    assert result["skipped"] == 1
    assert manager.get_purchase_order("PO-NORMALIZED-1")["vendor"] == "Different vendor"
    assert manager.get_goods_receipts("PO-NORMALIZED-1") == []


def test_import_transaction_rolls_back_records_and_summary_on_failure(tmp_path):
    manager = DatabaseManager(str(tmp_path / "import-rollback.db"))
    manager.setup_database()
    connection = manager.connect()
    try:
        connection.execute(
            """
            CREATE TRIGGER reject_test_receipt
            BEFORE INSERT ON goods_receipts
            WHEN NEW.receipt_number = 'GR-NORMALIZED-1'
            BEGIN
                SELECT RAISE(ABORT, 'simulated receipt insert failure');
            END;
            """
        )
        connection.commit()
    finally:
        connection.close()

    with pytest.raises(Exception, match="simulated receipt insert failure"):
        import_normalized_records(
            normalized_records(),
            source="TEST",
            database=manager,
            persist=True,
        )

    assert manager.get_purchase_order("PO-NORMALIZED-1") is None
    assert manager.get_goods_receipts("PO-NORMALIZED-1") == []
    assert manager.get_recent_import_runs() == []


def test_import_run_summary_records_counts_and_mapping_state(tmp_path):
    manager = DatabaseManager(str(tmp_path / "import-run-summary.db"))
    manager.setup_database()

    result = import_normalized_records(
        normalized_records(),
        source="SYNTHETIC_TEST",
        database=manager,
        persist=True,
        mapping_confirmed=True,
    )

    assert result["imported"] == 2
    assert result["import_run_id"] is not None
    recent = manager.get_recent_import_runs()
    assert len(recent) == 1
    assert recent[0]["source"] == "SYNTHETIC_TEST"
    assert recent[0]["status"] == "COMPLETED"
    assert recent[0]["mapping_confirmed"] is True
    assert recent[0]["imported_count"] == 2
    assert recent[0]["skipped_count"] == 0
    assert recent[0]["invalid_count"] == 0
    assert recent[0]["duplicate_count"] == 0


def test_imported_po_and_receipt_records_are_usable_by_existing_verifier(tmp_path):
    manager = DatabaseManager(str(tmp_path / "import-verification.db"))
    manager.setup_database()
    result = import_normalized_records(
        normalized_records(),
        source="SYNTHETIC_TEST",
        database=manager,
        persist=True,
    )
    assert result["imported"] == 2

    invoice = {
        "invoice_number": "SYNTHETIC-INVOICE-1",
        "vendor": "Example vendor",
        "po_number": "PO-NORMALIZED-1",
        "quantity": 2,
        "unit_price": 3.25,
        "amount": 6.50,
        "total_amount": 6.50,
    }
    po = manager.get_purchase_order(invoice["po_number"])
    receipts = manager.get_goods_receipts(invoice["po_number"])
    report = verify_invoice(invoice, po, receipts, manager)

    assert po["data_source"] == "SYNTHETIC_TEST"
    assert len(receipts) == 1
    assert receipts[0]["data_source"] == "SYNTHETIC_TEST"
    assert report["status"] == "PASSED"


def test_dashboard_source_summary_distinguishes_new_demo_seed_rows(tmp_path):
    manager = DatabaseManager(str(tmp_path / "source-summary.db"))
    manager.setup_database()
    manager.insert_demo_data()

    summary = manager.data_source_summary()

    assert summary["purchase_orders"]["DEMO"] == 1
    assert summary["goods_receipts"]["DEMO"] == 1
    assert summary["verified_invoices"]["DEMO"] == 2


def test_explicit_import_is_repeatable_and_preserves_source_metadata(tmp_path):
    manager = DatabaseManager(str(tmp_path / "normalized-import.db"))
    manager.setup_database()
    records = normalized_records()

    first = import_normalized_records(records, source="TEST", database=manager, persist=True)
    second = import_normalized_records(records, source="TEST", database=manager, persist=True)

    assert first["imported"] == 2
    assert second["imported"] == 0
    assert second["duplicate"] == 2
    po = manager.get_purchase_order("PO-NORMALIZED-1")
    receipt = manager.get_goods_receipts("PO-NORMALIZED-1")[0]
    assert po["data_source"] == "TEST"
    assert po["source_record_id"] == "source-po-1"
    assert json.loads(po["source_provenance_json"])["original_key"] == "source-po-1"
    assert receipt["data_source"] == "TEST"
    assert receipt["source_record_id"] == "source-gr-1"
    assert len(manager.get_all_purchase_orders()) == 1
    assert len(manager.get_all_goods_receipts()) == 1


def test_import_does_not_write_live_database_without_explicit_override():
    manager = DatabaseManager(str(DB_PATH))

    with pytest.raises(LiveDatabaseWriteDisabled):
        import_normalized_records(
            normalized_records(),
            source="TEST",
            database=manager,
            persist=True,
        )


def test_aczen_labeled_data_cannot_persist_before_mapping_confirmation(tmp_path):
    manager = DatabaseManager(str(tmp_path / "unconfirmed-source.db"))
    with pytest.raises(SourceMappingNotConfirmed):
        import_normalized_records(
            {},
            source="ACZEN",
            database=manager,
            persist=True,
        )


def test_new_demo_seeds_are_labeled_demo_and_existing_rows_stay_legacy(tmp_path):
    manager = DatabaseManager(str(tmp_path / "source-labels.db"))
    manager.setup_database()
    manager.insert_demo_data()
    manager.insert_demo_data()

    assert manager.get_purchase_order("PO500")["data_source"] == "DEMO"
    assert manager.get_goods_receipts("PO500")[0]["data_source"] == "DEMO"
    connection = manager.connect()
    try:
        rows = connection.execute(
            "SELECT invoice_number, data_source FROM verified_invoices ORDER BY invoice_number"
        ).fetchall()
    finally:
        connection.close()
    assert [(row[0], row[1]) for row in rows] == [("AI001", "DEMO"), ("AI002", "DEMO")]


def test_existing_database_rows_receive_legacy_source_during_safe_migration(tmp_path):
    manager = DatabaseManager(str(tmp_path / "legacy-source.db"))
    connection = manager.connect()
    try:
        connection.execute(
            "CREATE TABLE purchase_orders (po_number TEXT PRIMARY KEY, vendor TEXT NOT NULL, quantity INTEGER, unit_price REAL, amount REAL, status TEXT, created_at TEXT)"
        )
        connection.execute(
            "INSERT INTO purchase_orders VALUES ('PO-OLD', 'Old vendor', 1, 2, 2, 'APPROVED', NULL)"
        )
        connection.commit()
    finally:
        connection.close()

    manager.setup_database()
    po = manager.get_purchase_order("PO-OLD")
    assert po["data_source"] == "LEGACY"