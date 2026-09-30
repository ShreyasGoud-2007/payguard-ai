from __future__ import annotations

import asyncio
from typing import Any, Dict, List
from urllib.parse import quote

import httpx

from app.config import settings
from app.services.validation import evaluate_invoice


class SupabaseServiceError(RuntimeError):
    pass


class SupabaseAuthenticationError(RuntimeError):
    pass


class SupabaseService:
    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.url = (url if url is not None else settings.SUPABASE_URL).rstrip("/")
        self.key = key if key is not None else (
            settings.SUPABASE_SERVICE_ROLE_KEY or settings.SUPABASE_ANON_KEY
        )
        self.transport = transport

    async def _request(self, method: str, table: str, **kwargs: Any) -> List[Dict[str, Any]]:
        if not self.url or not self.key:
            raise SupabaseServiceError("Supabase URL and API key must be configured")

        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Accept": "application/json",
        }
        prefer = kwargs.pop("prefer", None)
        if method in {"POST", "PATCH"}:
            headers["Prefer"] = prefer or "return=representation"

        async with httpx.AsyncClient(
            transport=self.transport,
            timeout=20.0,
        ) as client:
            try:
                response = await client.request(
                    method,
                    f"{self.url}/rest/v1/{quote(table)}",
                    headers=headers,
                    **kwargs,
                )
                response.raise_for_status()
            except httpx.HTTPError as exc:
                raise SupabaseServiceError(f"Supabase {table} request failed") from exc

        if not response.content:
            return []
        payload = response.json()
        if not isinstance(payload, list):
            raise SupabaseServiceError(f"Unexpected Supabase response for {table}")
        return payload

    async def fetch_dataset(self) -> Dict[str, Any]:
        table_names = (
            "vendors",
            "invoices",
            "invoice_items",
            "purchase_orders",
            "purchase_order_items",
            "goods_receipts",
            "goods_receipt_items",
            "approvals",
            "payable_ledger",
            "audit_logs",
        )
        rows = await asyncio.gather(*(self._request("GET", name, params={"select": "*"}) for name in table_names))
        return dict(zip(table_names, rows))

    @staticmethod
    def _rows_by_id(rows: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        return {str(row["id"]): row for row in rows if row.get("id") is not None}

    @staticmethod
    def _quantity(items: List[Dict[str, Any]], field: str = "quantity") -> float:
        return sum(float(item.get(field) or 0) for item in items)

    @staticmethod
    def _invoice_po(invoice: Dict[str, Any], invoice_items: List[Dict[str, Any]], dataset: Dict[str, Any]) -> Dict[str, Any] | None:
        purchase_orders = dataset["purchase_orders"]
        by_id = SupabaseService._rows_by_id(purchase_orders)
        if invoice.get("po_id"):
            return by_id.get(str(invoice["po_id"]))

        po_items = SupabaseService._rows_by_id(dataset["purchase_order_items"])
        for item in invoice_items:
            po_item = po_items.get(str(item.get("po_item_id")))
            if po_item and str(po_item.get("po_id")) in by_id:
                return by_id[str(po_item["po_id"])]

        return None

    def _assemble_invoices(self, dataset: Dict[str, Any]) -> List[Dict[str, Any]]:
        vendors = self._rows_by_id(dataset["vendors"])
        invoices = self._rows_by_id(dataset["invoices"])
        invoice_items_by_invoice: Dict[str, List[Dict[str, Any]]] = {}
        for item in dataset["invoice_items"]:
            invoice_items_by_invoice.setdefault(str(item.get("invoice_id")), []).append(item)
        po_items_by_po: Dict[str, List[Dict[str, Any]]] = {}
        for item in dataset["purchase_order_items"]:
            po_items_by_po.setdefault(str(item.get("po_id")), []).append(item)
        receipts_by_po: Dict[str, List[Dict[str, Any]]] = {}
        receipt_items_by_receipt: Dict[str, List[Dict[str, Any]]] = {}
        for receipt in dataset["goods_receipts"]:
            receipts_by_po.setdefault(str(receipt.get("po_id")), []).append(receipt)
        for item in dataset["goods_receipt_items"]:
            receipt_items_by_receipt.setdefault(str(item.get("grn_id")), []).append(item)

        assembled = []
        for row in dataset["invoices"]:
            line_items = invoice_items_by_invoice.get(str(row.get("id")), [])
            vendor = vendors.get(str(row.get("vendor_id")), {})
            po = self._invoice_po(row, line_items, dataset)
            po_lines = po_items_by_po.get(str(po.get("id")), []) if po else []
            related_receipts = receipts_by_po.get(str(po.get("id")), []) if po else []
            receipt = related_receipts[0] if related_receipts else None
            received_quantity = sum(
                self._quantity(receipt_items_by_receipt.get(str(item.get("id")), []), "quantity_received")
                or float(item.get("total_received_quantity") or 0)
                for item in related_receipts
            )
            expected_total = float(row.get("subtotal_amount") or 0)
            duplicate = row.get("duplicate_of_invoice_id")
            if duplicate is None:
                duplicate_row = next((
                    other for other in dataset["invoices"]
                    if other.get("id") != row.get("id")
                    and other.get("vendor_id") == row.get("vendor_id")
                    and other.get("total_amount") == row.get("total_amount")
                    and (
                        str(other.get("invoice_date") or other.get("created_at", "")),
                        str(other.get("created_at", "")),
                        str(other.get("id", "")),
                    ) < (
                        str(row.get("invoice_date") or row.get("created_at", "")),
                        str(row.get("created_at", "")),
                        str(row.get("id", "")),
                    )
                ), None)
                duplicate = duplicate_row.get("id") if duplicate_row else None

            assembled.append({
                **row,
                "invoice_total": float(row.get("total_amount") or expected_total),
                "vendor": {
                    "vendor_id": vendor.get("id"),
                    "vendor_name": vendor.get("vendor_name"),
                    "status": vendor.get("status"),
                },
                "po": {
                    "po_id": po.get("id"),
                    "po_number": po.get("po_number"),
                    "vendor_name": vendor.get("vendor_name"),
                    "status": po.get("status"),
                    "quantity": self._quantity(po_lines),
                    "unit_price": float(po_lines[0].get("unit_price") or 0) if po_lines else 0,
                } if po else {},
                "grn": {
                    "grn_id": receipt.get("id"),
                    "grn_number": receipt.get("grn_number"),
                    "status": receipt.get("status"),
                    "quantity_received": received_quantity,
                } if receipt else {},
                "invoice_items": [
                    {"description": item.get("description"), "quantity": float(item.get("quantity") or 0),
                     "unit_price": float(item.get("unit_price") or 0)}
                    for item in line_items
                ],
                "tax_amount": float(row.get("tax_amount") or 0),
                "duplicate_of": invoices.get(str(duplicate), {}).get("invoice_number") if duplicate else None,
            })
        return assembled

    async def fetch_invoices(self) -> List[Dict[str, Any]]:
        return self._assemble_invoices(await self.fetch_dataset())

    async def fetch_invoice(self, invoice_number: str) -> Dict[str, Any] | None:
        return next((invoice for invoice in await self.fetch_invoices()
                     if invoice.get("invoice_number") == invoice_number), None)

    async def fetch_vendors(self) -> List[Dict[str, Any]]:
        dataset = await self.fetch_dataset()
        vendor_risks = {
            str(vendor.get("id")): [
                invoice.get("risk_level", "LOW") for invoice in dataset["invoices"]
                if invoice.get("vendor_id") == vendor.get("id")
            ]
            for vendor in dataset["vendors"]
        }
        return [{
            "vendor_id": row.get("id"),
            "vendor_name": row.get("vendor_name"),
            "vendor_code": row.get("tax_id"),
            "status": row.get("status"),
            "risk_level": max(vendor_risks[str(row.get("id"))],
                               key={"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get, default="LOW"),
        } for row in dataset["vendors"]]

    async def fetch_purchase_orders(self) -> List[Dict[str, Any]]:
        dataset = await self.fetch_dataset()
        vendors = self._rows_by_id(dataset["vendors"])
        items_by_po: Dict[str, List[Dict[str, Any]]] = {}
        for item in dataset["purchase_order_items"]:
            items_by_po.setdefault(str(item.get("po_id")), []).append(item)
        return [{
            "po_id": row.get("id"),
            "po_number": row.get("po_number"),
            "vendor_name": vendors.get(str(row.get("vendor_id")), {}).get("vendor_name"),
            "status": row.get("status"),
            "quantity": self._quantity(items_by_po.get(str(row.get("id")), [])),
            "unit_price": float(items_by_po.get(str(row.get("id")), [{}])[0].get("unit_price") or 0),
        } for row in dataset["purchase_orders"]]

    async def fetch_goods_receipts(self) -> List[Dict[str, Any]]:
        dataset = await self.fetch_dataset()
        purchase_orders = self._rows_by_id(dataset["purchase_orders"])
        items_by_receipt: Dict[str, List[Dict[str, Any]]] = {}
        for item in dataset["goods_receipt_items"]:
            items_by_receipt.setdefault(str(item.get("grn_id")), []).append(item)
        return [{
            "grn_id": row.get("id"),
            "grn_number": row.get("grn_number"),
            "status": row.get("status"),
            "quantity_received": self._quantity(items_by_receipt.get(str(row.get("id")), []), "quantity_received")
                or float(row.get("total_received_quantity") or 0),
            "po_number": purchase_orders.get(str(row.get("po_id")), {}).get("po_number"),
        } for row in dataset["goods_receipts"]]

    async def fetch_audit_log(self) -> List[Dict[str, Any]]:
        dataset = await self.fetch_dataset()
        invoices = self._rows_by_id(dataset["invoices"])
        return [{
            "invoice_number": invoices.get(str(row.get("invoice_id")), {}).get("invoice_number"),
            "event": row.get("action"),
            "status": (row.get("details") or {}).get("status"),
            "details": (row.get("details") or {}).get("reason", row.get("action")),
            "created_at": row.get("created_at"),
        } for row in dataset["audit_logs"]]

    async def fetch_payable_ledger(self) -> List[Dict[str, Any]]:
        dataset = await self.fetch_dataset()
        invoices = self._rows_by_id(dataset["invoices"])
        vendors = self._rows_by_id(dataset["vendors"])
        return [{
            "invoice_number": invoices.get(str(row.get("invoice_id")), {}).get("invoice_number"),
            "vendor": vendors.get(str(row.get("vendor_id")), {}).get("vendor_name"),
            "amount": float(row.get("total_amount") or 0),
        } for row in dataset["payable_ledger"]]

    async def fetch_exceptions(self) -> List[Dict[str, Any]]:
        exceptions = []
        for invoice in await self.fetch_invoices():
            result = evaluate_invoice(invoice)
            if result["exception_codes"]:
                exceptions.append({
                    "invoice_number": invoice["invoice_number"],
                    "risk_level": result["risk_level"],
                    "exception_codes": result["exception_codes"],
                    "reasons": result["reasons"],
                })
        return exceptions

    async def _authenticate_approver(self, access_token: str) -> Dict[str, Any]:
        if not self.url or not self.key:
            raise SupabaseServiceError("Supabase URL and API key must be configured")
        async with httpx.AsyncClient(transport=self.transport, timeout=20.0) as client:
            try:
                response = await client.get(
                    f"{self.url}/auth/v1/user",
                    headers={"apikey": self.key, "Authorization": f"Bearer {access_token}"},
                )
            except httpx.HTTPError as exc:
                raise SupabaseServiceError("Supabase Auth request failed") from exc
        if response.status_code in {401, 403}:
            raise SupabaseAuthenticationError("Invalid or expired Supabase access token")
        try:
            response.raise_for_status()
            auth_user = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SupabaseServiceError("Supabase Auth request failed") from exc

        users = await self._request(
            "GET", "users",
            params={"select": "id,email,role", "auth_provider_id": f"eq.{auth_user.get('id')}", "is_active": "eq.true"},
        )
        if not users:
            raise SupabaseAuthenticationError("No active PayGuard user is linked to this Supabase account")
        return users[0]

    async def decide_approval(
        self,
        invoice_number: str,
        approved: bool,
        access_token: str,
    ) -> Dict[str, Any] | None:
        actor = await self._authenticate_approver(access_token)
        invoice_rows = await self._request(
            "GET", "invoices", params={"select": "id,invoice_number", "invoice_number": f"eq.{invoice_number}"}
        )
        if not invoice_rows:
            return None
        invoice_id = str(invoice_rows[0]["id"])
        state = "APPROVED" if approved else "REJECTED"
        approval_rows = await self._request(
            "PATCH", "approvals", params={
                "invoice_id": f"eq.{invoice_id}",
                "approver_id": f"eq.{actor['id']}",
                "approval_state": "eq.PENDING",
            },
            json={"approval_state": state},
        )
        if not approval_rows:
            return {"invoice_number": invoice_number, "status": state, "message": "No pending approval found"}

        fresh_invoice = await self.fetch_invoice(invoice_number)
        payable = bool(approved and fresh_invoice and evaluate_invoice(fresh_invoice)["payable_eligible"])
        invoice_status = "APPROVED" if payable else ("UNDER_REVIEW" if approved else "REJECTED")
        await self._request(
            "PATCH", "invoices", params={"id": f"eq.{invoice_id}"},
            json={"status": invoice_status, "payable_eligible": payable},
        )
        if payable and fresh_invoice:
            amount = float(fresh_invoice.get("total_amount") or 0)
            required_fields = (fresh_invoice.get("vendor_id"), fresh_invoice.get("due_date"), actor.get("id"))
            if amount <= 0 or not all(required_fields):
                raise SupabaseServiceError("Validated invoice is missing required payable ledger fields")
            await self._request(
                "POST", "payable_ledger",
                params={"on_conflict": "invoice_id"},
                prefer="resolution=merge-duplicates,return=representation",
                json=[{
                    "invoice_id": invoice_id,
                    "vendor_id": fresh_invoice["vendor_id"],
                    "total_amount": amount,
                    "amount_paid": 0,
                    "remaining_balance": amount,
                    "currency_code": fresh_invoice.get("currency_code") or "USD",
                    "payment_due_date": fresh_invoice["due_date"],
                    "posted_by": actor["id"],
                }],
            )
        await self._request(
            "POST", "audit_logs", json=[{
                "invoice_id": invoice_id,
                "entity_type": "INVOICE",
                "entity_id": invoice_id,
                "action": f"APPROVAL_{state}",
                "actor": actor.get("email"),
                "actor_role": actor.get("role"),
                "details": {"status": invoice_status, "payable_eligible": payable},
            }],
        )
        return {"invoice_number": invoice_number, "status": invoice_status, "payable_eligible": payable}
