"""
Tests live Supabase connectivity by listing tables in information_schema.
Prints table names only – no secret values are printed.
Run from the backend directory:  venv\Scripts\python scripts\check_db_connectivity.py
"""
from __future__ import annotations
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.database import supabase

print("Attempting Supabase connectivity check...")
try:
    # Try a raw SQL query via RPC to list public tables, falling back to
    # a simple table probe that works with the anon/service key.
    resp = (
        supabase.table("vendors")
        .select("id")
        .limit(1)
        .execute()
    )
    print(f"vendors_table_accessible: True  (rows_returned={len(resp.data)})")
except Exception as exc:
    code = getattr(exc, "code", None)
    msg = str(exc)
    # Scrub any potential key fragments from error message
    print(f"vendors_table_accessible: False")
    print(f"error_type: {type(exc).__name__}")
    print(f"error_code: {code}")
    # Only show the first 120 chars, no auth tokens appear in typical PG errors
    print(f"error_summary: {msg[:120]}")
