import unittest
from datetime import datetime, timezone
from uuid import uuid4

from app.services.nova_sync import NovaSyncService


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, database, table):
        self.database = database
        self.table = table
        self.operation = "select"
        self.payload = None
        self.conflict_key = "nova_id"
        self.filters = []

    def select(self, *_args, **_kwargs):
        self.operation = "select"
        return self

    def upsert(self, payload, on_conflict="nova_id"):
        self.operation = "upsert"
        self.payload = payload
        self.conflict_key = on_conflict
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def eq(self, column, value):
        self.filters.append((column, "eq", str(value)))
        return self

    def neq(self, column, value):
        self.filters.append((column, "neq", str(value)))
        return self

    def execute(self):
        rows = self.database.tables.setdefault(self.table, [])
        if self.operation == "select":
            matching = []
            for row in rows:
                include = True
                for column, operator, value in self.filters:
                    equal = str(row.get(column)) == value
                    if (operator == "eq" and not equal) or (operator == "neq" and equal):
                        include = False
                        break
                if include:
                    matching.append(row)
            return FakeResponse(matching)

        if self.operation == "update":
            matching = []
            for row in rows:
                if all(
                    (str(row.get(column)) == value if operator == "eq" else str(row.get(column)) != value)
                    for column, operator, value in self.filters
                ):
                    row.update(self.payload)
                    matching.append(row)
            return FakeResponse(matching)

        incoming = self.payload if isinstance(self.payload, list) else [self.payload]
        if self.operation == "insert":
            inserted = []
            for record in incoming:
                row = {
                    "id": str(uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    **record,
                }
                rows.append(row)
                inserted.append(row)
            return FakeResponse(inserted)

        result = []
        for record in incoming:
            existing = next(
                (row for row in rows if row.get(self.conflict_key) == record.get(self.conflict_key)),
                None,
            )
            if existing:
                existing.update(record)
                result.append(existing)
            else:
                row = {
                    "id": str(uuid4()),
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    **record,
                }
                rows.append(row)
                result.append(row)
        return FakeResponse(result)


class FakeSupabase:
    def __init__(self):
        self.tables = {}

    def table(self, name):
        return FakeQuery(self, name)


class FakeNova:
    def __init__(self):
        self.vendors = [{
            "id": "nova-vendor-1",
            "name": "Source Vendor",
            "status": "active",
            "created_at": "2026-01-01T00:00:00Z",
        }]
        self.purchase_orders = [{
            "id": "nova-po-1",
            "po_number": "PO-1",
            "vendor_id": "nova-vendor-1",
            "status": "open",
            "total_amount": "118.00",
            "items": [{"item_id": "catalog-1", "qty": "2", "unit_price": "50", "gst_rate": "18"}],
        }]
        self.goods_receipts = [{
            "id": "nova-grn-1",
            "grn_number": "GRN-1",
            "po_id": "nova-po-1",
            "status": "received",
            "items": [{"item_id": "catalog-1", "qty_received": "2", "qty_rejected": "0"}],
        }]
        self.purchase_bills = [{
            "id": "nova-bill-1",
            "bill_number": "BILL-1",
            "vendor_id": "nova-vendor-1",
            "po_id": "nova-po-1",
            "grn_id": "nova-grn-1",
            "amount": "100.00",
            "gst_amount": "18.00",
            "cgst_amount": "9.00",
            "sgst_amount": "9.00",
            "total_amount": "118.00",
            "status": "paid",
            "approval_status": "approved",
            "items": [{
                "item_id": "catalog-1",
                "description": "Source item",
                "quantity": "2",
                "rate": "50",
                "amount": "100",
                "gst_rate": "18",
                "gst_amount": "18",
            }],
        }]
        self.approvals = [{
            "id": "nova-approval-1",
            "doc_type": "purchase_bill",
            "doc_id": "nova-bill-1",
            "action": "approve",
        }]
        self.requested = []

    def _return(self, name):
        self.requested.append(name)
        return getattr(self, name)

    def list_vendors(self):
        return self._return("vendors")

    def list_purchase_orders(self):
        return self._return("purchase_orders")

    def list_goods_receipts(self):
        return self._return("goods_receipts")

    def list_purchase_bills(self):
        return self._return("purchase_bills")

    def list_approvals(self, **filters):
        self.requested.append(("approvals", filters))
        return self.approvals


class NovaSyncTests(unittest.TestCase):
    def setUp(self):
        self.nova = FakeNova()
        self.database = FakeSupabase()
        self.service = NovaSyncService(self.nova, self.database)

    def test_repeated_sync_upserts_by_source_id_without_duplicates(self):
        first = self.service.sync()
        initial_rows = {
            table: len(rows)
            for table, rows in self.database.tables.items()
            if table != "audit_logs"
        }
        bill_id = self.database.tables["invoices"][0]["id"]
        second = self.service.sync()

        self.assertEqual(initial_rows, {
            table: len(rows)
            for table, rows in self.database.tables.items()
            if table != "audit_logs"
        })
        self.assertEqual(self.database.tables["invoices"][0]["id"], bill_id)
        self.assertEqual(first["counts"]["purchase_bills"], 1)
        self.assertEqual(second["counts"]["new_purchase_bills"], 0)
        self.assertEqual(len(self.database.tables["nova_approvals"]), 1)
        self.assertNotIn("approvals", self.database.tables)
        self.assertEqual(
            sum(row["action"] == "BILL_IMPORTED" for row in self.database.tables["audit_logs"]),
            1,
        )
        self.assertEqual(
            sum(row["action"] == "SYNC_COMPLETED" for row in self.database.tables["audit_logs"]),
            2,
        )
        self.assertIn(("approvals", {"doc_type": "purchase_bill"}), self.nova.requested)
        self.assertNotIn("list_vendor_payments", self.nova.requested)
        self.assertNotIn("list_vendor_bank_accounts", self.nova.requested)

    def test_dry_run_normalizes_full_graph_without_database_writes(self):
        database = FakeSupabase()
        result = NovaSyncService(self.nova, database, dry_run=True).sync()

        self.assertTrue(result["dry_run"])
        self.assertEqual(result["counts"]["purchase_bills"], 1)
        self.assertEqual(result["counts"]["purchase_order_items"], 1)
        self.assertEqual(result["counts"]["goods_receipt_items"], 1)
        self.assertEqual(database.tables, {})

    def test_source_bill_status_never_creates_payguard_payable(self):
        self.service.sync()
        imported = self.database.tables["invoices"][0]

        self.assertEqual(imported["source_status"], "paid")
        self.assertEqual(imported["source_approval_status"], "approved")
        self.assertEqual(imported["status"], "uploaded")
        self.assertEqual(imported["verification_status"], "pending")
        self.assertNotIn("payable_ledger", self.database.tables)

    def test_resync_preserves_payguard_approval_and_risk_state(self):
        self.service.sync()
        invoice = self.database.tables["invoices"][0]
        invoice.update({
            "status": "approved",
            "verification_status": "verified",
            "risk_level": "medium",
            "risk_score": 35,
            "risk_reasons": ["manual review"],
            "verification_result": {"passed": True},
        })

        self.service.sync()

        self.assertEqual(invoice["status"], "approved")
        self.assertEqual(invoice["verification_status"], "verified")
        self.assertEqual(invoice["risk_score"], 35)
        self.assertEqual(invoice["risk_reasons"], ["manual review"])
        self.assertEqual(invoice["verification_result"], {"passed": True})


if __name__ == "__main__":
    unittest.main()
