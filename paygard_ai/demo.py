"""Run a complete, synthetic PayGard invoice workflow demonstration."""

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any

from . import config
from .database import DatabaseManager
from .extraction import Image, check_ocr_available
from .workflow import process_invoice_file


SYNTHETIC_VENDOR = "SYNTHETIC DEMO SUPPLY CO"
SYNTHETIC_ITEM = "Synthetic Widget"
EXPECTED_STATUSES = {
    "matching": "PASSED",
    "amount_mismatch": "REVIEW REQUIRED",
    "missing_information": "INCOMPLETE",
    "duplicate": "REVIEW REQUIRED",
    "po_not_approved": "REVIEW REQUIRED",
    "insufficient_receipt": "REVIEW REQUIRED",
}


def _invoice_text(
    invoice_number: str,
    po_number: str | None,
    *,
    unit_price: int,
    line_total: int,
    total: int,
    include_required_fields: bool = True,
) -> str:
    lines = [
        SYNTHETIC_VENDOR,
        "SYNTHETIC INVOICE - DEMONSTRATION ONLY",
        f"Invoice Number: {invoice_number}",
    ]
    if include_required_fields:
        lines.extend([
            "Invoice Date: 2026-09-30",
            f"PO Number: {po_number}",
            "Currency: USD",
            "",
            "Description       Qty       Unit Price       Line Total",
            f"{SYNTHETIC_ITEM}       2       {unit_price:.2f}       {line_total:.2f}",
            "",
            f"Subtotal: {line_total:.2f}",
            "Tax: 0.00",
        ])
    else:
        lines.extend([
            "",
            "PO number and line item intentionally omitted for this incomplete scenario.",
        ])
    lines.append(f"Total Amount: {total:.2f}")
    return "\n".join(lines) + "\n"


def _write_invoice(text: str, path: Path, use_ocr: bool) -> None:
    if not use_ocr:
        path.write_text(text, encoding="utf-8")
        return
    if Image is None:
        raise RuntimeError("Pillow is unavailable; cannot create OCR demo invoice images.")
    from PIL import ImageDraw, ImageFont

    font = ImageFont.load_default(size=38)
    lines = text.splitlines()
    line_height = 70
    image = Image.new("RGB", (2200, max(900, 180 + len(lines) * line_height)), "white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((100, 100 + index * line_height), line, fill="black", font=font)
    image.save(path, dpi=(300, 300))


def _add_reference_records(manager: DatabaseManager) -> None:
    definitions = [
        ("SYNTH-PO-MATCH", "APPROVED", 100.0, 2),
        ("SYNTH-PO-AMOUNT", "APPROVED", 100.0, 2),
        ("SYNTH-PO-PENDING", "PENDING", 100.0, 2),
        ("SYNTH-PO-RECEIPT", "APPROVED", 100.0, 2),
    ]
    for po_number, status, amount, quantity in definitions:
        manager.add_purchase_order({
            "po_number": po_number,
            "vendor": SYNTHETIC_VENDOR,
            "quantity": quantity,
            "unit_price": 50.0,
            "amount": amount,
            "status": status,
            "line_items": [{
                "description": SYNTHETIC_ITEM,
                "quantity": quantity,
                "unit_price": 50.0,
                "line_total": amount,
            }],
            "data_source": "SYNTHETIC_DEMO",
            "source_record_id": f"SYNTHETIC-DEMO:{po_number}",
            "source_provenance": {"fixture": "synthetic workflow demonstration"},
        })

    for receipt_number, po_number, quantity in (
        ("SYNTH-GR-MATCH", "SYNTH-PO-MATCH", 2),
        ("SYNTH-GR-AMOUNT", "SYNTH-PO-AMOUNT", 2),
        ("SYNTH-GR-PENDING", "SYNTH-PO-PENDING", 2),
        ("SYNTH-GR-SHORT", "SYNTH-PO-RECEIPT", 1),
    ):
        manager.add_goods_receipt({
            "receipt_number": receipt_number,
            "po_number": po_number,
            "quantity": quantity,
            "received_on": "2026-09-30",
            "line_items": [{"description": SYNTHETIC_ITEM, "quantity": quantity}],
            "data_source": "SYNTHETIC_DEMO",
            "source_record_id": f"SYNTHETIC-DEMO:{receipt_number}",
            "source_provenance": {"fixture": "synthetic workflow demonstration"},
        })


def _render_result(name: str, result: dict[str, Any]) -> None:
    invoice = result["invoice"]
    report = result["report"]
    latest_upload = result["latest_upload"]
    print(f"\n=== {name.replace('_', ' ').title()} ===")
    print("File:", invoice.get("source_file"))
    print("OCR:", invoice.get("ocr_status"))
    print("Extraction:", invoice.get("validation_state"))
    for key in ("invoice_number", "vendor", "invoice_date", "po_number", "line_items", "total_amount"):
        print(f"{key}: {invoice.get(key)}")
    print("Missing fields:", invoice.get("missing_fields", []))
    print("Uncertain fields:", invoice.get("uncertain_fields", []))
    print("Validation issues:", invoice.get("validation_issues", []))
    print("Verification checks:")
    for key, check in report["checks"].items():
        print(f"  {key}: {check['status']} | expected={check.get('expected')} | actual={check.get('actual')}")
    explanation = result["risk_analysis"]["ai_explanation"]
    print("Explanation source:", explanation["source"])
    print("Explanation:", explanation["summary"])
    print("Final status:", result["status"])
    print("Persisted upload status:", latest_upload["final_status"])


def run_synthetic_demo(
    output_dir: str | Path | None = None,
    *,
    use_ocr: bool = False,
    use_ai: bool = False,
) -> dict[str, Any]:
    original_ai_provider = config.AI_PROVIDER
    if not use_ai:
        config.AI_PROVIDER = "disabled"
    try:
        return _run_synthetic_demo(output_dir, use_ocr=use_ocr)
    finally:
        config.AI_PROVIDER = original_ai_provider


def _run_synthetic_demo(output_dir: str | Path | None, *, use_ocr: bool) -> dict[str, Any]:
    if use_ocr:
        available, message = check_ocr_available()
        if not available:
            raise RuntimeError(f"Real OCR demo cannot run: {message}")

    if output_dir is None:
        root = Path(tempfile.mkdtemp(prefix="paygard-synthetic-workflow-demo-"))
    else:
        root = Path(output_dir).expanduser().resolve()
        if root.exists() and any(root.iterdir()):
            raise FileExistsError(f"Refusing to reuse non-empty demo directory: {root}")
        root.mkdir(parents=True, exist_ok=True)

    database_path = root / "paygard_synthetic_demo.db"
    if database_path.exists():
        raise FileExistsError(f"Refusing to overwrite an existing demo database: {database_path}")
    invoice_directory = root / "invoices"
    invoice_directory.mkdir()

    manager = DatabaseManager(str(database_path))
    manager.setup_database()
    _add_reference_records(manager)

    extension = ".png" if use_ocr else ".txt"
    invoice_texts = {
        "matching": _invoice_text("SYNTH-INV-MATCH", "SYNTH-PO-MATCH", unit_price=50, line_total=100, total=100),
        "amount_mismatch": _invoice_text("SYNTH-INV-AMOUNT", "SYNTH-PO-AMOUNT", unit_price=60, line_total=120, total=120),
        "missing_information": _invoice_text("SYNTH-INV-INCOMPLETE", None, unit_price=0, line_total=0, total=100, include_required_fields=False),
        "po_not_approved": _invoice_text("SYNTH-INV-PENDING", "SYNTH-PO-PENDING", unit_price=50, line_total=100, total=100),
        "insufficient_receipt": _invoice_text("SYNTH-INV-SHORT", "SYNTH-PO-RECEIPT", unit_price=50, line_total=100, total=100),
    }
    invoice_paths = {}
    for name, text in invoice_texts.items():
        path = invoice_directory / f"{name}{extension}"
        _write_invoice(text, path, use_ocr)
        invoice_paths[name] = path

    scenario_paths = [
        ("matching", invoice_paths["matching"]),
        ("amount_mismatch", invoice_paths["amount_mismatch"]),
        ("missing_information", invoice_paths["missing_information"]),
        ("duplicate", invoice_paths["matching"]),
        ("po_not_approved", invoice_paths["po_not_approved"]),
        ("insufficient_receipt", invoice_paths["insufficient_receipt"]),
    ]
    scenarios = {}
    for scenario_name, path in scenario_paths:
        workflow_result = process_invoice_file(path, manager)
        latest_upload = manager.get_upload_records(1)[0]
        expected_status = EXPECTED_STATUSES[scenario_name]
        if workflow_result["status"] != expected_status:
            raise AssertionError(
                f"{scenario_name} expected {expected_status}, got {workflow_result['status']}"
            )
        if latest_upload["final_status"] != expected_status:
            raise AssertionError(f"{scenario_name} persisted the wrong status")
        workflow_result["latest_upload"] = latest_upload
        scenarios[scenario_name] = workflow_result

    connection = manager.connect()
    try:
        audit_count = connection.execute(
            "SELECT COUNT(*) FROM audit_logs WHERE event_type = 'invoice_workflow'"
        ).fetchone()[0]
    finally:
        connection.close()
    if audit_count != len(scenario_paths):
        raise AssertionError(f"Expected {len(scenario_paths)} workflow audit events, got {audit_count}")

    for name, result in scenarios.items():
        _render_result(name, result)
    print("\nSynthetic reference rows:", manager.data_source_summary())
    print("Workflow uploads persisted:", len(manager.get_upload_records(20)))
    print("Workflow audit events:", audit_count)
    print("Human decisions are not auto-generated; reviewers must record them in the dashboard.")
    print("No payment is authorized or initiated by this demo.")
    print("Demo directory:", root)
    print("Demo database:", database_path)
    print("Invoice files:", invoice_directory)
    print("\nTo open this exact database in the dashboard (PowerShell):")
    print(f'$env:DB_PATH = "{database_path}"')
    print('$env:PAYGARD_SKIP_DEMO_SEED = "1"')
    print('$env:AI_PROVIDER = "disabled"')
    print(".\\.venv\\Scripts\\python.exe -m streamlit run app.py")
    return {
        "output_dir": str(root),
        "database_path": str(database_path),
        "invoice_directory": str(invoice_directory),
        "scenarios": scenarios,
        "audit_count": audit_count,
        "use_ocr": use_ocr,
    }


def main():
    parser = argparse.ArgumentParser(description="Run six isolated synthetic PayGard workflow scenarios.")
    parser.add_argument("--output-dir", default=None, help="New or empty directory for generated files and a separate demo DB.")
    parser.add_argument("--ocr", action="store_true", help="Render synthetic invoices as PNG and require real Tesseract OCR.")
    parser.add_argument("--use-ai", action="store_true", help="Allow the configured optional AI provider; this may make billable API calls.")
    args = parser.parse_args()
    try:
        run_synthetic_demo(args.output_dir, use_ocr=args.ocr, use_ai=args.use_ai)
    except (FileExistsError, RuntimeError, AssertionError) as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()