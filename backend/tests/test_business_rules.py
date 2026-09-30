from app.services.validation import evaluate_invoice


def test_clean_invoice_is_payable():
    result = evaluate_invoice(
        {
            "invoice_number": "INV-1001",
            "vendor": {"vendor_name": "ABC Technologies Pvt Ltd", "status": "ACTIVE", "risk_level": "LOW"},
            "po": {"po_number": "PO-1001", "vendor_name": "ABC Technologies Pvt Ltd", "status": "APPROVED"},
            "grn": {"grn_number": "GRN-1001", "status": "RECEIVED", "quantity_received": 100},
            "invoice_items": [{"quantity": 100, "unit_price": 850.0}],
            "invoice_total": 85000.0,
            "tax_amount": 0.0,
            "duplicate_of": None,
        }
    )

    assert result["status"] == "APPROVED"
    assert result["risk_level"] == "LOW"
    assert result["payable_eligible"] is True
    assert result["exception_codes"] == []


def test_quantity_mismatch_invoice_is_not_payable():
    result = evaluate_invoice(
        {
            "invoice_number": "INV-1002",
            "vendor": {"vendor_name": "ABC Technologies Pvt Ltd", "status": "ACTIVE", "risk_level": "LOW"},
            "po": {"po_number": "PO-1002", "vendor_name": "ABC Technologies Pvt Ltd", "status": "APPROVED"},
            "grn": {"grn_number": "GRN-1002", "status": "RECEIVED", "quantity_received": 40},
            "invoice_items": [{"quantity": 60, "unit_price": 1200.0}],
            "invoice_total": 72000.0,
            "tax_amount": 0.0,
            "duplicate_of": None,
        }
    )

    assert result["status"] == "UNDER_REVIEW"
    assert result["risk_level"] == "HIGH"
    assert result["payable_eligible"] is False
    assert "QUANTITY_MISMATCH" in result["exception_codes"]


def test_price_mismatch_invoice_is_not_payable():
    result = evaluate_invoice(
        {
            "invoice_number": "INV-1003",
            "vendor": {"vendor_name": "ABC Technologies Pvt Ltd", "status": "ACTIVE", "risk_level": "LOW"},
            "po": {"po_number": "PO-1003", "vendor_name": "ABC Technologies Pvt Ltd", "status": "APPROVED", "quantity": 20, "unit_price": 950.0},
            "grn": {"grn_number": "GRN-1003", "status": "RECEIVED", "quantity_received": 20},
            "invoice_items": [{"quantity": 20, "unit_price": 959.0}],
            "invoice_total": 19180.0,
            "tax_amount": 0.0,
            "duplicate_of": None,
        }
    )

    assert result["status"] == "UNDER_REVIEW"
    assert result["risk_level"] == "MEDIUM"
    assert result["payable_eligible"] is False
    assert "PRICE_MISMATCH" in result["exception_codes"]


def test_duplicate_invoice_is_reviewed():
    result = evaluate_invoice(
        {
            "invoice_number": "INV-1004",
            "vendor": {"vendor_name": "ABC Technologies Pvt Ltd", "status": "ACTIVE", "risk_level": "LOW"},
            "po": {"po_number": "PO-1001", "vendor_name": "ABC Technologies Pvt Ltd", "status": "APPROVED"},
            "grn": {"grn_number": "GRN-1001", "status": "RECEIVED", "quantity_received": 100},
            "invoice_items": [{"quantity": 100, "unit_price": 850.0}],
            "invoice_total": 85000.0,
            "tax_amount": 0.0,
            "duplicate_of": "INV-1001",
        }
    )

    assert result["status"] == "UNDER_REVIEW"
    assert result["risk_level"] == "HIGH"
    assert result["payable_eligible"] is False
    assert "DUPLICATE_INVOICE" in result["exception_codes"]
