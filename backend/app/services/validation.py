import os
from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List

AP_PRICE_TOLERANCE = Decimal(str(os.getenv("AP_PRICE_TOLERANCE", "0.01")))


def _to_decimal(value: Any, default: Decimal = Decimal("0")) -> Decimal:
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return default


def _risk_score_from_exceptions(exception_codes: List[str]) -> int:
    risk = 0
    if any(code in {"INACTIVE_VENDOR", "MISSING_PO", "MISSING_GRN", "QUANTITY_MISMATCH", "TAX_MISMATCH", "DUPLICATE_INVOICE"} for code in exception_codes):
        risk += 50
    if any(code in {"PRICE_MISMATCH", "PO_VENDOR_MISMATCH", "RECEIPT_MISMATCH"} for code in exception_codes):
        risk += 30
    return max(risk, 0)


def evaluate_invoice(invoice: Dict[str, Any]) -> Dict[str, Any]:
    exception_codes: List[str] = []
    reasons: List[str] = []
    vendor = invoice.get("vendor") or {}
    po = invoice.get("po") or {}
    grn = invoice.get("grn") or {}
    items = invoice.get("invoice_items") or []
    duplicate_of = invoice.get("duplicate_of")

    vendor_status = (vendor.get("status") or "").upper()
    if vendor_status not in {"ACTIVE", "LOW_RISK"}:
        exception_codes.append("INACTIVE_VENDOR")
        reasons.append("Vendor is inactive or invalid")

    if not po:
        exception_codes.append("MISSING_PO")
        reasons.append("No valid purchase order found")
    elif (po.get("status") or "").upper() != "APPROVED":
        exception_codes.append("PO_VALIDATION_FAILED")
        reasons.append("Purchase order is not approved")
    elif vendor.get("vendor_name") and po.get("vendor_name") and vendor["vendor_name"] != po["vendor_name"]:
        exception_codes.append("PO_VENDOR_MISMATCH")
        reasons.append("Invoice vendor does not match the PO vendor")

    if not grn:
        exception_codes.append("MISSING_GRN")
        reasons.append("No goods receipt found")
    elif (grn.get("status") or "").upper() != "RECEIVED":
        exception_codes.append("RECEIPT_MISMATCH")
        reasons.append("Goods receipt is not valid or not received")

    received_quantity = _to_decimal(grn.get("quantity_received"))
    invoice_quantity = sum((_to_decimal(item.get("quantity")) for item in items), Decimal("0"))
    if invoice_quantity > received_quantity:
        exception_codes.append("QUANTITY_MISMATCH")
        reasons.append("Invoice quantity exceeds received quantity")

    po_quantity = _to_decimal(po.get("quantity"))
    if po_quantity and invoice_quantity > po_quantity:
        exception_codes.append("PO_QUANTITY_MISMATCH")
        reasons.append("Invoice quantity exceeds the authorized PO quantity")

    expected_total = sum(
        (_to_decimal(item.get("quantity")) * _to_decimal(item.get("unit_price")) for item in items),
        Decimal("0"),
    )
    tax_amount = _to_decimal(invoice.get("tax_amount"))
    invoice_total = _to_decimal(invoice.get("invoice_total"))
    if abs((expected_total + tax_amount) - invoice_total) > Decimal("0.01"):
        exception_codes.append("TAX_MISMATCH")
        reasons.append("Tax and total do not reconcile to the invoice value")

    po_unit_price = _to_decimal(po.get("unit_price"))
    for item in items:
        item_unit_price = _to_decimal(item.get("unit_price"))
        if po_unit_price and abs(item_unit_price - po_unit_price) > AP_PRICE_TOLERANCE:
            exception_codes.append("PRICE_MISMATCH")
            reasons.append("Invoice item price differs from the PO unit price beyond tolerance")
            break

    if duplicate_of:
        exception_codes.append("DUPLICATE_INVOICE")
        reasons.append(f"Possible duplicate: {invoice.get('invoice_number')} resembles {duplicate_of} for the same vendor and amount")

    distinct_codes = []
    for code in exception_codes:
        if code not in distinct_codes:
            distinct_codes.append(code)

    risk_level = "LOW"
    if any(code in {"MISSING_PO", "INACTIVE_VENDOR", "TAX_MISMATCH", "QUANTITY_MISMATCH", "DUPLICATE_INVOICE"} for code in distinct_codes):
        risk_level = "HIGH"
    elif any(code in {"PRICE_MISMATCH", "PO_VENDOR_MISMATCH", "RECEIPT_MISMATCH", "PO_QUANTITY_MISMATCH"} for code in distinct_codes):
        risk_level = "MEDIUM"

    if not distinct_codes:
        status = "APPROVED"
    else:
        status = "UNDER_REVIEW"

    payable_eligible = status == "APPROVED" and risk_level == "LOW" and not distinct_codes

    return {
        "invoice_number": invoice.get("invoice_number"),
        "status": status,
        "risk_level": risk_level,
        "risk_score": _risk_score_from_exceptions(distinct_codes),
        "exception_codes": distinct_codes,
        "reasons": reasons,
        "payable_eligible": payable_eligible,
        "approval_required": risk_level in {"MEDIUM", "HIGH"},
        "audit_ready": True,
    }
