import os
from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR.parent / ".env")
load_dotenv(BASE_DIR / ".env")


class Settings:
    APP_NAME = "PayGuard AI"
    APP_VERSION = "1.0.0"

    # Supabase
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv(
        "SUPABASE_SERVICE_ROLE_KEY",
        "",
    )

    # Nova
    NOVA_API_KEY = os.getenv("NOVA_API_KEY", "")

    NOVA_API_URL = os.getenv(
        "NOVA_API_URL",
        "https://www.aczen.in/nova-api/v1",
    )

    # AP validation
    PRICE_TOLERANCE = float(
        os.getenv("AP_PRICE_TOLERANCE", "0.01")
    )


settings = Settings()