from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from .nova_mapping import (
    line_source_key,
    map_bill_item,
    map_goods_receipt,
    map_nova_approval,
    map_order_item,
    map_purchase_bill,
    map_purchase_order,
    map_receipt_item,
    map_vendor,
    source_id,
)


class NovaSyncError(RuntimeError):
    pass


class NovaSyncService:
    BATCH_SIZE = 100

    def __init__(self, nova_client: Any, database: Any, *, dry_run: bool = False):
        self.nova = nova_client
        self.database = database
        self.dry_run = dry_run
        self.synced_at = datetime.now(timezone.utc).isoformat()

    def _upsert(self, table: str, records: list[dict[str, Any]]) -> list[dict[str, Any]]:
        if not records:
            return []

        if self.dry_run:
            result = []
            for record in records:
                row = dict(record)
                row["id"] = str(uuid5(NAMESPACE_URL, f"payguard:{table}:{record['nova_id']}"))
                result.append(row)
            return result

        result: list[dict[str, Any]] = []
        try:
            for start in range(0, len(records), self.BATCH_SIZE):
                batch = records[start:start + self.BATCH_SIZE]
                response = (
                    self.database.table(table)
                    .upsert(batch, on_conflict="nova_id")
                    .execute()
                )
                if not response.data:
                    raise NovaSyncError(f"Supabase returned no rows for {table} upsert")
                result.extend(response.data)
        except NovaSyncError:
            raise
        except Exception as exc:
            raise NovaSyncError(f"Supabase synchronization failed for {table}") from exc
        return result

    def _audit(self, action: str, run_id: str, details: dict[str, Any]) -> None:
        if self.dry_run:
            return
        try:
            self.database.table("audit_logs").insert({
                "invoice_id": None,
                "entity_type": "nova_sync",
                "entity_id": run_id,
                "action": action,
                "performed_by": "nova_sync",
                "source": "nova",
                "details": details,
            }).execute()
        except Exception as exc:
            raise NovaSyncError("Could not record Nova synchronization audit event") from exc

    @staticmethod
    def _id_map(rows: list[dict[str, Any]]) -> dict[str, str]:
        return {str(row["nova_id"]): str(row["id"]) for row in rows}

    def sync(self) -> dict[str, Any]:
        run_id = f"nova-sync:{self.synced_at}"
        self._audit("SYNC_STARTED", run_id, {"source": "nova"})

        try:
            source_vendors = self.nova.list_vendors()
            source_orders = self.nova.list_purchase_orders()
            source_receipts = self.nova.list_goods_receipts()
            source_bills = self.nova.list_purchase_bills()
            source_approvals = self.nova.list_approvals(doc_type="purchase_bill")

            vendors = self._upsert(
                "vendors",
                [map_vendor(record, self.synced_at) for record in source_vendors],
            )
            vendor_ids = self._id_map(vendors)

            order_records = []
            for record in source_orders:
                vendor_id = vendor_ids.get(str(record.get("vendor_id")))
                if not vendor_id:
                    raise NovaSyncError("A Nova purchase order references an unknown vendor")
                order_records.append(map_purchase_order(record, vendor_id, self.synced_at))
            orders = self._upsert("purchase_orders", order_records)
            order_ids = self._id_map(orders)
            source_orders_by_id = {source_id(record): record for record in source_orders}

            order_items_to_sync = []
            for order in orders:
                source_order = source_orders_by_id[order["nova_id"]]
                for index, item in enumerate(source_order.get("items") or []):
                    order_items_to_sync.append(
                        map_order_item(item, order["nova_id"], str(order["id"]), index)
                    )
            order_items = self._upsert("purchase_order_items", order_items_to_sync)

            order_item_ids: dict[tuple[str, str], list[str]] = {}
            for item in order_items:
                source_order_id = item["nova_id"].split(":line:", 1)[0]
                source_item_id = str(item.get("source_item_id") or "")
                if source_item_id:
                    order_item_ids.setdefault((source_order_id, source_item_id), []).append(str(item["id"]))

            receipt_records = []
            for record in source_receipts:
                po_id = order_ids.get(str(record.get("po_id")))
                if not po_id:
                    raise NovaSyncError("A Nova goods receipt references an unknown purchase order")
                receipt_records.append(map_goods_receipt(record, po_id, self.synced_at))
            receipts = self._upsert("goods_receipts", receipt_records)
            receipt_ids = self._id_map(receipts)
            source_receipts_by_id = {source_id(record): record for record in source_receipts}

            receipt_items_to_sync = []
            unresolved_receipt_items = 0
            for receipt in receipts:
                source_receipt = source_receipts_by_id[receipt["nova_id"]]
                po_nova_id = str(source_receipt.get("po_id") or "")
                local_po_id = order_ids[po_nova_id]
                for index, item in enumerate(source_receipt.get("items") or []):
                    source_item_id = str(item.get("item_id") or "")
                    candidates = order_item_ids.get((po_nova_id, source_item_id), [])
                    if not candidates:
                        unresolved_receipt_items += 1
                        continue
                    receipt_items_to_sync.append(
                        map_receipt_item(
                            item,
                            receipt["nova_id"],
                            str(receipt["id"]),
                            local_po_id,
                            candidates[0],
                            index,
                        )
                    )
            receipt_items = self._upsert("goods_receipt_items", receipt_items_to_sync)

            source_bills_by_id = {source_id(record): record for record in source_bills}
            source_vendors_by_id = {source_id(record): record for record in source_vendors}
            existing_ids: set[str] = set()
            existing_bills: dict[str, dict[str, Any]] = {}
            if not self.dry_run:
                try:
                    existing_rows = (
                        self.database.table("invoices")
                        .select("id,nova_id,status,verification_status,risk_level,risk_score,risk_reasons,verification_result")
                        .execute()
                        .data
                    )
                    existing_ids = {str(row["nova_id"]) for row in existing_rows if row.get("nova_id")}
                    existing_bills = {
                        str(row["nova_id"]): row
                        for row in existing_rows
                        if row.get("nova_id")
                    }
                except Exception as exc:
                    raise NovaSyncError("Could not inspect existing Nova bills for idempotent sync") from exc

            bill_records = []
            for record in source_bills:
                vendor_id = vendor_ids.get(str(record.get("vendor_id")))
                if not vendor_id:
                    raise NovaSyncError("A Nova purchase bill references an unknown vendor")
                source_po_id = str(record.get("po_id") or "")
                po_id = order_ids.get(source_po_id) if source_po_id else None
                source_grn_id = str(record.get("grn_id") or "")
                grn_id = receipt_ids.get(source_grn_id) if source_grn_id else None
                payment_terms = source_vendors_by_id.get(
                    str(record.get("vendor_id")),
                    {},
                ).get("payment_terms_days")
                if grn_id and po_id:
                    source_receipt = source_receipts_by_id[source_grn_id]
                    if str(source_receipt.get("po_id")) != source_po_id:
                        grn_id = None
                bill_record = map_purchase_bill(
                    record,
                    vendor_id,
                    po_id,
                    grn_id,
                    self.synced_at,
                    int(payment_terms) if payment_terms is not None else None,
                )
                existing_bill = existing_bills.get(bill_record["nova_id"])
                if existing_bill:
                    for workflow_field in (
                        "status",
                        "verification_status",
                        "risk_level",
                        "risk_score",
                        "risk_reasons",
                        "verification_result",
                    ):
                        bill_record.pop(workflow_field, None)
                else:
                    bill_record.update({
                        "status": "uploaded",
                        "verification_status": "pending",
                        "risk_level": "low",
                        "risk_score": 0,
                        "risk_reasons": [],
                    })
                bill_records.append(bill_record)
            bills = self._upsert("invoices", bill_records)
            bill_ids = self._id_map(bills)

            bill_items_to_sync = []
            for bill in bills:
                source_bill = source_bills_by_id[bill["nova_id"]]
                for index, item in enumerate(source_bill.get("items") or []):
                    bill_items_to_sync.append(
                        map_bill_item(item, bill["nova_id"], str(bill["id"]), index)
                    )
            bill_items = self._upsert("invoice_items", bill_items_to_sync)

            approval_records = []
            for record in source_approvals:
                if str(record.get("doc_type") or "").lower() != "purchase_bill":
                    continue
                local_bill_id = bill_ids.get(str(record.get("doc_id")))
                approval_records.append(
                    map_nova_approval(record, local_bill_id, self.synced_at)
                )
            approvals = self._upsert("nova_approvals", approval_records)

            newly_imported_bills = [
                row for row in bills if row["nova_id"] not in existing_ids
            ]
            for bill in newly_imported_bills:
                self._audit(
                    "BILL_IMPORTED",
                    bill["nova_id"],
                    {"source": "nova", "invoice_id": bill["id"]},
                )

            result = {
                "run_id": run_id,
                "dry_run": self.dry_run,
                "synced_at": self.synced_at,
                "counts": {
                    "vendors": len(vendors),
                    "purchase_orders": len(orders),
                    "purchase_order_items": len(order_items),
                    "goods_receipts": len(receipts),
                    "goods_receipt_items": len(receipt_items),
                    "purchase_bills": len(bills),
                    "purchase_bill_items": len(bill_items),
                    "purchase_bill_approvals": len(approvals),
                    "new_purchase_bills": len(newly_imported_bills) if not self.dry_run else len(bills),
                    "unresolved_receipt_items": unresolved_receipt_items,
                },
            }
            self._audit("SYNC_COMPLETED", run_id, result["counts"])
            return result
        except Exception as exc:
            try:
                self._audit("SYNC_FAILED", run_id, {"error_type": type(exc).__name__})
            except Exception:
                pass
            if isinstance(exc, NovaSyncError):
                raise
            raise NovaSyncError("Nova synchronization failed") from exc
