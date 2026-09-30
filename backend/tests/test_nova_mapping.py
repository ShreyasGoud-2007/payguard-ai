import unittest
from decimal import Decimal

from app.services.nova_mapping import (
    decimal_value,
    map_purchase_bill,
    map_vendor,
    safe_payload,
)


class NovaMappingTests(unittest.TestCase):
    def test_bill_preserves_nova_id_and_does_not_import_source_approval_as_payguard_approval(self):
        bill = map_purchase_bill(
            {
                "id": "nova-bill-id-not-uuid",
                "bill_number": "PB-1",
                "vendor_id": "nova-vendor-id",
                "po_id": "nova-po-id",
                "grn_id": "nova-grn-id",
                "bill_date": "2026-08-10",
                "amount": "100.00",
                "gst_amount": "18.00",
                "cgst_amount": "9.00",
                "sgst_amount": "9.00",
                "total_amount": "118.00",
                "status": "paid",
                "approval_status": "approved",
            },
            "local-vendor-uuid",
            "local-po-uuid",
            "local-grn-uuid",
            "2026-09-30T00:00:00+00:00",
        )

        self.assertEqual(bill["nova_id"], "nova-bill-id-not-uuid")
        self.assertEqual(bill["vendor_id"], "local-vendor-uuid")
        self.assertEqual(bill["po_id"], "local-po-uuid")
        self.assertEqual(bill["grn_id"], "local-grn-uuid")
        self.assertEqual(bill["source_status"], "paid")
        self.assertEqual(bill["source_approval_status"], "approved")
        self.assertEqual(bill["status"], "uploaded")
        self.assertEqual(bill["verification_status"], "pending")
        self.assertEqual(bill["total_amount"], "118.00")
        self.assertEqual(bill["igst_amount"], None)

    def test_decimal_mapping_never_round_trips_through_float(self):
        value = decimal_value("123456789012.3400")
        self.assertEqual(value, Decimal("123456789012.3400"))
        self.assertIsInstance(value, Decimal)

    def test_vendor_payload_excludes_bank_fields(self):
        payload = safe_payload({
            "id": "vendor-id",
            "bank_account_last4": "0000",
            "bank_ifsc": "PRIVATE",
            "nested": {"account_number": "PRIVATE", "name": "Acme"},
        })
        self.assertEqual(payload, {"id": "vendor-id", "nested": {"name": "Acme"}})
        vendor = map_vendor(
            {"id": "vendor-id", "name": "Acme", "bank_account_last4": "0000"},
            "2026-09-30T00:00:00+00:00",
        )
        self.assertNotIn("bank_account_last4", vendor["nova_payload"])


if __name__ == "__main__":
    unittest.main()
