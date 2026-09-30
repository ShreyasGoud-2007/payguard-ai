from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any


class NovaMappingError(ValueError):
    pass


def source_id(record: dict[str, Any]) -> str:
    value = record.get("id")
    if value is None or not str(value).strip():
        raise NovaMappingError("Nova record is missing its source ID")
    return str(value)


def decimal_value(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError) as exc:
        raise NovaMappingError("Nova record contains an invalid numeric value") from exc


def decimal_text(value: Any, default: Decimal = Decimal("0")) -> str:
    return format(decimal_value(value, default), "f")


def date_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    try:
        return date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def timestamp_text(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        parsed = value
    else:
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except ValueError:
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def safe_payload(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: safe_payload(item)
            for key, item in value.items()
            if not any(token in key.lower() for token in ("secret", "token", "bank", "account_number", "api_key"))
        }
    if isinstance(value, list):
        return [safe_payload(item) for item in value]
    return value


def line_source_key(parent_id: str, index: int) -> str:
    return f"{parent_id}:line:{index}"


def map_vendor(record: dict[str, Any], synced_at: str) -> dict[str, Any]:
    source_status = str(record.get("status") or "active").lower()
    status = "active" if source_status == "active" else "inactive"
    return {
        "nova_id": source_id(record),
        "name": str(record.get("name") or record.get("id")),
        "email": record.get("email"),
        "phone": record.get("phone"),
        "tax_id": record.get("pan"),
        "address": record.get("address"),
        "status": status,
        "risk_level": "low",
        "risk_score": 0,
        "gst_number": record.get("gst_number"),
        "pan": record.get("pan"),
        "state": record.get("state"),
        "state_code": record.get("state_code"),
        "category": record.get("category"),
        "criticality": record.get("criticality"),
        "payment_terms_days": record.get("payment_terms_days"),
        "early_pay_discount_pct": decimal_text(record.get("early_pay_discount_pct")) if record.get("early_pay_discount_pct") is not None else None,
        "late_penalty_pct_per_month": decimal_text(record.get("late_penalty_pct_per_month")) if record.get("late_penalty_pct_per_month") is not None else None,
        "source_created_at": timestamp_text(record.get("created_at")),
        "source_updated_at": timestamp_text(record.get("updated_at")),
        "synced_at": synced_at,
        "nova_payload": safe_payload(record),
    }


def map_purchase_order(record: dict[str, Any], vendor_id: str, synced_at: str) -> dict[str, Any]:
    return {
        "nova_id": source_id(record),
        "po_number": str(record.get("po_number") or record.get("id")),
        "vendor_id": vendor_id,
        "source_vendor_id": str(record.get("vendor_id") or ""),
        "order_date": date_text(record.get("order_date")),
        "total_amount": decimal_text(record.get("total_amount")) if record.get("total_amount") is not None else None,
        "order_total": decimal_text(record.get("total_amount")) if record.get("total_amount") is not None else None,
        "status": normalize_po_status(record.get("status")),
        "source_status": str(record.get("status") or "unknown"),
        "source_created_at": timestamp_text(record.get("created_at")),
        "source_updated_at": timestamp_text(record.get("updated_at")),
        "synced_at": synced_at,
        "nova_payload": safe_payload(record),
    }


def normalize_po_status(value: Any) -> str:
    status = str(value or "open").lower()
    known = {"open", "partially_received", "received", "closed", "cancelled"}
    return status if status in known else "open"


def map_order_item(record: dict[str, Any], parent_nova_id: str, parent_id: str, index: int) -> dict[str, Any]:
    source_item_id = str(record.get("item_id") or "") or None
    quantity = decimal_value(record.get("qty", record.get("quantity")))
    unit_price = decimal_value(record.get("unit_price", record.get("rate")))
    gst_rate = record.get("gst_rate", record.get("tax_rate"))
    return {
        "nova_id": line_source_key(parent_nova_id, index),
        "po_id": parent_id,
        "source_item_id": source_item_id,
        "description": str(record.get("description") or source_item_id or f"line {index + 1}"),
        "quantity": decimal_text(quantity),
        "unit_price": decimal_text(unit_price),
        "tax_rate": decimal_text(gst_rate) if gst_rate is not None else None,
        "source_gst_rate": decimal_text(gst_rate) if gst_rate is not None else None,
        "total": decimal_text(record.get("amount", quantity * unit_price)),
        "nova_payload": safe_payload(record),
    }


def map_goods_receipt(record: dict[str, Any], po_id: str, synced_at: str) -> dict[str, Any]:
    source_status = str(record.get("status") or "unknown").lower()
    status_map = {
        "received": "received",
        "accepted": "accepted",
        "completed": "completed",
        "rejected": "rejected",
        "cancelled": "cancelled",
        "partial": "received",
        "partially_received": "received",
        "pending": "received",
    }
    return {
        "nova_id": source_id(record),
        "grn_number": str(record.get("grn_number") or record.get("id")),
        "po_id": po_id,
        "received_date": date_text(record.get("received_date")),
        "status": status_map.get(source_status, "received"),
        "source_status": source_status,
        "source_po_id": str(record.get("po_id") or ""),
        "source_created_at": timestamp_text(record.get("created_at")),
        "source_updated_at": timestamp_text(record.get("updated_at")),
        "synced_at": synced_at,
        "nova_payload": safe_payload(record),
    }


def map_receipt_item(record: dict[str, Any], parent_nova_id: str, receipt_id: str, po_id: str, po_item_id: str, index: int) -> dict[str, Any]:
    return {
        "nova_id": line_source_key(parent_nova_id, index),
        "grn_id": receipt_id,
        "po_id": po_id,
        "po_item_id": po_item_id,
        "source_item_id": str(record.get("item_id") or "") or None,
        "quantity_received": decimal_text(record.get("qty_received", record.get("quantity_received"))),
        "quantity_rejected": decimal_text(record.get("qty_rejected")),
        "reject_reason": record.get("reject_reason"),
        "nova_payload": safe_payload(record),
    }


def map_purchase_bill(
    record: dict[str, Any],
    vendor_id: str,
    po_id: str | None,
    grn_id: str | None,
    synced_at: str,
    payment_terms_days: int | None = None,
) -> dict[str, Any]:
    amount = record.get("amount")
    total = record.get("total_amount")
    gst = record.get("gst_amount")
    bill_date = date_text(record.get("bill_date"))
    due_date = date_text(record.get("due_date"))
    if due_date is None and bill_date is not None and payment_terms_days is not None:
        due_date = (
            date.fromisoformat(bill_date) + timedelta(days=payment_terms_days)
        ).isoformat()
    return {
        "nova_id": source_id(record),
        "invoice_number": str(record.get("bill_number") or record.get("id")),
        "vendor_id": vendor_id,
        "po_id": po_id,
        "grn_id": grn_id,
        "invoice_date": bill_date,
        "due_date": due_date,
        "payment_terms_days": payment_terms_days,
        "subtotal": decimal_text(amount) if amount is not None else None,
        "source_amount": decimal_text(amount) if amount is not None else None,
        "tax_amount": decimal_text(gst) if gst is not None else None,
        "gst_amount": decimal_text(gst) if gst is not None else None,
        "cgst_amount": decimal_text(record.get("cgst_amount")) if record.get("cgst_amount") is not None else None,
        "sgst_amount": decimal_text(record.get("sgst_amount")) if record.get("sgst_amount") is not None else None,
        "igst_amount": decimal_text(record.get("igst_amount")) if record.get("igst_amount") is not None else None,
        "discount": "0",
        "total_amount": decimal_text(total) if total is not None else None,
        "currency": record.get("currency"),
        "paid_amount": decimal_text(record.get("paid_amount")) if record.get("paid_amount") is not None else None,
        "balance_due": decimal_text(record.get("balance_due")) if record.get("balance_due") is not None else None,
        "itc_eligible": record.get("itc_eligible"),
        "reverse_charge": record.get("reverse_charge"),
        "source_status": str(record.get("status") or "unknown"),
        "source_approval_status": str(record.get("approval_status") or "unknown"),
        "source_vendor_name": record.get("vendor_name"),
        "source_vendor_gst_number": record.get("vendor_gst_number"),
        "source_grn_id": str(record.get("grn_id") or "") or None,
        "status": "uploaded",
        "verification_status": "pending",
        "risk_level": "low",
        "risk_score": 0,
        "source_created_at": timestamp_text(record.get("created_at")),
        "source_updated_at": timestamp_text(record.get("updated_at")),
        "synced_at": synced_at,
        "nova_payload": safe_payload(record),
    }


def map_bill_item(record: dict[str, Any], parent_nova_id: str, invoice_id: str, index: int) -> dict[str, Any]:
    quantity = decimal_value(record.get("quantity"))
    unit_price = decimal_value(record.get("rate", record.get("unit_price")))
    source_item_id = str(record.get("item_id") or "") or None
    return {
        "nova_id": line_source_key(parent_nova_id, index),
        "invoice_id": invoice_id,
        "source_item_id": source_item_id,
        "description": str(record.get("description") or source_item_id or f"line {index + 1}"),
        "quantity": decimal_text(quantity),
        "unit_price": decimal_text(unit_price),
        "tax_rate": decimal_text(record.get("gst_rate")) if record.get("gst_rate") is not None else None,
        "total": decimal_text(record.get("amount", quantity * unit_price)),
        "gst_amount": decimal_text(record.get("gst_amount")) if record.get("gst_amount") is not None else None,
        "hsn_code": record.get("hsn_code"),
        "nova_payload": safe_payload(record),
    }


def map_nova_approval(
    record: dict[str, Any],
    invoice_id: str | None,
    synced_at: str,
) -> dict[str, Any]:
    return {
        "nova_id": source_id(record),
        "invoice_id": invoice_id,
        "doc_type": str(record.get("doc_type") or "unknown"),
        "source_doc_id": str(record.get("doc_id") or "") or None,
        "source_action": str(record.get("action") or "unknown"),
        "actor_id": str(record.get("actor_id") or "") or None,
        "approval_level": str(record.get("level") or "") or None,
        "threshold_applied": decimal_text(record.get("threshold_applied")) if record.get("threshold_applied") is not None else None,
        "acted_at": timestamp_text(record.get("acted_at")),
        "source_created_at": timestamp_text(record.get("created_at")),
        "source_updated_at": timestamp_text(record.get("updated_at")),
        "synced_at": synced_at,
        "nova_payload": safe_payload(record),
    }
