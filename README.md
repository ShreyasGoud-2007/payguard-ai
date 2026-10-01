# PayGuard AI

PayGuard AI is an Accounts Payable control system that verifies invoices against approved purchase orders and goods receipts before they enter the payable ledger.

This project consists of:
- **Backend**: Python-based invoice verification engine with OCR and AI capabilities
- **Frontend**: React/TypeScript web application with 3D visualization

---

## Frontend (3D Web Interface)

This project was built with [Lovable](https://lovable.dev) and provides a modern web interface for PayGuard AI.

### Frontend Development

You need Node.js and npm — [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating).

```sh
npm i
npm run dev
```

Continue developing in the [Lovable editor](https://lovable.dev/projects/f948e624-91b0-4644-a625-af371f58c2b8).

---

## Backend (Python Invoice Verification)

### Overview

This system checks whether an invoice matches an approved purchase order, is supported by goods receipts, and has the expected prices and quantities before a human reviewer decides whether the invoice can proceed.

Backend setup, Nova sync, Supabase migrations, API flow, and test instructions are in [backend/README.md](backend/README.md) (if applicable).

### Problem Statement

A vendor invoice should not become a payable obligation just because it was received. The system checks the invoice against approved PO and receipt data before flagging a case for human review.

### Architecture

The prototype has a simple layered design:

- File input and validation
- Text extraction / OCR fallback
- Deterministic verification checks
- SQLite database for PO, receipt, and invoice records
- Optional AI-assisted mapping layer
- Streamlit dashboard and review workflow

```text
Upload invoice
   ↓
Validate file and metadata
   ↓
Extract text and identify fields
   ↓
Look up approved PO and goods receipts
   ↓
Run deterministic verification rules
   ↓
Show PASSED / REVIEW REQUIRED / INCOMPLETE
   ↓
Save results and audit evidence
```

### AI Explanation and Privacy

The provider is opt-in. `AI_PROVIDER` defaults to `disabled`; in that mode the application makes no model call and displays the existing deterministic explanation. To enable OpenAI, add settings to your local `.env` file (which is ignored by Git):

```dotenv
AI_PROVIDER=openai
OPENAI_API_KEY=your-key-from-the-provider
OPENAI_MODEL=gpt-4o-mini
```

Use a model available to your account. Keep the key in the ignored `.env` file or a process environment variable; never put it in source code or `.env.example`. Set `AI_PROVIDER=disabled` to turn off AI. Tests do not require a key or network access.

The OpenAI provider receives only the deterministic verification status, named check results and explanations, numeric expected/actual values for applicable checks, and missing/uncertain field names. Vendor names, invoice/PO identifiers, raw OCR text, images, API keys, and unrelated database records are excluded. Provider timeouts, errors, missing configuration, malformed output, or unsupported evidence references return the deterministic fallback. The model output is labeled `AI-generated`; it is explanatory only and cannot change verification status or checks. No provider request initiates a payment or makes an approval decision.

The deterministic risk analysis is available from `paygard_ai.risk_analysis.analyze_invoice_risk(invoice, verification_report)`. The optional provider boundary is in `paygard_ai.ai_provider`; both layers preserve the verifier's original status and evidence. No probability score is produced.

### OCR and Local Demo Mode

With the default `AI_PROVIDER=disabled`, the app runs in offline local mode. Text files and text-based PDF pages use local parsing. Scanned PDFs, PNGs, and JPG/JPEG files use Tesseract OCR; scanned PDF pages are rendered with PyMuPDF. Each page is processed in order, and raw OCR text is stored separately from structured invoice fields.

Python packages do not install the Tesseract executable. On Windows, install Tesseract OCR using the installer linked from the [UB-Mannheim Tesseract releases](https://github.com/UB-Mannheim/tesseract/wiki). If the executable is not on `PATH`, set its full path in PowerShell and restart the terminal:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

Check availability with:

```powershell
tesseract --version
```

If this command is unavailable, the dashboard displays an OCR setup error and saves the attempt as `INCOMPLETE`; it never treats OCR text as a verification pass. Invalid or uncertain financial fields are retained as raw OCR text and routed to review. OCR confidence is separate from PO/receipt verification.

### Backend Setup

1. Create and activate a virtual environment.
2. Install dependencies:

```bash
python -m venv .venv
. .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate  # Windows PowerShell
pip install -r requirements.txt
```

3. Install the Tesseract system executable as described above to process scans.
4. Copy `.env.example` to `.env` if using optional AI configuration.
5. Run the demo CLI:

```bash
python main.py --sample-file sample_invoice.txt
```

If `--db-path` is omitted, this legacy single-invoice CLI now creates a fresh uniquely named database under the system temporary directory and prints its location. The six-case demo is `python -m paygard_ai.demo`; it likewise creates a fresh isolated database by default. To use an existing path deliberately, pass `--db-path` (CLI) or `--output-dir` (workflow demo); neither command deletes or resets an existing database.

6. Run the dashboard:

```bash
python -m streamlit run app.py
```

7. Upload a PDF, PNG, JPG/JPEG, or TXT invoice and select **Process invoice**. The dashboard shows OCR status, page count, extracted text, structured fields, uncertainties, verification evidence, and the saved final status.

For hands-on OCR checks after installing Tesseract, upload the raster samples in `samples/`:

- `ocr_matching_invoice.png` should match the seeded PO500 and receipt and pass.
- `ocr_mismatched_invoice.png` exceeds the PO quantity/amount and should require review.
- `ocr_incomplete_invoice.png` lacks required invoice/PO fields and should remain incomplete.
- Upload `ocr_matching_invoice.png` again to check duplicate detection.

Run all automated tests with:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

### Sample Data and Demo Flow

The seeded demo data includes:

- Vendor: ABC Traders
- PO: PO500
- Unit price: 100
- Quantity: 10
- Amount: 1000
- Receipt: GR500

The default sample file is `sample_invoice.txt` with the same matching values. It should pass as a normal demo case.

### End-to-End Synthetic Workflow Demo

Run the full isolated six-case demo with:

```powershell
.\.venv\Scripts\python.exe -m paygard_ai.demo
```

The runner creates a unique temporary directory and a separate `paygard_synthetic_demo.db`; it does not use or reset `paygard.db`. It generates invoice files with the clearly synthetic vendor `SYNTHETIC DEMO SUPPLY CO` and `SYNTH-*` identifiers. The normal command uses text invoices for a repeatable extraction test and forces deterministic AI fallback, so it makes no API calls.

To exercise actual Tesseract recognition on generated synthetic scans, set `TESSERACT_CMD` as above and run:

```powershell
.\.venv\Scripts\python.exe -m paygard_ai.demo --ocr
```

To use the configured optional OpenAI provider, add `--use-ai` to either command. That option may make billable external requests; the default demo does not. The runner prints the isolated database and invoice folder. To inspect that exact demo database in Streamlit, use the printed database path:

```powershell
$env:DB_PATH = "<printed demo database path>"
$env:PAYGARD_SKIP_DEMO_SEED = "1"
$env:AI_PROVIDER = "disabled"
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The six expected outcomes are:

| Synthetic scenario | Expected result |
|---|---|
| Approved PO, matching amount and receipt | `PASSED` |
| Invoice amount and price differ from the PO | `REVIEW REQUIRED` |
| Invoice date, PO, and line information missing | `INCOMPLETE` |
| Matching invoice submitted a second time | `REVIEW REQUIRED` (duplicate check fails) |
| PO is `PENDING` | `REVIEW REQUIRED` |
| Receipt quantity is less than invoice quantity | `REVIEW REQUIRED` |

For any review-required or incomplete upload, the dashboard offers explicit reviewer, decision, and notes fields. Saving a decision creates a review-history row and a linked audit event; it does not change verification status or authorize payment.

#### Two-Minute Presentation

1. Run the synthetic demo and point out that it creates a separate database and clearly labeled test invoices.
2. Show the matching invoice passing PO, amount, and receipt checks.
3. Compare the amount-mismatch and insufficient-receipt cases; explain that failed deterministic checks require human review.
4. Show the missing-information case remaining incomplete and the duplicate case being detected on reprocessing.
5. Open the dashboard with the printed demo DB path, inspect the evidence and deterministic explanation, and record a review decision with notes. Emphasize that this records review only; PayGuard never initiates payment.
6. State that the demo uses no real AI API call by default.

### Data Sources and Future Imports

PayGuard labels newly created reference rows with their origin: demo seed rows are `DEMO`, invoices processed from uploaded files are `UPLOAD`, and rows that existed before source tracking was added remain `LEGACY` because their origin cannot be proven retroactively. The dashboard shows counts by source. These labels describe local PayGuard records.

`paygard_ai.data_import.import_normalized_records()` is a format-neutral boundary for already-normalized PayGard purchase orders and goods receipts. It does not read CSV/Excel/SQL files and does not contain specific field names. A future adapter must inspect the actual files, map them into the internal PayGard fields, and provide source record IDs and provenance where available. Unmapped fields are rejected rather than discarded. The importer validates canonical PO status as `APPROVED`, amounts, quantities, dates, references, and duplicate keys.

The importer is preview-only by default: it returns prepared, invalid, skipped, duplicate, and imported counts without writing. Persistence requires an explicit database manager and `persist=True`; labeled persistence additionally requires `mapping_confirmed=True`, and writes to the configured live database require a separate `allow_live_database=True` opt-in. Tests use temporary databases. The importer currently accepts only PO and receipt reference records; it does not import a vendor master or historical invoice references.

After a source-specific adapter has been implemented from the real dataset documentation, preview its normalized records first:

```python
preview = import_normalized_records(normalized_records, source="SOURCE")
print(preview["imported"], preview["invalid"], preview["duplicate"], preview["issues"])
```

Only after reviewing the mapping and preview should a test import persist to a separate staging database:

```python
staging_db = DatabaseManager("staging.db")
result = import_normalized_records(
   normalized_records,
   source="SOURCE",
   database=staging_db,
   persist=True,
   mapping_confirmed=True,
)
```

The importer deliberately refuses the configured live `paygard.db` unless `allow_live_database=True` is explicitly supplied. Do not set that flag until source mapping, staging import results, and backups are reviewed.

Persisted imports create a `data_import_runs` history row in the same transaction as the imported PO/receipt rows. The dashboard's **Data import status** section shows recent persisted-run counts, mapping confirmation, or explicitly reports that there is no import. Preview results are returned to the caller but intentionally are not saved to SQLite.

### Security and Privacy

- Uploads are validated by type and size.
- Files are stored only in the project when the user chooses to keep them.
- Secrets stay in environment variables or `.env`.
- Invoice images and raw OCR documents are not sent to the AI provider. When explicitly enabled, only the structured verification evidence described above is sent; default mode is offline.

### Current Limitations

- OCR requires the separately installed Tesseract executable; OCR unit tests mock the engine and do not prove real OCR quality.
- Invoice layout parsing uses conservative patterns. Complex tables and low-quality scans may require human review.
- OCR output is never corrected by guessing financial values. Ambiguity is kept with the source text and routed to review/incomplete status.
- This is a prototype verification tool, not an approval engine.
- A technical pass is not payment authorization.

### Future Scope

- Multi-line PO matching and line-item reconciliation
- Better OCR and PDF table extraction
- Real review queue and audit dashboard
- More advanced AI field mapping with schema validation
