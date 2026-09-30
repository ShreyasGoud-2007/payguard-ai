"""
Inspect the live Supabase schema to check whether the migrations have been applied.
Queries information_schema via PostgREST RPC.

Run from the backend directory:
  venv\Scripts\python scripts\check_schema.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import supabase

EXPECTED_TABLES = [
    "vendors",
    "purchase_orders",
    "purchase_order_items",
    "goods_receipts",
    "goods_receipt_items",
    "invoices",
    "invoice_items",
    "approvals",
    "payable_ledger",
    "audit_logs",
    "nova_approvals",  # added by 002
]

# Nova-specific columns added by 002_nova_sync.sql
NOVA_COLUMNS = {
    "vendors":         ["nova_id", "gst_number", "pan", "synced_at"],
    "purchase_orders": ["nova_id", "source_status", "order_total"],
    "invoices":        ["nova_id", "source_status", "gst_amount", "currency"],
    "nova_approvals":  ["nova_id", "invoice_id", "doc_type"],
}

print("=== Table existence check ===")
for table in EXPECTED_TABLES:
    try:
        resp = supabase.table(table).select("id").limit(1).execute()
        print(f"  {table:30s}  EXISTS  (rows_checked={len(resp.data)})")
    except Exception as exc:
        code = getattr(exc, "code", None)
        msg  = str(exc)[:80]
        print(f"  {table:30s}  MISSING/ERROR  code={code}  {msg}")

print()
print("=== Nova-column spot check ===")
for table, columns in NOVA_COLUMNS.items():
    try:
        col_list = ", ".join(columns[:2])  # just check first two
        resp = supabase.table(table).select(col_list).limit(1).execute()
        print(f"  {table:30s}  nova_cols_present=True")
    except Exception as exc:
        msg = str(exc)[:100]
        print(f"  {table:30s}  nova_cols_present=False  ({msg})")
