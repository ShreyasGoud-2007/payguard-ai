import argparse
from pathlib import Path
import tempfile

from paygard_ai.database import DatabaseManager
from paygard_ai.workflow import process_invoice_file


def run_demo(db_path: str | None = None, sample_file: str | None = None):
    if db_path is None:
        demo_directory = Path(tempfile.mkdtemp(prefix="paygard-cli-demo-"))
        db_path = str(demo_directory / "paygard_cli_demo.db")
    db = DatabaseManager(db_path)
    db.setup_database()
    db.insert_demo_data()

    sample_path = Path(sample_file) if sample_file else Path(__file__).resolve().parent / "sample_invoice.txt"
    result = process_invoice_file(sample_path, db)
    invoice = result["invoice"]
    report = result["report"]

    print("\n========== PAYGARD AI ==========")
    print("INVOICE VERIFICATION SYSTEM")
    print(f"Demo database: {db.db_path}")
    print("\n--- INVOICE READ FROM FILE ---")
    for key in ["vendor", "invoice_number", "invoice_date", "po_number", "quantity", "unit_price", "total_amount"]:
        print(f"{key}: {invoice.get(key)}")

    print(f"OCR status: {invoice.get('ocr_status')}")
    print(f"Extraction status: {invoice.get('validation_state')}")
    if invoice.get("error"):
        print(f"Extraction error: {invoice['error']}")

    print("\n========== VERIFICATION REPORT ==========")
    for key, check in report["checks"].items():
        print(f"{key}: {check['status']} | {check['explanation']}")
    print("\n--- EXCEPTIONS ---")
    if report["exceptions"]:
        for exception in report["exceptions"]:
            print("WARNING:", exception)
    else:
        print("No exceptions found.")
    print("\n--- FINAL STATUS ---")
    print(report["status"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify a vendor invoice using PO and goods receipt data.")
    parser.add_argument("--db-path", default=None, help="Optional SQLite database path for a clean demo run.")
    parser.add_argument("--sample-file", default=None, help="Optional invoice file path for a fresh sample file.")
    args = parser.parse_args()
    run_demo(args.db_path, args.sample_file)
