import mimetypes
from pathlib import Path

from .ai_provider import generate_ai_explanation
from .extraction import extract_invoice_file, parse_invoice_text
from .risk_analysis import analyze_invoice_risk
from .verification import verify_invoice


def _failed_extraction(path: Path, message: str):
    invoice = parse_invoice_text("")
    invoice.update({
        "source_file": str(path),
        "raw_ocr_text": "",
        "pages": [],
        "page_count": 0,
        "ocr_status": "ERROR",
        "ocr_errors": [message],
        "detected_format": path.suffix.lower().lstrip(".").upper(),
        "error": message,
        "validation_state": "INCOMPLETE",
        "ready_for_verification": False,
        "validation_issues": [message],
    })
    return invoice


def process_invoice_file(
    file_path,
    db_manager,
    original_name: str | None = None,
    stored_name: str | None = None,
    mime_type: str | None = None,
    file_size: int | None = None,
):
    path = Path(file_path)
    try:
        invoice = extract_invoice_file(path)
    except Exception as exc:
        invoice = _failed_extraction(path, str(exc))

    po_number = invoice.get("po_number") or ""
    po = db_manager.get_purchase_order(po_number)
    receipts = db_manager.get_goods_receipts(po_number)
    report = verify_invoice(invoice, po, receipts, db_manager)

    extraction_state = invoice.get("validation_state", "INCOMPLETE")
    if extraction_state == "INCOMPLETE":
        final_status = "INCOMPLETE"
    elif extraction_state == "REVIEW REQUIRED" and report["status"] == "PASSED":
        final_status = "REVIEW REQUIRED"
    else:
        final_status = report["status"]

    if extraction_state != "READY":
        checks = report["checks"]
        checks["extraction_validation"] = {
            "key": "extraction_validation",
            "name": "Extraction quality",
            "status": extraction_state,
            "expected": "Required fields are extracted with no unresolved critical ambiguity",
            "actual": {
                "missing_fields": invoice.get("missing_fields", []),
                "uncertain_fields": invoice.get("uncertain_fields", []),
                "issues": invoice.get("validation_issues", []),
            },
            "explanation": "OCR/extraction quality is separate from verification confidence; uncertain or missing invoice data cannot produce a pass.",
            "evidence": "Structured extraction validation",
            "severity": "high",
        }

    report["status"] = final_status
    report["extraction_state"] = extraction_state
    report["summary"]["total_checks"] = len(report["checks"])
    report["summary"]["failed"] = sum(1 for check in report["checks"] if check["status"] != "PASS")
    report["exceptions"] = [
        check["name"] for check in report["checks"] if check["status"] in {"FAIL", "INCOMPLETE", "REVIEW REQUIRED"}
    ]
    analysis = analyze_invoice_risk(invoice, report)
    analysis["ai_explanation"] = generate_ai_explanation(invoice, report, analysis)
    report["risk_analysis"] = analysis

    resolved_original_name = original_name or path.name
    resolved_stored_name = stored_name or path.name
    resolved_mime_type = mime_type or mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if file_size is None:
        try:
            file_size = path.stat().st_size
        except OSError:
            file_size = 0
    db_manager.save_workflow_result(
        invoice,
        report,
        resolved_original_name,
        resolved_stored_name,
        str(path),
        resolved_mime_type,
        file_size,
    )
    return {"invoice": invoice, "report": report, "status": final_status, "risk_analysis": analysis}