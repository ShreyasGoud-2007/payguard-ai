
from pathlib import Path

from paygard_ai.extraction import extract_invoice_file

invoice = extract_invoice_file(str(Path(__file__).resolve().parent / "sample_invoice.txt"))


if __name__ == "__main__":
    print("========== PAYGARD AI ==========")
    print("INVOICE FIELD EXTRACTION")
    print()
    print(invoice)
    print("\nStatus:", invoice.get("validation_state"))
