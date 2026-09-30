import os
import unittest
from datetime import datetime, timezone
from uuid import uuid4

os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_KEY", "test-key")

from fastapi.testclient import TestClient

from app import main


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, database, table):
        self.database = database
        self.table = table
        self.operation = "select"
        self.payload = None
        self.filters = []
        self.order_by = None
        self.limit_count = None

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, "eq", str(value)))
        return self

    def neq(self, column, value):
        self.filters.append((column, "neq", str(value)))
        return self

    def order(self, column, desc=False):
        self.order_by = (column, desc)
        return self

    def limit(self, count):
        self.limit_count = count
        return self

    def execute(self):
        rows = self.database.tables.setdefault(self.table, [])
        matching = [row for row in rows if self._matches(row)]

        if self.operation == "insert":
            payloads = self.payload if isinstance(self.payload, list) else [self.payload]
            inserted = []
            for payload in payloads:
                row = {
                    "id": str(uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    **payload,
                }
                rows.append(row)
                inserted.append(row)
            return FakeResponse(inserted)

        if self.operation == "update":
            for row in matching:
                row.update(self.payload)
            return FakeResponse(matching)

        if self.order_by:
            column, descending = self.order_by
            matching.sort(key=lambda row: row.get(column) or "", reverse=descending)
        if self.limit_count is not None:
            matching = matching[:self.limit_count]
        return FakeResponse(matching)

    def _matches(self, row):
        for column, operation, value in self.filters:
            matches = str(row.get(column)) == value
            if operation == "eq" and not matches:
                return False
            if operation == "neq" and matches:
                return False
        return True


class FakeSupabase:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        return FakeQuery(self, name)


class InvoiceWorkflowTests(unittest.TestCase):
    def setUp(self):
        self.database = FakeSupabase()
        main.supabase = self.database
        self.client = TestClient(main.app)

    def create_vendor(self, name="Northstar Supplies"):
        response = self.client.post("/api/vendors", json={"name": name})
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["vendor"]

    def create_order_and_receipt(self, vendor_id):
        response = self.client.post(
            "/api/purchase-orders",
            json={
                "po_number": "PO-1001",
                "vendor_id": vendor_id,
                "total_amount": "110.00",
                "items": [
                    {
                        "description": "Industrial filters",
                        "quantity": "2",
                        "unit_price": "50.00",
                        "tax_rate": "10",
                        "total": "100.00",
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        order = response.json()["purchase_order"]
        po_item = response.json()["items"][0]

        receipt_response = self.client.post(
            "/api/goods-receipts",
            json={
                "grn_number": "GRN-1001",
                "po_id": order["id"],
                "items": [
                    {"po_item_id": po_item["id"], "quantity_received": "2"}
                ],
            },
        )
        self.assertEqual(receipt_response.status_code, 200, receipt_response.text)
        return order, po_item

    def create_invoice(self, vendor_id, po_id, invoice_number="INV-1001"):
        response = self.client.post(
            "/api/invoices",
            json={
                "invoice_number": invoice_number,
                "vendor_id": vendor_id,
                "po_id": po_id,
                "subtotal": "100.00",
                "tax_amount": "10.00",
                "discount": "0",
                "total_amount": "110.00",
                "items": [
                    {
                        "description": "Industrial filters",
                        "quantity": "2",
                        "unit_price": "50.00",
                        "tax_rate": "10",
                        "total": "100.00",
                    }
                ],
            },
        )
        self.assertEqual(response.status_code, 200, response.text)
        return response.json()["invoice"]

    def test_health_openapi_and_frontend_collection_aliases(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "healthy"})

        openapi = self.client.get("/openapi.json")
        self.assertEqual(openapi.status_code, 200)
        self.assertIn("/api/admin/nova/sync", openapi.json()["paths"])

        for path in ("/vendors", "/purchase-orders", "/goods-receipts", "/invoices", "/purchase-bills", "/payables"):
            response = self.client.get(path)
            self.assertEqual(response.status_code, 200, f"{path}: {response.text}")

    def test_complete_invoice_to_payable_and_audit_workflow(self):
        vendor = self.create_vendor()
        order, _ = self.create_order_and_receipt(vendor["id"])
        invoice = self.create_invoice(vendor["id"], order["id"])

        verified = self.client.post(f"/api/invoices/{invoice['id']}/verify")
        self.assertEqual(verified.status_code, 200, verified.text)
        self.assertTrue(verified.json()["verified"])
        self.assertEqual(verified.json()["risk_level"], "low")

        premature_post = self.client.post(f"/api/invoices/{invoice['id']}/post-payable")
        self.assertEqual(premature_post.status_code, 409)

        approved = self.client.post(
            f"/api/invoices/{invoice['id']}/approve",
            json={"approver_name": "A. Reviewer", "approver_role": "controller"},
        )
        self.assertEqual(approved.status_code, 200, approved.text)
        self.assertEqual(approved.json()["invoice_status"], "approved")

        posted = self.client.post(f"/api/invoices/{invoice['id']}/post-payable")
        self.assertEqual(posted.status_code, 200, posted.text)
        self.assertEqual(posted.json()["payable"]["approved_amount"], "110.00")

        repeated_post = self.client.post(f"/api/invoices/{invoice['id']}/post-payable")
        self.assertEqual(repeated_post.status_code, 200, repeated_post.text)
        self.assertTrue(repeated_post.json()["already_exists"])
        self.assertEqual(len(self.database.tables["payable_ledger"]), 1)

        details = self.client.get(f"/api/invoices/{invoice['id']}")
        self.assertEqual(details.status_code, 200, details.text)
        self.assertEqual(details.json()["invoice"]["status"], "posted")
        self.assertIsNotNone(details.json()["payable"])
        actions = {entry["action"] for entry in details.json()["audit_logs"]}
        self.assertIn("invoice_created", actions)
        self.assertIn("invoice_verification_completed", actions)
        self.assertIn("invoice_approved", actions)
        self.assertIn("invoice_posted_to_payable", actions)

    def test_rejects_cross_vendor_invoice_and_cross_po_receipt_line(self):
        first_vendor = self.create_vendor("First Vendor")
        second_vendor = self.create_vendor("Second Vendor")
        order, _ = self.create_order_and_receipt(first_vendor["id"])

        mismatched_invoice = self.client.post(
            "/api/invoices",
            json={
                "invoice_number": "INV-MISMATCH",
                "vendor_id": second_vendor["id"],
                "po_id": order["id"],
            },
        )
        self.assertEqual(mismatched_invoice.status_code, 422)

        other_order = self.client.post(
            "/api/purchase-orders",
            json={
                "po_number": "PO-1002",
                "vendor_id": first_vendor["id"],
                "items": [{"description": "Other item", "quantity": 1, "unit_price": 5}],
            },
        )
        other_item_id = other_order.json()["items"][0]["id"]
        mismatched_receipt = self.client.post(
            "/api/goods-receipts",
            json={
                "grn_number": "GRN-MISMATCH",
                "po_id": order["id"],
                "items": [{"po_item_id": other_item_id, "quantity_received": 1}],
            },
        )
        self.assertEqual(mismatched_receipt.status_code, 422)

    def test_duplicate_invoice_number_is_rejected(self):
        vendor = self.create_vendor()
        order, _ = self.create_order_and_receipt(vendor["id"])
        self.create_invoice(vendor["id"], order["id"])

        duplicate = self.client.post(
            "/api/invoices",
            json={"invoice_number": "INV-1001", "vendor_id": vendor["id"]},
        )
        self.assertEqual(duplicate.status_code, 409)

    def test_verified_invoice_quantities_cannot_exceed_receipts_across_invoices(self):
        vendor = self.create_vendor()
        order, _ = self.create_order_and_receipt(vendor["id"])
        first = self.create_invoice(vendor["id"], order["id"], "INV-FIRST-1001")
        first_result = self.client.post(f"/api/invoices/{first['id']}/verify")
        self.assertTrue(first_result.json()["verified"])

        second = self.create_invoice(vendor["id"], order["id"], "INV-SECOND-2002")
        second_result = self.client.post(f"/api/invoices/{second['id']}/verify")
        self.assertFalse(second_result.json()["verified"])
        self.assertTrue(
            any("Total invoiced quantity exceeds received quantity" in issue
                for issue in second_result.json()["issues"])
        )

    def test_pending_bill_reserves_po_quantity_and_amount_exposure(self):
        vendor = self.create_vendor()
        order, _ = self.create_order_and_receipt(vendor["id"])
        self.create_invoice(vendor["id"], order["id"], "PENDING-FIRST-100")
        second = self.create_invoice(vendor["id"], order["id"], "PENDING-SECOND-200")

        response = self.client.post(f"/api/invoices/{second['id']}/verify")

        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["passed"])
        self.assertIn(
            "Cumulative invoice total exceeds purchase order amount",
            response.json()["issues"],
        )

    def test_cumulative_invoice_amount_cannot_exceed_po_amount(self):
        vendor = self.create_vendor()
        order, _ = self.create_order_and_receipt(vendor["id"])

        def create_partial_invoice(number):
            response = self.client.post(
                "/api/invoices",
                json={
                    "invoice_number": number,
                    "vendor_id": vendor["id"],
                    "po_id": order["id"],
                    "subtotal": "50.00",
                    "tax_amount": "10.00",
                    "total_amount": "60.00",
                    "items": [
                        {
                            "description": "Industrial filters",
                            "quantity": "1",
                            "unit_price": "50.00",
                            "tax_rate": "20",
                            "total": "50.00",
                        }
                    ],
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            return response.json()["invoice"]

        first = create_partial_invoice("PARTIAL-FIRST-100")
        self.assertTrue(
            self.client.post(f"/api/invoices/{first['id']}/verify").json()["verified"]
        )
        second = create_partial_invoice("PARTIAL-SECOND-200")
        verification = self.client.post(f"/api/invoices/{second['id']}/verify")
        self.assertFalse(verification.json()["verified"])
        self.assertIn(
            "Cumulative invoice total exceeds purchase order amount",
            verification.json()["issues"],
        )

    def test_gst_component_mismatch_fails_financial_validation(self):
        vendor = self.create_vendor()
        invoice = self.create_invoice(vendor["id"], None)
        row = self.database.tables["invoices"][0]
        row.update({
            "gst_amount": "10.00",
            "cgst_amount": "6.00",
            "sgst_amount": "4.00",
            "igst_amount": "0.00",
        })

        response = self.client.get(
            f"/api/invoices/{invoice['id']}/financial-validation"
        )
        self.assertEqual(response.status_code, 200, response.text)
        self.assertFalse(response.json()["valid"])
        self.assertFalse(response.json()["gst_component_match"])
        self.assertTrue(
            any("CGST and SGST amounts must match" in issue
                for issue in response.json()["issues"])
        )

    def test_rejected_goods_quantity_is_not_available_for_invoice(self):
        vendor = self.create_vendor()
        order, _ = self.create_order_and_receipt(vendor["id"])
        invoice = self.create_invoice(vendor["id"], order["id"])
        receipt_item = self.database.tables["goods_receipt_items"][0]
        receipt_item["quantity_rejected"] = "1"

        result = self.client.post(f"/api/invoices/{invoice['id']}/verify")
        self.assertEqual(result.status_code, 200, result.text)
        self.assertFalse(result.json()["goods_received"])
        self.assertTrue(
            any("Total invoiced quantity exceeds received quantity" in issue
                for issue in result.json()["issues"])
        )

    def test_high_value_invoice_requires_two_distinct_approvers(self):
        vendor = self.create_vendor()
        order_response = self.client.post(
            "/api/purchase-orders",
            json={
                "po_number": "PO-HIGH-1001",
                "vendor_id": vendor["id"],
                "total_amount": "110000.00",
                "items": [
                    {
                        "description": "Annual services",
                        "quantity": "1",
                        "unit_price": "100000.00",
                        "tax_rate": "10",
                        "total": "100000.00",
                    }
                ],
            },
        )
        order = order_response.json()["purchase_order"]
        po_item = order_response.json()["items"][0]
        self.client.post(
            "/api/goods-receipts",
            json={
                "grn_number": "GRN-HIGH-1001",
                "po_id": order["id"],
                "items": [{"po_item_id": po_item["id"], "quantity_received": "1"}],
            },
        )
        invoice_response = self.client.post(
            "/api/invoices",
            json={
                "invoice_number": "INV-HIGH-1001",
                "vendor_id": vendor["id"],
                "po_id": order["id"],
                "subtotal": "100000.00",
                "tax_amount": "10000.00",
                "total_amount": "110000.00",
                "items": [
                    {
                        "description": "Annual services",
                        "quantity": "1",
                        "unit_price": "100000.00",
                        "tax_rate": "10",
                        "total": "100000.00",
                    }
                ],
            },
        )
        invoice = invoice_response.json()["invoice"]
        verified = self.client.post(f"/api/invoices/{invoice['id']}/verify")
        self.assertTrue(verified.json()["verified"])

        first = self.client.post(
            f"/api/invoices/{invoice['id']}/approve",
            json={"approver_name": "First Reviewer", "approver_role": "controller"},
        )
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(first.json()["invoice_status"], "pending_approval")

        repeated = self.client.post(
            f"/api/invoices/{invoice['id']}/approve",
            json={"approver_name": "First Reviewer", "approver_role": "controller"},
        )
        self.assertEqual(repeated.status_code, 409)

        second = self.client.post(
            f"/api/invoices/{invoice['id']}/approve",
            json={"approver_name": "Second Reviewer", "approver_role": "finance"},
        )
        self.assertEqual(second.status_code, 200, second.text)
        self.assertEqual(second.json()["invoice_status"], "approved")

    def test_similar_invoice_detection_requires_number_and_amount_similarity(self):
        vendor = self.create_vendor()
        first = self.client.post(
            "/api/invoices",
            json={"invoice_number": "ACCT-40012", "vendor_id": vendor["id"], "invoice_date": "2026-05-01", "total_amount": 110},
        ).json()["invoice"]
        similar = self.client.post(
            "/api/invoices",
            json={"invoice_number": "ACCT-40012-A", "vendor_id": vendor["id"], "invoice_date": "2026-05-01", "total_amount": 110},
        ).json()["invoice"]
        same_amount = self.client.post(
            "/api/invoices",
            json={"invoice_number": "APRIL-RETAINER-772", "vendor_id": vendor["id"], "invoice_date": "2026-06-01", "total_amount": 110},
        ).json()["invoice"]

        suspicious_result = self.client.get(
            f"/api/invoices/{similar['id']}/duplicate-check"
        )
        amount_only_result = self.client.get(
            f"/api/invoices/{same_amount['id']}/duplicate-check"
        )
        self.assertTrue(suspicious_result.json()["is_suspicious"])
        self.assertFalse(amount_only_result.json()["is_suspicious"])
        self.assertNotEqual(first["id"], similar["id"])

    def test_verification_fails_without_required_values_and_missing_records_are_404(self):
        vendor = self.create_vendor()
        invoice = self.create_invoice(vendor["id"], None)
        invoice_row = self.database.tables["invoices"][0]
        invoice_row["subtotal"] = None
        invoice_row["total_amount"] = None

        verification = self.client.post(f"/api/invoices/{invoice['id']}/verify")
        self.assertEqual(verification.status_code, 200)
        self.assertFalse(verification.json()["verified"])
        self.assertGreater(verification.json()["risk_score"], 0)

        missing = self.client.get(f"/api/invoices/{uuid4()}")
        self.assertEqual(missing.status_code, 404)


if __name__ == "__main__":
    unittest.main()
