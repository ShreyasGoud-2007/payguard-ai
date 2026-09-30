import io
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

try:
    import pymupdf as fitz
except Exception:  # pragma: no cover
    fitz = None

try:
    from PIL import Image
except Exception:  # pragma: no cover
    Image = None

try:
    import pytesseract
except Exception:  # pragma: no cover
    pytesseract = None

SUPPORTED_EXTENSIONS = {".txt", ".pdf", ".png", ".jpg", ".jpeg"}
WINDOWS_TESSERACT_PATH = Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe")


def _configure_tesseract():
    if pytesseract is None:
        return None, "Python package pytesseract is not installed. Install project requirements."

    configured_path = os.getenv("TESSERACT_CMD", "").strip().strip('"')
    if configured_path:
        if not Path(configured_path).is_file() and not shutil.which(configured_path):
            return None, f"TESSERACT_CMD points to a missing executable: {configured_path}"
        executable = configured_path
    elif WINDOWS_TESSERACT_PATH.is_file():
        executable = str(WINDOWS_TESSERACT_PATH)
    else:
        executable = "tesseract"

    pytesseract.pytesseract.tesseract_cmd = executable
    return executable, None


def check_ocr_available():
    executable, configuration_error = _configure_tesseract()
    if configuration_error:
        return False, configuration_error
    try:
        version = pytesseract.get_tesseract_version()
    except Exception as exc:
        return False, (
            f"Tesseract OCR executable '{executable}' is unavailable: {exc}. "
            "Install Tesseract, set TESSERACT_CMD, or add it to PATH."
        )
    return True, f"Tesseract {version} is ready."


def _read_text_file(file_path):
    return Path(file_path).read_text(encoding="utf-8", errors="replace")


def _rotate_image_if_needed(image):
    if pytesseract is None:
        return image
    try:
        orientation = pytesseract.image_to_osd(image, config="--psm 0")
        match = re.search(r"Rotate:\s*(\d+)", orientation)
        if match:
            degrees = int(match.group(1)) % 360
            if degrees:
                return image.rotate(-degrees, expand=True)
    except Exception:
        pass
    return image


def _ocr_image(image):
    if Image is None or pytesseract is None:
        raise RuntimeError("OCR dependencies are missing. Install Pillow, pytesseract, and the Tesseract executable.")
    image = _rotate_image_if_needed(image)
    return pytesseract.image_to_string(image) or ""


def _extract_document_text(path):
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}. Supported: TXT, PDF, PNG, JPG, JPEG.")

    pages = []
    ocr_used = False
    ocr_errors = []
    if suffix == ".txt":
        text = _read_text_file(path)
        pages.append({"page_number": 1, "text": text, "method": "text", "status": "READ"})
    elif suffix == ".pdf":
        if fitz is None:
            raise RuntimeError("PDF rendering dependency PyMuPDF is missing. Install pymupdf to process scanned PDFs.")
        document = fitz.open(str(path))
        try:
            for index, page in enumerate(document):
                embedded_text = (page.get_text("text") or "").strip()
                if embedded_text:
                    pages.append({"page_number": index + 1, "text": embedded_text, "method": "embedded_text", "status": "READ"})
                    continue
                available, message = check_ocr_available()
                if not available:
                    ocr_errors.append(f"Page {index + 1}: {message}")
                    pages.append({"page_number": index + 1, "text": "", "method": "ocr", "status": "ERROR", "error": message})
                    continue
                try:
                    pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image = Image.open(io.BytesIO(pixmap.tobytes("png")))
                    text = _ocr_image(image)
                    ocr_used = True
                    pages.append({"page_number": index + 1, "text": text, "method": "ocr", "status": "READ" if text.strip() else "EMPTY"})
                except Exception as exc:
                    message = f"OCR failed on page {index + 1}: {exc}"
                    ocr_errors.append(message)
                    pages.append({"page_number": index + 1, "text": "", "method": "ocr", "status": "ERROR", "error": message})
        finally:
            document.close()
    else:
        available, message = check_ocr_available()
        if not available:
            raise RuntimeError(message)
        if Image is None:
            raise RuntimeError("Pillow is missing. Install project requirements to read images.")
        try:
            with Image.open(path) as image:
                image.load()
                text = _ocr_image(image.convert("RGB"))
            ocr_used = True
            pages.append({"page_number": 1, "text": text, "method": "ocr", "status": "READ" if text.strip() else "EMPTY"})
        except Exception as exc:
            raise RuntimeError(f"OCR failed for {path.name}: {exc}") from exc

    raw_text = "\n\n".join(page["text"] for page in pages)
    if ocr_errors:
        status = "PARTIAL" if any(page["text"].strip() for page in pages) else "ERROR"
    elif not raw_text.strip():
        status = "EMPTY"
    elif ocr_used:
        status = "COMPLETED"
    else:
        status = "TEXT_EXTRACTED"
    return {
        "raw_text": raw_text,
        "pages": pages,
        "page_count": len(pages),
        "ocr_status": status,
        "ocr_errors": ocr_errors,
        "detected_format": suffix.lstrip(".").upper(),
    }


def _get_field(patterns, text):
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
        if match:
            value = match.group(1).strip()
            if value:
                return value
    return None


def _numeric_value(value):
    if value is None:
        return None
    text = str(value).strip()
    text = re.sub(r"^(?:USD|EUR|GBP|CAD|AUD)\s*", "", text, flags=re.IGNORECASE)
    text = text.replace("$", "").replace("€", "").replace("£", "").replace("¥", "")
    if not re.fullmatch(r"[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?", text):
        return None
    try:
        return float(text.replace(",", ""))
    except ValueError:
        return None


def _field_value(patterns, text):
    raw = _get_field(patterns, text)
    return raw, _numeric_value(raw)


def _parse_date(value):
    if not value:
        return None, False
    candidate = value.strip()
    slash_date = re.fullmatch(r"(\d{1,2})/(\d{1,2})/(\d{4})", candidate)
    if slash_date:
        first, second = int(slash_date.group(1)), int(slash_date.group(2))
        if first <= 12 and second <= 12 and first != second:
            return None, True
    for date_format in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(candidate, date_format).date().isoformat(), False
        except ValueError:
            continue
    return None, True


def _parse_line_items(lines):
    items = []
    row_pattern = re.compile(
        r"^\s*(.+?)\s+(\d+(?:\.\d+)?)\s+[$€£]?([\d,]+(?:\.\d{1,2})?)\s+[$€£]?([\d,]+(?:\.\d{1,2})?)\s*$"
    )
    partial_row_pattern = re.compile(
        r"^\s*(.+?)\s+(\d+(?:\.\d+)?)\s+[$€£]?([\d,]+(?:\.\d{1,2})?)\s*$"
    )
    amount_only_pattern = re.compile(r"^\s*[$€£]?([\d,]+(?:\.\d{1,2})?)\s*$")
    line_index = 0
    while line_index < len(lines):
        line = lines[line_index]
        if re.search(r"\b(subtotal|tax|vat|gst|grand total|amount due|total amount)\b", line, re.I):
            line_index += 1
            continue
        match = row_pattern.match(line)
        if match:
            description, quantity_text, price_text, total_text = match.groups()
        else:
            partial_match = partial_row_pattern.match(line)
            next_match = amount_only_pattern.match(lines[line_index + 1]) if line_index + 1 < len(lines) else None
            if not partial_match or not next_match:
                line_index += 1
                continue
            description, quantity_text, price_text = partial_match.groups()
            total_text = next_match.group(1)
            line_index += 1
        description = description.strip(" |\t-")
        if not description or description.lower() in {"description", "item", "product"}:
            line_index += 1
            continue
        quantity = _numeric_value(quantity_text)
        unit_price = _numeric_value(price_text)
        line_total = _numeric_value(total_text)
        if quantity is not None and unit_price is not None and line_total is not None:
            items.append({
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "line_total": line_total,
            })
        line_index += 1
    if items:
        return items

    document_text = "\n".join(lines)
    description = _get_field([r"^\s*(?:Item|Description|Product)\s*:\s*([^\r\n]+)"], document_text)
    quantity_raw = _get_field([r"^\s*(?:Quantity|Qty)\s*:\s*([^\r\n]+)"], document_text)
    price_raw = _get_field([r"^\s*(?:Unit Price|Price per Unit|Rate)\s*:\s*([^\r\n]+)"], document_text)
    line_total_raw = _get_field([r"^\s*(?:Line Total|Item Total)\s*:\s*([^\r\n]+)"], document_text)
    quantity = _numeric_value(quantity_raw)
    price = _numeric_value(price_raw)
    line_total = _numeric_value(line_total_raw)
    if line_total is None and quantity is not None and price is not None:
        line_total = round(quantity * price, 2)
    if description and any(value is not None for value in (quantity, price, line_total)):
        return [{"description": description, "quantity": quantity, "unit_price": price, "line_total": line_total}]
    return []


def parse_invoice_text(text: str):
    text = text or ""
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    vendor = _get_field([r"(?:Vendor|Supplier|Company)\s*[:\-]?\s*([^\r\n]+)"], text)
    if not vendor and lines and lines[0].lower() not in {"invoice", "tax invoice", "bill"}:
        vendor = lines[0]

    invoice_number = _get_field([
        r"(?:Invoice\s*(?:No|Number)|Inv\s*No|Bill\s*No)\s*[:\-]?\s*([A-Za-z0-9\-]+)",
        r"No\.?\s*[:\-]?\s*([A-Za-z0-9\-]+)",
    ], text)
    invoice_date_raw = _get_field([r"(?:Invoice\s*Date|Date)\s*[:\-]?\s*([^\r\n]+)"], text)
    invoice_date, bad_date = _parse_date(invoice_date_raw)
    po_number = _get_field([
        r"^\s*(?:PO\s*(?:Number|No\.?)|Purchase\s+Order(?:\s+Number|\s+No\.?)?|Order\s+No)\s*[:#-]\s*([A-Za-z0-9][A-Za-z0-9/-]*)",
    ], text)
    currency = _get_field([r"(?:Invoice\s+)?Currency\s*[:\-]?\s*([A-Z]{3})"], text)
    if not currency:
        currency_match = re.search(r"\b(USD|EUR|GBP|CAD|AUD|INR)\b", text, re.I)
        currency = currency_match.group(1).upper() if currency_match else None

    number_patterns = {
        "quantity": [r"^\s*(?:Quantity|Qty)\s*[:\-]?\s*([^\r\n]+)"],
        "unit_price": [r"^\s*(?:Unit Price|Price per Unit|Rate)\s*[:\-]?\s*([^\r\n]+)"],
        "subtotal": [r"^\s*(?:Sub\s*total|Amount)\s*[:\-]?\s*([^\r\n]+)"],
        "tax_amount": [r"^\s*(?:Tax|VAT|GST)\s*[:\-]?\s*([^\r\n]+)"],
        "total_amount": [r"^\s*(?:Total Amount|Grand Total|Amount Due|Net Payable|Total)\s*[:\-]?\s*([^\r\n]+)"],
    }
    raw_values = {}
    values = {}
    for field, patterns in number_patterns.items():
        raw_values[field], values[field] = _field_value(patterns, text)

    line_items = _parse_line_items(lines)
    row_pattern = re.compile(
        r"^\s*(.+?)\s+(\d+(?:\.\d+)?)\s+[$€£]?([\d,]+(?:\.\d{1,2})?)\s+[$€£]?([\d,]+(?:\.\d{1,2})?)\s*$"
    )
    numeric_like = re.compile(r"^[$€£0-9OIl,.-]+$", re.IGNORECASE)
    suspicious_table_rows = [
        line for line in lines
        if len(line.split()) >= 4
        and not row_pattern.match(line)
        and sum(bool(numeric_like.fullmatch(part)) for part in line.split()) >= 3
        and not re.search(r"\b(subtotal|tax|vat|gst|grand total|amount due|total amount)\b", line, re.I)
    ]
    if line_items:
        if values["quantity"] is None:
            values["quantity"] = sum(item["quantity"] for item in line_items if item["quantity"] is not None)
        if values["unit_price"] is None and len({item["unit_price"] for item in line_items}) == 1:
            values["unit_price"] = line_items[0]["unit_price"]
        if values["subtotal"] is None:
            values["subtotal"] = sum(item["line_total"] for item in line_items if item["line_total"] is not None)

    uncertain_fields = []
    validation_issues = []
    if line_items and values["quantity"] is not None:
        line_quantity_sum = sum(item["quantity"] for item in line_items if item.get("quantity") is not None)
        if round(line_quantity_sum, 2) != round(values["quantity"], 2):
            uncertain_fields.append("quantity")
            validation_issues.append("Invoice quantity summary does not match the extracted line quantities")
    for field, raw in raw_values.items():
        if raw and values[field] is None:
            uncertain_fields.append(field)
            validation_issues.append(f"{field} value is ambiguous or invalid: {raw}")
    if bad_date:
        uncertain_fields.append("invoice_date")
        validation_issues.append(f"Invoice date could not be parsed safely: {invoice_date_raw}")
    if suspicious_table_rows:
        uncertain_fields.append("line_items")
        validation_issues.extend(f"Possible OCR-confused table row needs review: {line}" for line in suspicious_table_rows)

    required_values = {
        "vendor": vendor,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "po_number": po_number,
        "total_amount": values["total_amount"],
    }
    missing_fields = [
        field for field, value in required_values.items()
        if value in (None, "") and field not in uncertain_fields
    ]
    if not line_items and (values["quantity"] is None or values["unit_price"] is None):
        missing_fields.append("line_items")
    for item in line_items:
        if None in (item.get("quantity"), item.get("unit_price"), item.get("line_total")):
            validation_issues.append(f"Line item '{item.get('description')}' has missing or invalid numeric fields")
            uncertain_fields.append("line_items")
        elif round(item["quantity"] * item["unit_price"], 2) != round(item["line_total"], 2):
            validation_issues.append(f"Line total does not equal quantity times unit price for '{item['description']}'")
            uncertain_fields.append("line_items")

    calculated_subtotal = sum(item["line_total"] for item in line_items if item.get("line_total") is not None)
    if line_items and values["subtotal"] is not None and round(calculated_subtotal, 2) != round(values["subtotal"], 2):
        validation_issues.append("Invoice subtotal does not match the extracted line totals")
        uncertain_fields.append("subtotal")
    if line_items and values["total_amount"] is not None and values["tax_amount"] is not None:
        expected_total = (values["subtotal"] if values["subtotal"] is not None else calculated_subtotal) + values["tax_amount"]
        if round(expected_total, 2) != round(values["total_amount"], 2):
            validation_issues.append("Invoice total does not equal subtotal plus tax")
            uncertain_fields.append("total_amount")

    if missing_fields:
        validation_state = "INCOMPLETE"
    elif uncertain_fields or validation_issues:
        validation_state = "REVIEW REQUIRED"
    else:
        validation_state = "READY"

    return {
        "vendor": vendor,
        "invoice_number": invoice_number,
        "invoice_date": invoice_date,
        "po_number": po_number,
        "currency": currency,
        "item": line_items[0]["description"] if line_items else _get_field([r"(?:Item|Description|Product)\s*[:\-]?\s*([^\r\n]+)"], text),
        "line_items": line_items,
        "quantity": values["quantity"],
        "unit_price": values["unit_price"],
        "subtotal": values["subtotal"],
        "tax_amount": values["tax_amount"],
        "total_amount": values["total_amount"],
        "amount": values["total_amount"],
        "raw_values": raw_values,
        "missing_fields": missing_fields,
        "uncertain_fields": sorted(set(uncertain_fields)),
        "validation_issues": validation_issues,
        "source_text": text,
        "validation_state": validation_state,
        "ready_for_verification": validation_state == "READY",
    }


def extract_invoice_file(file_path):
    path = Path(file_path)
    if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {path.suffix.lower() or 'unknown'}. Supported: TXT, PDF, PNG, JPG, JPEG.")
    try:
        extracted = _extract_document_text(path)
        invoice = parse_invoice_text(extracted["raw_text"])
        invoice.update({
            "raw_ocr_text": extracted["raw_text"] if any(page["method"] == "ocr" for page in extracted["pages"]) else "",
            "pages": extracted["pages"],
            "page_count": extracted["page_count"],
            "ocr_status": extracted["ocr_status"],
            "ocr_errors": extracted["ocr_errors"],
            "detected_format": extracted["detected_format"],
        })
        if extracted["ocr_status"] == "EMPTY" and invoice["validation_state"] == "READY":
            invoice["validation_state"] = "INCOMPLETE"
            invoice["ready_for_verification"] = False
        if extracted["ocr_status"] in {"ERROR", "PARTIAL"}:
            invoice["uncertain_fields"] = sorted(set(invoice["uncertain_fields"] + ["document_text"]))
            invoice["validation_issues"].extend(extracted["ocr_errors"])
            if not invoice["missing_fields"]:
                invoice["validation_state"] = "REVIEW REQUIRED"
                invoice["ready_for_verification"] = False
    except Exception as exc:
        invoice = parse_invoice_text("")
        invoice.update({
            "raw_ocr_text": "",
            "pages": [],
            "page_count": 0,
            "ocr_status": "ERROR",
            "ocr_errors": [str(exc)],
            "detected_format": path.suffix.lower().lstrip(".").upper(),
            "validation_state": "INCOMPLETE",
            "ready_for_verification": False,
            "error": str(exc),
            "validation_issues": [str(exc)],
        })
    invoice["source_file"] = str(path)
    return invoice


if __name__ == "__main__":
    sample = extract_invoice_file(Path(__file__).resolve().parent.parent / "sample_invoice.txt")
    print(sample)