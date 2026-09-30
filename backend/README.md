# PayGuard AI Backend

FastAPI backend for accounts payable controls. Aczen/Nova `/purchase-bills` are the AP source; Nova `/invoices` are not used. Source approval/payment states are evidence only and do not create PayGuard approvals or payable obligations.

## Setup

Requirements: Python 3.10+, a Supabase project, and the private Nova API key.

From `backend/`:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Set these server-only variables in `.env`:

- `SUPABASE_URL`
- `SUPABASE_KEY` (private Supabase service-role key)
- `NOVA_API_KEY`
- `NOVA_BASE_URL` (defaults to `https://www.aczen.in/nova-api/v1`)
- `PAYGUARD_SYNC_TOKEN` (long random value; required to enable the sync endpoint)
- Optional: `APPROVAL_THRESHOLD`, `PRICE_TOLERANCE_PERCENT`, `NOVA_PAGE_SIZE`, `NOVA_MAX_RETRIES`

Never expose either API key or the sync token to frontend code or commit `.env`.

## Database

In Supabase SQL Editor, run these files in order:

1. [`sql/001_initial_schema.sql`](sql/001_initial_schema.sql)
2. [`sql/002_nova_sync.sql`](sql/002_nova_sync.sql)

Both are additive/idempotent where practical. They add source IDs as text (Nova IDs are not always UUID-compatible), timestamps, source payloads, GST fields, verification results, and a separate `nova_approvals` table. Nova approvals remain distinct from PayGuard approvals. Migration 002 normalizes the legacy `UNPAID` ledger state and preserves it in `source_payment_status`.

All backend tables use row-level security and are accessed with the private server-side service-role key. Do not add public/anonymous policies.

## Run and Test

Run the API from `backend/` so `.env` is loaded:

```powershell
.\.venv\Scripts\Activate.ps1
uvicorn app.main:app --reload
```

OpenAPI docs: `http://127.0.0.1:8000/docs`. Health endpoints: `/health` and `/health/db`.

Run automated tests from another terminal in `backend/`:

```powershell
python -m unittest discover -s tests -v
```

The suite mocks Nova and uses an in-memory Supabase-compatible adapter. It does not write fabricated business records to live Nova or Supabase.

## Nova Sync

The server-side client uses Bearer auth, offset/limit pagination (`data` plus `pagination`), bounded network retries, `Retry-After` for 429, and exponential backoff for 502. It syncs vendors, POs and PO items, GRNs and GRN items, purchase bills and bill items, and approvals filtered to `doc_type=purchase_bill`. Payments and bank accounts are available as client methods but are not fetched during AP sync.

The sync endpoint is disabled unless `PAYGUARD_SYNC_TOKEN` is configured. Send the token in `X-Sync-Token`; dry-run is the default:

```powershell
Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/api/admin/nova/sync `
  -Headers @{ 'X-Sync-Token' = $env:PAYGUARD_SYNC_TOKEN } `
  -ContentType 'application/json' `
  -Body '{"dry_run":true}'
```

After applying both migrations and reviewing the dry-run counts, a write sync uses `{"dry_run":false}`. Repeated syncs upsert by stable Nova IDs and preserve PayGuard-owned bill workflow/risk fields. Nova bill status `paid` or approval status `approved` never creates a PayGuard payable.

To verify an actual source bill without writing to Supabase, with Nova configured run:

```powershell
python scripts/verify_real_nova_bill.py
```

The script synchronizes source data only into its in-memory adapter and prints aggregate results, not bill contents.

## Verification and Approval Flow

Nova purchase bills are imported as PayGuard `uploaded` with `verification_status=pending`. Verification returns and stores structured checks for vendor/PO/GRN relationships, accepted quantities (rejected receipt units excluded), line prices, GST components and totals, duplicate/similarity signals, and cumulative PO quantity/value exposure. Exact item IDs are preferred; description similarity is a fallback for manual records.

Nova approvals are informational only. PayGuard approvals use `APPROVAL_THRESHOLD` (default `100000`): one approval at/below the threshold and two distinct approvers above it. Payable posting independently checks verification, duplicates, financial validity, and required approvals. Reposting returns the existing ledger row.

## Frontend APIs

Existing `/api/...` routes are retained. Main contracts include:

- `GET /health`, `GET /health/db`
- `GET /vendors`, `/purchase-orders`, `/goods-receipts`, `/invoices`, `/purchase-bills`, `/payables`
- `POST /api/admin/nova/sync` (protected by `X-Sync-Token`)
- `POST /invoice/upload`; `GET /invoice/{id}`
- `POST /invoice/{id}/verify`, `/approve`, `/reject`
- `GET /invoice/{id}/verification`, `/approvals`
- `GET /audit/{id}`
- Existing `/api/invoices/{id}/post-payable`, `/api/invoices/{id}/risk`, `/api/invoices/{id}/financial-validation`

Errors use JSON `detail`: 401/403 for sync authorization, 404 for missing entities, 409 for workflow conflicts, 422 for invalid inputs/relationships, 502 for Nova upstream errors, and 503 for unavailable integrations. CORS remains limited to local frontend origins on ports 5173 and 3000.

## Deployment Boundaries

A live Nova dry run and live Supabase read check were verified during development. The live Supabase schema does not yet contain the migration-002 objects, and no PostgreSQL/Supabase migration CLI or SQL execution channel is available in the development environment. Apply the two SQL files in Supabase before write sync. Invoice uploads use local disk; production should use private persistent object storage. API caller authentication and payment execution are outside this module.
