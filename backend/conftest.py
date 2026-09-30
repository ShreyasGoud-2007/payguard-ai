"""
Root conftest.py – adds the backend directory to sys.path so that
'from app.xxx import ...' works in all tests regardless of the working
directory pytest is launched from.
"""
import os
import sys
from pathlib import Path

# Ensure BACKEND_DIR is on the path before any test module is imported.
BACKEND_DIR = Path(__file__).resolve().parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Provide safe fallback env vars so tests that don't patch them can still
# import app.config without a real .env file.
os.environ.setdefault("SUPABASE_URL", "http://localhost:54321")
os.environ.setdefault("SUPABASE_KEY", "test-key")
