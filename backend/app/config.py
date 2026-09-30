from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import SecretStr
from decimal import Decimal


class Settings(BaseSettings):
    supabase_url: str
    supabase_key: SecretStr
    nova_api_key: SecretStr | None = None
    nova_base_url: str = "https://www.aczen.in/nova-api/v1"
    nova_timeout_seconds: float = 20.0
    nova_page_size: int = 100
    nova_max_retries: int = 3
    nova_retry_backoff_seconds: float = 0.5
    payguard_sync_token: SecretStr | None = None
    approval_threshold: Decimal = Decimal("100000")
    price_tolerance_percent: Decimal = Decimal("0")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()