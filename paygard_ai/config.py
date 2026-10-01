import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "paygard.db"))).expanduser()
ALLOWED_EXTENSIONS = {".txt", ".pdf", ".png", ".jpg", ".jpeg"}
MAX_UPLOAD_SIZE = 10 * 1024 * 1024

AI_PROVIDER = os.getenv("AI_PROVIDER", "disabled").strip().lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini").strip()
