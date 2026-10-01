from decimal import Decimal, InvalidOperation


class CheckCollection(dict):
    def __iter__(self):
        return iter(self.values())


def _normalize_text(value):
    if value is None:
        return ""
    return "".join(ch for ch in str(value).lower() if ch.isalnum() or ch.isspace()).replace("  ", " ").strip()


def _as_decimal(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        if isinstance(value, (int, float)):
            return Decimal(str(value))
        text = str(value).strip().replace(",", "")
        if not text or text.lower() in {"na", "n/a", "none"}:
            return None
        return Decimal(text)
    except (InvalidOperation, ValueError):
        return None


def _check_result(key, name, status, expected=None, actual=None, explanation="", evidence="", severity="medium"):
    return {
        "key": key,
        "name": name,
        "status": status,
        "expected": expected,
        "actual": actual,
        "explanation": explanation,
        "evidence": evidence,
        "severity": severity,
    }


def _build_line_items(invoice):
    if invoice is None:
        return []
    if invoice.get("line_items"):
        return invoice["line_items"]
    item_name = invoice.get("item") or invoice.get("description") or "Item"
    quantity = invoice.get("quantity")
    unit_price = invoice.get("unit_price")
    amount = invoice.get("amount") or invoice.get("total_amount")
    if quantity is None and unit_price is None and amount is None:
        return []
    return [{
        "description": item_name,
        "quantity": quantity,
        "unit_price": unit_price,
        "line_total": amount,
    }]


def _po_lines(po):
    if po is None:
        return []
    if po.get("line_items"):
        return po["line_items"]
    if po.get("item") or po.get("quantity") or po.get("unit_price"):
        return [{
            "description": po.get("item") or po.get("description") or "Item",
            "quantity": po.get("quantity"),
            "unit_price": po.get("unit_price"),
            "line_total": po.get("amount") or po.get("total_amount"),
        }]
    return []


def _receipt_lines(receipts):
    if not receipts:
        return []
    all_lines = []
    for receipt in receipts:
        if isinstance(receipt, dict):
            items = receipt.get("line_items") or []
            if items:
                for item in items:
                    all_lines.append({
                        "description": item.get("description") or item.get("item") or "Item",
                        "quantity": item.get("quantity"),
                    })
            elif receipt.get("quantity") is not None:
                all_lines.append({
                    "description": "Item",
                    "quantity": receipt.get("quantity"),
                })
    return all_lines


def verify_invoice(invoice, po, receipts, db_manager=None):
    checks = {}
    invoice_items = _build_line_items(invoice)
    invoice_number = str(invoice.get("invoice_number", "")).strip()
    vendor = str(invoice.get("vendor", "")).strip()
    po_number = str(invoice.get("po_number", "")).strip()
    quantity = _as_decimal(invoice.get("quantity"))
    unit_price = _as_decimal(invoice.get("unit_price"))
    amount = _as_decimal(invoice.get("amount"))
    if amount is None:
        amount = _as_decimal(invoice.get("total_amount"))

    if invoice_items:
        line_quantities = []
        line_prices = []
        line_totals = []
        for item in invoice_items:
            qty = _as_decimal(item.get("quantity"))
            price = _as_decimal(item.get("unit_price"))
            total = _as_decimal(item.get("line_total"))
            if qty is not None:
                line_quantities.append(qty)
            if price is not None:
                line_prices.append(price)
            if total is None and qty is not None and price is not None:
                total = qty * price
            if total is not None:
                line_totals.append(total)
        if line_quantities:
            quantity = sum(line_quantities, Decimal("0"))
        if line_prices and unit_price is None:
            unique_prices = {price for price in line_prices}
            if len(unique_prices) == 1:
                unit_price = next(iter(unique_prices))
        if line_totals and amount is None:
            amount = sum(line_totals, Decimal("0"))

    if not invoice_number or not vendor or not po_number:
        checks["required_fields"] = _check_result(
            "required_fields",
            "Required invoice fields",
            "INCOMPLETE",
            expected="invoice_number, vendor, po_number",
            actual={"invoice_number": invoice_number, "vendor": vendor, "po_number": po_number},
            explanation="The invoice is missing required identifier information for verification.",
            evidence="Field validation",
            severity="high",
        )

    if invoice_items:
        line_numeric_invalid = any(
            (_as_decimal(item.get("quantity")) is None and item.get("quantity") is not None)
            or (_as_decimal(item.get("unit_price")) is None and item.get("unit_price") is not None)
            for item in invoice_items
        )
        checks["numeric_validation"] = _check_result(
            "numeric_validation",
            "Numeric validation",
            "PASS" if not line_numeric_invalid else "INCOMPLETE",
            expected="all line-item quantities and prices are valid numbers",
            actual=[item for item in invoice_items if (_as_decimal(item.get("quantity")) is None and item.get("quantity") is not None) or (_as_decimal(item.get("unit_price")) is None and item.get("unit_price") is not None)],
            explanation="Multi-line invoices validate each item quantity and price independently before summing the final total.",
            evidence="Line-item numeric parsing",
            severity="high" if line_numeric_invalid else "low",
        )
    elif quantity is None or unit_price is None or amount is None:
        checks["numeric_validation"] = _check_result(
            "numeric_validation",
            "Numeric validation",
            "INCOMPLETE",
            expected="valid quantity, unit price, and amount",
            actual={
                "quantity": invoice.get("quantity"),
                "unit_price": invoice.get("unit_price"),
                "amount": invoice.get("amount") or invoice.get("total_amount"),
            },
            explanation="One or more numeric fields could not be parsed as valid values.",
            evidence="Field parsing",
            severity="high",
        )
    else:
        checks["numeric_validation"] = _check_result(
            "numeric_validation",
            "Numeric validation",
            "PASS",
            expected="valid quantity, unit price, and amount",
            actual={
                "quantity": quantity,
                "unit_price": unit_price,
                "amount": amount,
            },
            explanation="The invoice summary values are valid numbers and can be used for checking against the PO.",
            evidence="Numeric parsing",
            severity="low",
        )

    duplicate = False
    if db_manager and invoice_number:
        duplicate = db_manager.invoice_exists(invoice_number)
        checks["duplicate_check"] = _check_result(
            "duplicate_check",
            "Duplicate invoice",
            "PASS" if not duplicate else "FAIL",
            expected="invoice is not already in verified invoices",
            actual=duplicate,
            explanation="Duplicate invoice detection compares the invoice number against previously verified records.",
            evidence="Database check",
            severity="high" if duplicate else "low",
        )
    else:
        checks["duplicate_check"] = _check_result(
            "duplicate_check",
            "Duplicate invoice",
            "PASS",
            expected="invoice is not already in verified invoices",
            actual=False,
            explanation="No duplicate check was run because no database manager was provided.",
            evidence="No database",
            severity="low",
        )

    if po is None:
        checks["po_lookup"] = _check_result(
            "po_lookup",
            "PO lookup",
            "INCOMPLETE",
            expected=f"Approved purchase order for {po_number}",
            actual=None,
            explanation="No approved purchase order was found for the invoice PO number.",
            evidence="Database lookup",
            severity="high",
        )
    else:
        po_status = str(po.get("status") or "").strip().upper()
        if not po_status:
            po_approval_status = "INCOMPLETE"
        elif po_status == "APPROVED":
            po_approval_status = "PASS"
        else:
            po_approval_status = "FAIL"
        checks["po_approval"] = _check_result(
            "po_approval",
            "Purchase order approval",
            po_approval_status,
            expected="APPROVED",
            actual=po.get("status"),
            explanation="Only a purchase order explicitly marked APPROVED is eligible for a passing verification.",
            evidence="PO status",
            severity="high" if po_approval_status != "PASS" else "low",
        )

        vendor_match = vendor.lower() == str(po.get("vendor", "")).strip().lower()
        checks["vendor_match"] = _check_result(
            "vendor_match",
            "Vendor match",
            "PASS" if vendor_match else "FAIL",
            expected=str(po.get("vendor", "")).strip(),
            actual=vendor,
            explanation="The supplier on the invoice must match the approved vendor on the PO.",
            evidence="PO vendor",
            severity="high" if not vendor_match else "low",
        )

        po_match = po_number.upper() == str(po.get("po_number", "")).strip().upper()
        checks["po_number_match"] = _check_result(
            "po_number_match",
            "PO number match",
            "PASS" if po_match else "FAIL",
            expected=str(po.get("po_number", "")).strip(),
            actual=po_number,
            explanation="The invoice PO number must match the approved purchase order number.",
            evidence="PO number",
            severity="high" if not po_match else "low",
        )

        po_quantity = _as_decimal(po.get("quantity"))
        po_unit_price = _as_decimal(po.get("unit_price"))
        po_amount = _as_decimal(po.get("amount"))
        po_items = _po_lines(po)
        if po_items:
            po_line_quantities = []
            po_line_totals = []
            for item in po_items:
                qty = _as_decimal(item.get("quantity"))
                price = _as_decimal(item.get("unit_price"))
                total = _as_decimal(item.get("line_total"))
                if qty is not None:
                    po_line_quantities.append(qty)
                if total is None and qty is not None and price is not None:
                    total = qty * price
                if total is not None:
                    po_line_totals.append(total)
            if po_quantity is None and po_line_quantities:
                po_quantity = sum(po_line_quantities, Decimal("0"))
            if po_amount is None and po_line_totals:
                po_amount = sum(po_line_totals, Decimal("0"))
        if invoice_items:
            total_invoice_quantity = sum((value for value in [_as_decimal(item.get("quantity")) for item in invoice_items if _as_decimal(item.get("quantity")) is not None]), Decimal("0"))
            quantity_ok = po_quantity is not None and total_invoice_quantity <= po_quantity
        else:
            quantity_ok = quantity is not None and po_quantity is not None and quantity <= po_quantity
        checks["quantity_vs_po"] = _check_result(
            "quantity_vs_po",
            "Invoice quantity does not exceed PO quantity",
            "PASS" if quantity_ok else "FAIL",
            expected=str(po_quantity),
            actual=str(quantity),
            explanation="The invoiced quantity must not exceed the approved PO quantity.",
            evidence="PO quantity",
            severity="high" if not quantity_ok else "low",
        )

        if invoice_items and po.get("line_items"):
            line_prices = [_as_decimal(item.get("unit_price")) for item in po.get("line_items") if _as_decimal(item.get("unit_price")) is not None]
            if line_prices:
                unit_price_ok = all(
                    _as_decimal(item.get("unit_price")) == line_prices[idx]
                    for idx, item in enumerate(invoice_items)
                    if _as_decimal(item.get("unit_price")) is not None and idx < len(line_prices)
                )
            else:
                unit_price_ok = unit_price is not None and po_unit_price is not None and unit_price == po_unit_price
        else:
            unit_price_ok = unit_price is not None and po_unit_price is not None and unit_price == po_unit_price
        checks["unit_price_match"] = _check_result(
            "unit_price_match",
            "Unit price matches PO unit price",
            "PASS" if unit_price_ok else "FAIL",
            expected=str(po_unit_price),
            actual=str(unit_price),
            explanation="The invoice unit price must match the approved PO price.",
            evidence="PO unit price",
            severity="high" if not unit_price_ok else "low",
        )

        if invoice_items and po.get("line_items"):
            total_invoice_amount = Decimal("0")
            for item in invoice_items:
                line_total = _as_decimal(item.get("line_total"))
                if line_total is None:
                    qty = _as_decimal(item.get("quantity"))
                    price = _as_decimal(item.get("unit_price"))
                    if qty is not None and price is not None:
                        line_total = qty * price
                if line_total is not None:
                    total_invoice_amount += line_total
            amount_ok = po_amount is not None and total_invoice_amount == po_amount
        else:
            amount_ok = amount is not None and po_amount is not None and amount == po_amount
        checks["amount_match"] = _check_result(
            "amount_match",
            "Invoice amount matches PO amount",
            "PASS" if amount_ok else "FAIL",
            expected=str(po_amount),
            actual=str(amount),
            explanation="The invoice total must match the approved PO amount.",
            evidence="PO amount",
            severity="high" if not amount_ok else "low",
        )

    if po and po.get("line_items"):
        invoice_items = _build_line_items(invoice)
        po_items = _po_lines(po)
        po_lookup = { _normalize_text(item.get("description") or item.get("item") or "Item"): item for item in po_items }
        line_failures = []
        for idx, item in enumerate(invoice_items, start=1):
            desc = _normalize_text(item.get("description") or item.get("item") or f"Item {idx}")
            matched_po = po_lookup.get(desc)
            if matched_po is None:
                line_failures.append(f"Missing PO item: {item.get('description') or item.get('item') or 'Item'}")
                continue
            inv_qty = _as_decimal(item.get("quantity"))
            po_qty = _as_decimal(matched_po.get("quantity"))
            inv_price = _as_decimal(item.get("unit_price"))
            po_price = _as_decimal(matched_po.get("unit_price"))
            if inv_qty is not None and po_qty is not None and inv_qty > po_qty:
                line_failures.append(f"Excess quantity on {item.get('description') or 'line'}")
            if inv_price is not None and po_price is not None and inv_price != po_price:
                line_failures.append(f"Price mismatch on {item.get('description') or 'line'}")
        checks["line_item_reconciliation"] = _check_result(
            "line_item_reconciliation",
            "Line item reconciliation",
            "PASS" if not line_failures else "FAIL",
            expected="Every invoice line matches the approved PO item description, quantity, and price",
            actual=line_failures or "All invoice lines matched the PO",
            explanation="Each invoice line must match a PO line and stay within approved limits.",
            evidence="PO line-item comparison",
            severity="high" if line_failures else "low",
        )
    else:
        checks["line_item_reconciliation"] = _check_result(
            "line_item_reconciliation",
            "Line item reconciliation",
            "PASS",
            expected="No multi-line data was provided",
            actual="Single-line fallback",
            explanation="This invoice used the single-line fallback path.",
            evidence="Invoice summary",
            severity="low",
        )

    invoice_total = _as_decimal(invoice.get("amount"))
    if invoice_total is None:
        invoice_total = _as_decimal(invoice.get("total_amount"))
    calculated_total = Decimal("0")
    for item in invoice_items:
        line_total = _as_decimal(item.get("line_total"))
        if line_total is None:
            qty = _as_decimal(item.get("quantity"))
            price = _as_decimal(item.get("unit_price"))
            if qty is not None and price is not None:
                line_total = qty * price
        if line_total is not None:
            calculated_total += line_total
    checks["invoice_total_match"] = _check_result(
        "invoice_total_match",
        "Invoice total matches expected total",
        "PASS" if invoice_total is None or calculated_total == invoice_total else "FAIL",
        expected=str(invoice_total),
        actual=str(calculated_total),
        explanation="The subtotal of individual invoice lines must match the final invoice total when both are available.",
        evidence="Invoice line totals",
        severity="high" if invoice_total is not None and calculated_total != invoice_total else "low",
    )

    receipt_quantities = []
    if isinstance(receipts, dict):
        receipts = [receipts]
    for receipt in receipts or []:
        if isinstance(receipt, dict):
            receipt_quantities.append(_as_decimal(receipt.get("quantity")))

    total_received = sum((q for q in receipt_quantities if q is not None), Decimal("0"))
    if not receipts:
        checks["receipt_support"] = _check_result(
            "receipt_support",
            "Goods receipt support",
            "INCOMPLETE",
            expected="Goods receipt exists for the PO",
            actual=None,
            explanation="No goods receipt record was found to support the invoice quantity.",
            evidence="Goods receipt lookup",
            severity="high",
        )
    else:
        total_invoice_quantity = Decimal("0")
        for item in invoice_items:
            parsed_quantity = _as_decimal(item.get("quantity"))
            if parsed_quantity is not None:
                total_invoice_quantity += parsed_quantity
        if total_invoice_quantity == Decimal("0"):
            total_invoice_quantity = quantity or Decimal("0")
        receipt_item_totals = {}
        has_item_receipt_detail = False
        for receipt in receipts:
            if not isinstance(receipt, dict) or not receipt.get("line_items"):
                continue
            has_item_receipt_detail = True
            for item in receipt["line_items"]:
                description = _normalize_text(item.get("description") or item.get("item"))
                received_quantity = _as_decimal(item.get("quantity"))
                if description and received_quantity is not None:
                    receipt_item_totals[description] = receipt_item_totals.get(description, Decimal("0")) + received_quantity
        if has_item_receipt_detail and all(item.get("description") or item.get("item") for item in invoice_items):
            unsupported_items = []
            for item in invoice_items:
                description = _normalize_text(item.get("description") or item.get("item"))
                invoiced_quantity = _as_decimal(item.get("quantity"))
                received_quantity = receipt_item_totals.get(description, Decimal("0"))
                if invoiced_quantity is None or received_quantity < invoiced_quantity:
                    unsupported_items.append({
                        "item": item.get("description") or item.get("item"),
                        "invoiced": str(invoiced_quantity),
                        "received": str(received_quantity),
                    })
            quantity_supported = not unsupported_items
            actual_receipts = unsupported_items or "All invoice items have receipt support"
        else:
            quantity_supported = total_received >= total_invoice_quantity
            actual_receipts = str(total_received)
        checks["receipt_support"] = _check_result(
            "receipt_support",
            "Goods receipt support",
            "PASS" if quantity_supported else "FAIL",
            expected=f"at least {total_invoice_quantity}",
            actual=actual_receipts,
            explanation="Received quantities must cover invoice quantities; item-level receipts are compared by description when available.",
            evidence="Receipt quantity totals and item details",
            severity="high" if not quantity_supported else "low",
        )

    failed_checks = [item for item in checks.values() if item["status"] in {"FAIL", "INCOMPLETE"}]
    if any(item["status"] == "INCOMPLETE" for item in checks.values()):
        status = "INCOMPLETE"
    elif any(item["status"] == "FAIL" for item in checks.values()):
        status = "REVIEW REQUIRED"
    else:
        status = "PASSED"

    result = {
        "status": status,
        "checks": CheckCollection(checks),
        "exceptions": [item["name"] for item in checks.values() if item["status"] in {"FAIL", "INCOMPLETE"}],
        "summary": {
            "total_checks": len(checks),
            "failed": len(failed_checks),
        },
    }
    return result
