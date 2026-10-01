import json
import sqlite3

import pytest

from paygard_ai.database import DatabaseManager
from paygard_ai.verification import verify_invoice


def make_invoice(**overrides):
    invoice = {
        "invoice_number": "AI100",
        "vendor": "ABC Traders",
        "po_number": "PO500",
        "quantity": 10,
        "unit_price": 100,
        "amount": 1000,
        "invoice_date": "2026-09-30",
    }
    invoice.update(overrides)
    return invoice


def make_po(**overrides):
    po = {
        "po_number": "PO500",
        "vendor": "ABC Traders",
        "quantity": 10,
        "unit_price": 100,
        "amount": 1000,
        "status": "APPROVED",
    }
    po.update(overrides)
    return po


def make_receipt(**overrides):
    receipt = {
        "receipt_number": "GR500",
        "po_number": "PO500",
        "quantity": 10,
    }
    receipt.update(overrides)
    return receipt


def test_matching_invoice_passes(tmp_path):
    db_path = tmp_path / "paygard.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.insert_demo_data()

    invoice = make_invoice()
    po = make_po()
    receipt = make_receipt()
    result = verify_invoice(invoice, po, [receipt], manager)

    assert result["status"] == "PASSED"
    assert result["checks"]["duplicate_check"]["status"] == "PASS"


@pytest.mark.parametrize("po_status", ["PENDING", "REJECTED"])
def test_nonapproved_purchase_order_cannot_pass(po_status):
    result = verify_invoice(make_invoice(), make_po(status=po_status), [make_receipt()])

    assert result["status"] == "REVIEW REQUIRED"
    assert result["checks"]["po_approval"]["status"] == "FAIL"


def test_missing_purchase_order_status_is_incomplete():
    result = verify_invoice(make_invoice(), make_po(status=None), [make_receipt()])

    assert result["status"] == "INCOMPLETE"
    assert result["checks"]["po_approval"]["status"] == "INCOMPLETE"


def test_duplicate_invoice_is_review_required(tmp_path):
    db_path = tmp_path / "paygard.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.insert_demo_data()

    manager.save_invoice(make_invoice(), "PASSED")
    result = verify_invoice(make_invoice(), make_po(), [make_receipt()], manager)

    assert result["status"] == "REVIEW REQUIRED"
    assert any(check["name"] == "Duplicate invoice" for check in result["checks"])


def test_missing_po_and_receipt_are_incomplete(tmp_path):
    db_path = tmp_path / "paygard.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()

    result = verify_invoice(make_invoice(), None, [], manager)

    assert result["status"] == "INCOMPLETE"


def test_vendor_mismatch_and_amount_mismatch(tmp_path):
    db_path = tmp_path / "paygard.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.insert_demo_data()

    invoice = make_invoice(vendor="Wrong Vendor", amount=800)
    po = make_po(vendor="ABC Traders")
    receipt = make_receipt(quantity=10)
    result = verify_invoice(invoice, po, [receipt], manager)

    assert result["status"] == "REVIEW REQUIRED"
    assert any(check["name"] == "Vendor match" for check in result["checks"])
    assert any(check["name"] == "Invoice amount matches PO amount" for check in result["checks"])


def test_malformed_numeric_values_are_flagged(tmp_path):
    db_path = tmp_path / "paygard.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.insert_demo_data()

    invoice = make_invoice(quantity="ten", unit_price="abc", amount="NaN")
    po = make_po()
    receipt = make_receipt()
    result = verify_invoice(invoice, po, [receipt], manager)

    assert result["status"] == "INCOMPLETE"
    assert any(check["name"] == "Numeric validation" for check in result["checks"])


def test_multi_line_invoice_matches_and_receipts_are_supported(tmp_path):
    db_path = tmp_path / "paygard.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.insert_demo_data()

    invoice = {
        "invoice_number": "MULTI-1",
        "vendor": "ABC Traders",
        "po_number": "PO500",
        "amount": 600,
        "total_amount": 600,
        "line_items": [
            {"description": "Laptop", "quantity": 2, "unit_price": 100, "line_total": 200},
            {"description": "Mouse", "quantity": 4, "unit_price": 100, "line_total": 400},
        ],
    }
    po = {
        "po_number": "PO500",
        "vendor": "ABC Traders",
        "status": "APPROVED",
        "line_items": [
            {"description": "Laptop", "quantity": 2, "unit_price": 100},
            {"description": "Mouse", "quantity": 4, "unit_price": 100},
        ],
    }
    receipts = [
        {"receipt_number": "GR500A", "po_number": "PO500", "quantity": 2, "line_items": [{"description": "Laptop", "quantity": 2}]},
        {"receipt_number": "GR500B", "po_number": "PO500", "quantity": 4, "line_items": [{"description": "Mouse", "quantity": 4}]},
    ]

    result = verify_invoice(invoice, po, receipts, manager)
    assert result["status"] == "PASSED"
    assert any(check["name"] == "Line item reconciliation" for check in result["checks"])


def test_partial_receipt_and_excess_quantity_are_review_required(tmp_path):
    db_path = tmp_path / "paygard.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.insert_demo_data()

    invoice = {
        "invoice_number": "MULTI-2",
        "vendor": "ABC Traders",
        "po_number": "PO500",
        "amount": 600,
        "total_amount": 600,
        "line_items": [
            {"description": "Laptop", "quantity": 3, "unit_price": 100, "line_total": 300},
            {"description": "Mouse", "quantity": 4, "unit_price": 100, "line_total": 400},
        ],
    }
    po = {
        "po_number": "PO500",
        "vendor": "ABC Traders",
        "status": "APPROVED",
        "line_items": [
            {"description": "Laptop", "quantity": 2, "unit_price": 100},
            {"description": "Mouse", "quantity": 4, "unit_price": 100},
        ],
    }
    receipts = [{"receipt_number": "GR500C", "po_number": "PO500", "quantity": 2}]

    result = verify_invoice(invoice, po, receipts, manager)
    assert result["status"] == "REVIEW REQUIRED"
    assert any(check["name"] == "Goods receipt support" for check in result["checks"])


def test_surplus_receipt_on_one_item_cannot_offset_another_item_shortage():
    invoice = {
        "invoice_number": "ITEM-RECEIPT-1",
        "vendor": "ABC Traders",
        "po_number": "PO500",
        "amount": 300,
        "total_amount": 300,
        "line_items": [
            {"description": "Laptop", "quantity": 2, "unit_price": 100, "line_total": 200},
            {"description": "Mouse", "quantity": 4, "unit_price": 25, "line_total": 100},
        ],
    }
    po = {
        "po_number": "PO500",
        "vendor": "ABC Traders",
        "status": "APPROVED",
        "amount": 300,
        "line_items": [
            {"description": "Laptop", "quantity": 2, "unit_price": 100},
            {"description": "Mouse", "quantity": 4, "unit_price": 25},
        ],
    }
    receipts = [{
        "receipt_number": "GR-ITEM-1",
        "po_number": "PO500",
        "quantity": 6,
        "line_items": [
            {"description": "Laptop", "quantity": 1},
            {"description": "Mouse", "quantity": 5},
        ],
    }]

    result = verify_invoice(invoice, po, receipts)
    assert result["status"] == "REVIEW REQUIRED"
    assert result["checks"]["receipt_support"]["status"] == "FAIL"


def test_review_decision_and_audit_history_are_saved(tmp_path):
    db_path = tmp_path / "paygard.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.insert_demo_data()

    manager.save_review_decision("AI999", "needs_correction", "reviewer1", "Price mismatch")
    manager.log_event("review", "Case reviewed", {"invoice_number": "AI999"})

    history = manager.get_review_history("AI999")
    assert len(history) >= 1
    assert history[0]["decision"] == "needs_correction"


def test_recent_audit_events_expose_review_context_without_source_paths(tmp_path):
    manager = DatabaseManager(str(tmp_path / "audit-view.db"))
    manager.setup_database()
    manager.record_review_decision("SYNTH-INV-1", "escalated", "reviewer", "Synthetic note")

    events = manager.list_recent_audit_events(10)

    assert len(events) == 1
    assert events[0]["event_type"] == "review_decision"
    assert events[0]["invoice_number"] == "SYNTH-INV-1"
    assert events[0]["decision"] == "escalated"
    assert "file_path" not in events[0]
    assert "details" not in events[0]


def test_record_review_decision_writes_audit_without_changing_verification(tmp_path):
    db_path = tmp_path / "review-audit.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.save_invoice(make_invoice(), "REVIEW REQUIRED")

    decision_id = manager.record_review_decision(
        "AI100",
        "needs_more_information",
        "synthetic-reviewer",
        "Confirm the source receipt before proceeding.",
    )

    assert decision_id > 0
    assert manager.get_review_history("AI100")[0]["notes"] == "Confirm the source receipt before proceeding."
    conn = manager.connect()
    try:
        audit = conn.execute(
            "SELECT event_type, details FROM audit_logs ORDER BY id DESC LIMIT 1"
        ).fetchone()
        invoice = conn.execute(
            "SELECT status FROM verified_invoices WHERE invoice_number = ?",
            ("AI100",),
        ).fetchone()
    finally:
        conn.close()
    details = json.loads(audit["details"])
    assert audit["event_type"] == "review_decision"
    assert details["invoice_number"] == "AI100"
    assert details["decision"] == "needs_more_information"
    assert invoice["status"] == "REVIEW REQUIRED"


def test_dashboard_summary_works(tmp_path):
    db_path = tmp_path / "paygard.db"
    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    manager.insert_demo_data()
    manager.save_invoice({"invoice_number": "AI900", "vendor": "ABC Traders", "po_number": "PO500", "quantity": 10, "unit_price": 100, "amount": 1000}, "PASSED")

    summary = manager.dashboard_summary()
    assert summary["passed"] >= 1


def test_list_recent_activity_supports_legacy_verified_invoices_schema(tmp_path):
    db_path = tmp_path / "legacy-paygard.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE verified_invoices (
            invoice_number TEXT PRIMARY KEY,
            vendor TEXT NOT NULL,
            po_number TEXT,
            quantity INTEGER,
            unit_price REAL,
            amount REAL,
            status TEXT
        )
        """
    )
    conn.execute(
        "INSERT INTO verified_invoices (invoice_number, vendor, status) VALUES (?, ?, ?)",
        ("LEGACY-1", "ABC Traders", "PASSED"),
    )
    conn.commit()
    conn.close()

    manager = DatabaseManager(str(db_path))
    manager.setup_database()
    activity = manager.list_recent_activity(10)

    assert activity == [{"invoice_number": "LEGACY-1", "status": "PASSED", "created_at": None}]
