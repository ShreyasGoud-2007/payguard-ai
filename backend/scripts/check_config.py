"""
Probe config and connectivity without printing any secret values.
Run from the backend directory:  venv\Scripts\python scripts\check_config.py
"""
from __future__ import annotations
import sys
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.config import settings

url = settings.supabase_url
parsed = urlparse(url)
print(f"supabase_host:          {parsed.hostname}")
print(f"supabase_url_scheme:    {parsed.scheme}")
print(f"supabase_url_set:       {bool(url and 'supabase' in url.lower())}")
print(f"nova_api_key_set:       {settings.nova_api_key is not None}")
print(f"payguard_sync_token_set:{settings.payguard_sync_token is not None}")
