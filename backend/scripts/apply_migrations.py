"""
Apply SQL migrations to the live Supabase project.

Strategy (in priority order):
1. POST https://<ref>.supabase.co/rest/v1/rpc/exec_sql  (custom RPC, may not exist)
2. POST https://<ref>.supabase.co/pg/query              (Supabase pg endpoint)
3. Supabase Management API  POST /v1/projects/{ref}/database/query
   (needs a PAT, not the service-role key – will detect and report)

Run from the backend directory:
  venv\Scripts\python scripts\apply_migrations.py [--sql-only]

Pass --sql-only to just print the SQL statements without executing.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from app.config import settings

# ── Configuration ──────────────────────────────────────────────────────────
match = re.match(r"https://([a-z0-9]+)\.supabase\.co", settings.supabase_url)
if not match:
    print("ERROR: Cannot extract project ref from SUPABASE_URL")
    sys.exit(1)

project_ref   = match.group(1)
service_key   = settings.supabase_key.get_secret_value()
base_url      = settings.supabase_url.rstrip("/")

print(f"project_ref: {project_ref}")

# ── Load SQL files ─────────────────────────────────────────────────────────
sql_dir    = Path(__file__).resolve().parents[1] / "sql"
migrations = [
    ("001_initial_schema.sql", (sql_dir / "001_initial_schema.sql").read_text()),
    ("002_nova_sync.sql",      (sql_dir / "002_nova_sync.sql").read_text()),
]

if "--sql-only" in sys.argv:
    for name, sql in migrations:
        print(f"\n{'='*60}\n-- {name}\n{'='*60}\n{sql}")
    sys.exit(0)

# ── Attempt via Supabase pg endpoint (service-role allowed) ───────────────
def try_pg_endpoint(sql: str) -> tuple[bool, str]:
    """Try POST /pg/query with service-role key."""
    url = f"{base_url}/pg/query"
    try:
        r = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {service_key}",
                "Content-Type":  "application/json",
                "apikey":        service_key,
            },
            json={"query": sql},
            timeout=60.0,
        )
        if r.is_success:
            return True, f"HTTP {r.status_code}"
        body = r.text[:300].replace(service_key, "***")
        return False, f"HTTP {r.status_code}: {body}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:200]}"


# ── Attempt via direct PostgREST RPC ──────────────────────────────────────
def try_rpc_exec(sql: str) -> tuple[bool, str]:
    """Try POST /rest/v1/rpc/payguard_exec_sql – only works if the function exists."""
    url = f"{base_url}/rest/v1/rpc/payguard_exec_sql"
    try:
        r = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {service_key}",
                "Content-Type":  "application/json",
                "apikey":        service_key,
            },
            json={"query": sql},
            timeout=60.0,
        )
        if r.is_success:
            return True, f"HTTP {r.status_code}"
        body = r.text[:300].replace(service_key, "***")
        return False, f"HTTP {r.status_code}: {body}"
    except Exception as exc:
        return False, f"{type(exc).__name__}: {str(exc)[:200]}"


overall_ok = True
for filename, sql in migrations:
    print(f"\n{'─'*60}")
    print(f"Applying: {filename}")

    ok, detail = try_pg_endpoint(sql)
    if ok:
        print(f"  method: pg_endpoint  result: OK  ({detail})")
        continue

    print(f"  pg_endpoint: {detail}")
    ok2, detail2 = try_rpc_exec(sql)
    if ok2:
        print(f"  method: rpc_exec     result: OK  ({detail2})")
        continue

    print(f"  rpc_exec: {detail2}")
    print(f"  result: NEEDS_MANUAL_APPLICATION")
    overall_ok = False

print(f"\n{'─'*60}")
print(f"migrations_applied_ok: {overall_ok}")
sys.exit(0 if overall_ok else 1)
