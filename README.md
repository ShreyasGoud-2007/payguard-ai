# PayGuard AI — Accounts Payable Control System

## Overview

This repository contains the AP control database and backend foundation for the hackathon demo. The system ensures an invoice only becomes payable after vendor validation, PO authorization, goods receipt verification, quantity and price match checks, tax validation, duplicate detection, risk review, approval gating, and a complete audit trail.

## Repository structure

- `database/migrations/` — additive schema changes for the AP workflow
- `database/seeds/` — safe demo seed scripts for fresh local/dev databases
- `database/docs/` — operational and database documentation
- `backend/` — FastAPI backend and validation logic

## Core AP rules

1. Vendor must exist and be active.
2. Invoice must match a valid PO and vendor.
3. Goods receipt must be present and quantities must reconcile.
4. Unit prices must match the PO within the configured tolerance.
5. Tax and total must reconcile mathematically.
6. Duplicate or similar invoices are flagged before payable status is allowed.
7. Risk is assigned based on explainable reasons.
8. Approved low-risk invoices may become payable; medium/high-risk invoices require review.
9. Payable ledger insertion is blocked until validation and approval requirements pass.
10. Important actions are recorded in audit logs.

## Demo scenarios

- `INV-1001` — clean, approved, low risk, payable
- `INV-1002` — quantity mismatch, high risk, under review, not payable
- `INV-1003` — price mismatch, medium risk, under review, not payable
- `INV-1004` — duplicate/similar invoice, high risk, under review, not payable

## Local setup

1. Copy `.env.example` to `.env` and fill in the Supabase variables if needed.
2. Create or activate a Python environment.
3. Install dependencies:

   ```bash
   cd backend
   python -m pip install -r requirements.txt
   ```

4. Start the API:

   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

5. Test the validation rules:

   ```bash
   cd backend
   python -m pytest tests/test_business_rules.py
   ```

## Environment variables

Use the project root `.env` file with the following keys:

```env
SUPABASE_URL=
SUPABASE_ANON_KEY=
SUPABASE_SERVICE_ROLE_KEY=
NOVA_API_KEY=
NOVA_API_URL=
NOVA_MODEL=nova-pro
AP_PRICE_TOLERANCE=0.01
```

Never commit real secrets. The service role key remains server-side only.
`NOVA_API_KEY` and `NOVA_API_URL` are also server-side only. `NOVA_API_URL` must point to the Nova server's OpenAI-compatible chat completions endpoint. Nova is used for advisory summaries only; deterministic validation remains authoritative.
Approval actions require a Supabase Auth Bearer token. The authenticated Supabase user must map to an active `users.auth_provider_id`, and the pending approval must be assigned to that user's `users.id`.

## Database guidance

- `001_initial_schema.sql` is treated as the committed baseline schema.
- New additive improvements must go into a new migration file such as `database/migrations/002_ap_hardening.sql`.
- The seed script in `database/seeds/001_demo_data.sql` is intended only for local or demo/dev use and includes explicit comments and safe conflict handling.

## Backend API notes

The FastAPI service reads invoices, vendors, purchase orders, goods receipts, approvals, payable ledger entries, and audit logs from Supabase. It returns HTTP 503 when Supabase is not configured or unavailable; it never falls back to the removed in-memory fixture data. The SQL demo seed remains available for local development.

## Security

- Do not expose the service-role key in the frontend.
- Keep secrets in `.env` and never commit them.
- Validate request payloads before generating ledger or approval actions.

## Manual actions

MANUAL ACTIONS REQUIRED: NONE
