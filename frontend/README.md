# PayGuard AI — "Verify before you pay."
React + TypeScript + Vite + Tailwind + React Router + Recharts. Mock data only, no backend.

## Run
```
npm install
npm run dev
```
Demo: Invoices → Upload Invoice → any file → Analyze → INV-1035 (PO 100 / GRN 80 / Invoice 100, ₹10,00,000 excess, risk 72) → Approve/Reject/Send for Review → check Audit Trail and Payable Ledger.

## Team split
- **Dev 1 – Verification & Invoices:** `components/verification`, `components/invoices`, `pages/InvoiceDetails|UploadInvoice|Invoices|DuplicateDetection`, `services/verificationService|duplicateService`
- **Dev 2 – Workflow & Ledger:** `components/approvals`, `pages/Approvals|Exceptions|PayableLedger|AuditTrail`, `services/approvalService`, `types/approval|audit`
- **Dev 3 – Shell, Dashboard & Master data:** `components/layout|dashboard|ui`, `pages/Dashboard|Vendors|PurchaseOrders|Settings`, `data/*`, `services/invoiceService`

## Backend later
Only `src/services/*` should change: replace in-memory logic with FastAPI/Supabase calls, keeping function signatures.
