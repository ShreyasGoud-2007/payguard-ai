import json
from unittest.mock import patch

import pytest
from PIL import Image

from paygard_ai.database import DatabaseManager
from paygard_ai.extraction import check_ocr_available, extract_invoice_file, parse_invoice_text
from paygard_ai.workflow import process_invoice_file


INVOICE_TEXT = """ABC Traders
Invoice Number: OCR-100
Invoice Date: 2026-09-30
PO Number: PO500
Currency: USD
Laptop 2 100.00 200.00
Mouse 4 25.00 100.00
Subtotal: 300.00
Tax: 0.00
Total Amount: 300.00
"""


def make_manager(tmp_path):
    manager = DatabaseManager(str(tmp_path / "ocr-test.db"))
    manager.setup_database()
    manager.add_purchase_order({
        "po_number": "PO500",
        "vendor": "ABC Traders",
        "quantity": 6,
        "unit_price": 50,
        "amount": 300,
        "line_items": [
            {"description": "Laptop", "quantity": 2, "unit_price": 100},
            {"description": "Mouse", "quantity": 4, "unit_price": 25},
        ],
    })
    manager.add_goods_receipt({
        "receipt_number": "GR-OCR",
        "po_number": "PO500",
        "quantity": 6,
        "line_items": [
            {"description": "Laptop", "quantity": 2},
            {"description": "Mouse", "quantity": 4},
        ],
    })
    return manager


@pytest.mark.parametrize("suffix", ["png", "jpg", "jpeg"])
def test_image_ocr_extracts_invoice_fields(tmp_path, suffix):
    image_path = tmp_path / f"invoice.{suffix}"
    Image.new("RGB", (200, 100), "white").save(image_path)

    with patch("paygard_ai.extraction.check_ocr_available", return_value=(True, "Tesseract ready")), patch(
        "paygard_ai.extraction.pytesseract.image_to_string", return_value=INVOICE_TEXT
    ):
        invoice = extract_invoice_file(image_path)

    assert invoice["ocr_status"] == "COMPLETED"
    assert invoice["invoice_number"] == "OCR-100"
    assert invoice["line_items"] == [
        {"description": "Laptop", "quantity": 2.0, "unit_price": 100.0, "line_total": 200.0},
        {"description": "Mouse", "quantity": 4.0, "unit_price": 25.0, "line_total": 100.0},
    ]
    assert invoice["raw_ocr_text"] == INVOICE_TEXT


def test_scanned_multipage_pdf_ocr_preserves_page_order(tmp_path):
    from io import BytesIO

    fitz = pytest.importorskip("pymupdf")
    pdf_path = tmp_path / "pages.pdf"
    document = fitz.open()
    for _ in range(2):
        page = document.new_page()
        raster = BytesIO()
        Image.new("RGB", (300, 200), "white").save(raster, format="PNG")
        page.insert_image(page.rect, stream=raster.getvalue())
    document.save(pdf_path)
    document.close()

    with patch("paygard_ai.extraction.check_ocr_available", return_value=(True, "Tesseract ready")), patch(
        "paygard_ai.extraction.pytesseract.image_to_string",
        side_effect=["Invoice Number: PAGE-1", "Total Amount: 42.00"],
    ):
        invoice = extract_invoice_file(pdf_path)

    assert invoice["page_count"] == 2
    assert [page["page_number"] for page in invoice["pages"]] == [1, 2]
    assert invoice["raw_ocr_text"].index("PAGE-1") < invoice["raw_ocr_text"].index("42.00")


def test_empty_image_is_incomplete_without_crashing(tmp_path):
    image_path = tmp_path / "blank.png"
    Image.new("RGB", (100, 100), "white").save(image_path)

    with patch("paygard_ai.extraction.check_ocr_available", return_value=(True, "Tesseract ready")), patch(
        "paygard_ai.extraction.pytesseract.image_to_string", return_value=""
    ):
        invoice = extract_invoice_file(image_path)

    assert invoice["ocr_status"] == "EMPTY"
    assert invoice["validation_state"] == "INCOMPLETE"
    assert not invoice["ready_for_verification"]


def test_unsupported_file_type_is_reported(tmp_path):
    path = tmp_path / "invoice.docx"
    path.write_bytes(b"unsupported")
    with pytest.raises(ValueError, match="Unsupported file type"):
        extract_invoice_file(path)


def test_missing_tesseract_is_reported_clearly():
    with patch("paygard_ai.extraction.pytesseract.get_tesseract_version", side_effect=RuntimeError("not found")):
        available, message = check_ocr_available()
    assert available is False
    assert "Tesseract" in message


def test_tesseract_environment_variable_configures_executable(monkeypatch):
    from paygard_ai import extraction

    configured_path = r"D:\Tools\Tesseract\tesseract.exe"
    monkeypatch.setenv("TESSERACT_CMD", configured_path)
    monkeypatch.setattr(extraction.Path, "is_file", lambda self: str(self) == configured_path)
    with patch("paygard_ai.extraction.pytesseract.get_tesseract_version", return_value="5.4.0"):
        available, _ = check_ocr_available()

    assert available is True
    assert extraction.pytesseract.pytesseract.tesseract_cmd == configured_path


def test_windows_tesseract_install_path_is_used_as_fallback(monkeypatch):
    from paygard_ai import extraction

    monkeypatch.delenv("TESSERACT_CMD", raising=False)
    expected_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    monkeypatch.setattr(extraction.Path, "is_file", lambda self: str(self) == expected_path)
    with patch("paygard_ai.extraction.pytesseract.get_tesseract_version", return_value="5.4.0"):
        available, _ = check_ocr_available()

    assert available is True
    assert extraction.pytesseract.pytesseract.tesseract_cmd == expected_path


def test_invalid_tesseract_environment_path_is_reported(monkeypatch):
    from paygard_ai import extraction

    configured_path = r"Z:\Missing\tesseract.exe"
    monkeypatch.setenv("TESSERACT_CMD", configured_path)
    monkeypatch.setattr(extraction.Path, "is_file", lambda self: False)

    available, message = check_ocr_available()

    assert available is False
    assert configured_path in message


def test_ambiguous_financial_value_is_not_guessed():
    invoice = parse_invoice_text(INVOICE_TEXT.replace("Total Amount: 300.00", "Total Amount: 3OO.OO"))
    assert invoice["total_amount"] is None
    assert "total_amount" in invoice["uncertain_fields"]
    assert invoice["validation_state"] == "REVIEW REQUIRED"


def test_ambiguous_date_and_confused_table_row_need_review():
    text = INVOICE_TEXT.replace("2026-09-30", "01/02/2026").replace(
        "Laptop 2 100.00 200.00", "Laptop 2 1OO.OO 200.00"
    )
    invoice = parse_invoice_text(text)
    assert invoice["invoice_date"] is None
    assert "invoice_date" in invoice["uncertain_fields"]
    assert "line_items" in invoice["uncertain_fields"]
    assert invoice["validation_state"] == "REVIEW REQUIRED"


def test_line_quantity_summary_mismatch_needs_review():
    text = INVOICE_TEXT.replace("Invoice Date: 2026-09-30", "Invoice Date: 2026-09-30\nQuantity: 7")
    invoice = parse_invoice_text(text)
    assert "quantity" in invoice["uncertain_fields"]
    assert any("summary does not match" in issue for issue in invoice["validation_issues"])
    assert invoice["validation_state"] == "REVIEW REQUIRED"


def test_prose_about_missing_po_and_items_does_not_create_candidates():
    text = "ABC Traders\nInvoice Number: OCR-INCOMPLETE\nTotal Amount: 25.00\nPO number and item details are missing."
    invoice = parse_invoice_text(text)
    assert invoice["po_number"] is None
    assert invoice["line_items"] == []
    assert "po_number" in invoice["missing_fields"]
    assert "line_items" in invoice["missing_fields"]
    assert invoice["validation_state"] == "INCOMPLETE"


def test_split_table_row_is_reassembled_from_adjacent_values():
    wrapped_text = INVOICE_TEXT.replace("Laptop 2 100.00 200.00", "Laptop 2 100.00\n200.00")
    invoice = parse_invoice_text(wrapped_text)
    assert invoice["line_items"][0] == {
        "description": "Laptop",
        "quantity": 2.0,
        "unit_price": 100.0,
        "line_total": 200.0,
    }
    assert invoice["validation_state"] == "READY"


def test_ocr_result_runs_verification_and_is_saved(tmp_path):
    manager = make_manager(tmp_path)
    image_path = tmp_path / "matching.png"
    Image.new("RGB", (200, 100), "white").save(image_path)

    with patch("paygard_ai.extraction.check_ocr_available", return_value=(True, "Tesseract ready")), patch(
        "paygard_ai.extraction.pytesseract.image_to_string", return_value=INVOICE_TEXT
    ):
        result = process_invoice_file(image_path, manager)

    assert result["status"] == "PASSED"
    assert result["report"]["status"] == "PASSED"
    assert result["risk_analysis"]["verification_status"] == "PASSED"
    assert result["risk_analysis"]["ai_explanation"]["ai_used"] is False
    assert result["risk_analysis"]["ai_explanation"]["source"] == "deterministic_fallback"
    assert manager.invoice_exists("OCR-100")
    saved = manager.get_invoice_record("OCR-100")
    assert saved["verification_status"] == "PASSED"
    assert "raw_ocr_text" in saved["extraction"]
    assert manager.get_verification_results("OCR-100")
    persisted_report = json.loads(manager.get_upload_records()[0]["result_json"])
    assert persisted_report["status"] == "PASSED"
    assert persisted_report["risk_analysis"]["ai_explanation"]["source"] == "deterministic_fallback"


def test_ocr_quantity_mismatch_is_review_required_and_persisted(tmp_path):
    manager = make_manager(tmp_path)
    image_path = tmp_path / "mismatch.png"
    Image.new("RGB", (200, 100), "white").save(image_path)
    mismatched_text = INVOICE_TEXT.replace("Laptop 2 100.00 200.00", "Laptop 3 100.00 300.00").replace(
        "Subtotal: 300.00", "Subtotal: 400.00"
    ).replace("Total Amount: 300.00", "Total Amount: 400.00")

    with patch("paygard_ai.extraction.check_ocr_available", return_value=(True, "Tesseract ready")), patch(
        "paygard_ai.extraction.pytesseract.image_to_string", return_value=mismatched_text
    ):
        result = process_invoice_file(image_path, manager)

    assert result["status"] == "REVIEW REQUIRED"
    assert any(check["status"] == "FAIL" for check in result["report"]["checks"])
    assert manager.get_invoice_record("OCR-100")["verification_status"] == "REVIEW REQUIRED"


def test_incomplete_and_duplicate_ocr_submissions_do_not_pass(tmp_path):
    manager = make_manager(tmp_path)
    image_path = tmp_path / "incomplete.png"
    Image.new("RGB", (200, 100), "white").save(image_path)
    incomplete_text = "ABC Traders\nInvoice Number: OCR-101\nTotal Amount: 40.00"

    with patch("paygard_ai.extraction.check_ocr_available", return_value=(True, "Tesseract ready")), patch(
        "paygard_ai.extraction.pytesseract.image_to_string", return_value=incomplete_text
    ):
        incomplete = process_invoice_file(image_path, manager)
    assert incomplete["status"] == "INCOMPLETE"

    image_path = tmp_path / "duplicate.png"
    Image.new("RGB", (200, 100), "white").save(image_path)
    with patch("paygard_ai.extraction.check_ocr_available", return_value=(True, "Tesseract ready")), patch(
        "paygard_ai.extraction.pytesseract.image_to_string", return_value=INVOICE_TEXT
    ):
        first = process_invoice_file(image_path, manager)
        duplicate = process_invoice_file(image_path, manager)
    assert first["status"] == "PASSED"
    assert duplicate["status"] == "REVIEW REQUIRED"
    assert duplicate["report"]["checks"]["duplicate_check"]["status"] == "FAIL"


def test_ocr_failure_is_saved_as_safe_review_status(tmp_path):
    manager = make_manager(tmp_path)
    image_path = tmp_path / "failure.jpg"
    Image.new("RGB", (100, 100), "white").save(image_path)
    with patch("paygard_ai.extraction.check_ocr_available", return_value=(False, "Tesseract is not installed")):
        result = process_invoice_file(image_path, manager)
    assert result["status"] == "INCOMPLETE"
    assert "Tesseract is not installed" in result["invoice"]["error"]
    assert manager.get_upload_records()