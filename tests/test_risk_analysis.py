from copy import deepcopy

from paygard_ai.risk_analysis import analyze_invoice_risk


def check(key, name, status, *, expected=None, actual=None, evidence=None, explanation=""):
    return {
        "key": key,
        "name": name,
        "status": status,
        "expected": expected,
        "actual": actual,
        "evidence": evidence,
        "explanation": explanation,
        "severity": "high" if status != "PASS" else "low",
    }


def test_passed_invoice_explanation_uses_verification_evidence():
    report = {
        "status": "PASSED",
        "checks": {
            "po_approval": check("po_approval", "PO approval", "PASS", expected="APPROVED", actual="APPROVED", evidence="PO status"),
            "amount_match": check("amount_match", "Amount match", "PASS", expected="100.00", actual="100.00", evidence="PO amount"),
        },
    }

    analysis = analyze_invoice_risk({"invoice_number": "INV-1"}, report)

    assert analysis["verification_status"] == "PASSED"
    assert analysis["analysis_method"] == "deterministic_fallback"
    assert analysis["ai_used"] is False
    assert [item["key"] for item in analysis["passed_checks"]] == ["po_approval", "amount_match"]
    assert analysis["failed_checks"] == []
    assert "PASSED" in analysis["summary"]


def test_failed_po_or_receipt_check_includes_actual_evidence():
    report = {
        "status": "REVIEW REQUIRED",
        "checks": {
            "po_approval": check("po_approval", "PO approval", "FAIL", expected="APPROVED", actual="PENDING", evidence="PO status"),
            "receipt_support": check("receipt_support", "Goods receipt support", "FAIL", expected="at least 5", actual="3", evidence="Receipt total"),
        },
    }

    analysis = analyze_invoice_risk({}, report)

    assert [item["key"] for item in analysis["failed_checks"]] == ["po_approval", "receipt_support"]
    assert analysis["warnings"][0]["actual"] == "PENDING"
    assert analysis["warnings"][1]["evidence"] == "Receipt total"
    assert len(analysis["review_guidance"]) == 2


def test_incomplete_extraction_lists_missing_and_uncertain_fields():
    invoice = {
        "missing_fields": ["po_number"],
        "uncertain_fields": ["total_amount"],
        "validation_issues": ["total amount is ambiguous: 3OO.OO"],
    }
    report = {
        "status": "INCOMPLETE",
        "checks": {
            "po_lookup": check("po_lookup", "PO lookup", "INCOMPLETE", expected="PO", actual=None, evidence="Database lookup"),
        },
    }

    analysis = analyze_invoice_risk(invoice, report)

    assert analysis["verification_status"] == "INCOMPLETE"
    assert "po_number" in analysis["missing_information"]
    assert "Uncertain field: total_amount" in analysis["missing_information"]
    assert "total amount is ambiguous: 3OO.OO" in analysis["missing_information"]
    assert analysis["incomplete_checks"][0]["key"] == "po_lookup"


def test_multiple_warnings_are_separated_by_check_outcome():
    report = {
        "status": "INCOMPLETE",
        "checks": {
            "vendor_match": check("vendor_match", "Vendor match", "FAIL", expected="A", actual="B", evidence="PO vendor"),
            "receipt_support": check("receipt_support", "Receipt support", "INCOMPLETE", expected="receipt exists", actual=None, evidence="Receipt lookup"),
            "duplicate_check": check("duplicate_check", "Duplicate invoice", "PASS", expected=False, actual=False, evidence="Database check"),
        },
    }

    analysis = analyze_invoice_risk({}, report)

    assert len(analysis["failed_checks"]) == 1
    assert len(analysis["incomplete_checks"]) == 1
    assert len(analysis["passed_checks"]) == 1
    assert len(analysis["warnings"]) == 2


def test_missing_check_evidence_is_reported_as_insufficient():
    analysis = analyze_invoice_risk({"missing_fields": [], "uncertain_fields": []}, {"status": "REVIEW REQUIRED", "checks": {}})

    assert analysis["insufficient_evidence"] is True
    assert any("No verification check evidence was provided" in item for item in analysis["limitations"])
    assert analysis["review_guidance"]


def test_fallback_is_labeled_and_cannot_change_verification_result():
    report = {
        "status": "REVIEW REQUIRED",
        "checks": {
            "amount_match": check("amount_match", "Amount match", "FAIL", expected=100, actual=120, evidence="PO amount"),
        },
    }
    original_report = deepcopy(report)

    analysis = analyze_invoice_risk({}, report)

    assert analysis["analysis_method"] == "deterministic_fallback"
    assert analysis["ai_used"] is False
    assert analysis["verification_status"] == "REVIEW REQUIRED"
    assert report == original_report