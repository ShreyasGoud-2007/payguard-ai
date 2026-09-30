from __future__ import annotations

import hmac

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from ..config import settings
from ..services.nova_client import NovaApiError, NovaClient
from ..services.nova_sync import NovaSyncError, NovaSyncService
from ..database import supabase


router = APIRouter(prefix="/api/admin/nova", tags=["Nova sync"])


class NovaSyncRequest(BaseModel):
    dry_run: bool = True


def create_nova_client() -> NovaClient:
    if settings.nova_api_key is None:
        raise HTTPException(status_code=503, detail="Nova integration is not configured")

    return NovaClient(
        settings.nova_api_key.get_secret_value(),
        settings.nova_base_url,
        timeout_seconds=settings.nova_timeout_seconds,
        page_size=settings.nova_page_size,
        max_retries=settings.nova_max_retries,
        retry_backoff_seconds=settings.nova_retry_backoff_seconds,
    )


@router.post("/sync")
def sync_nova(
    request: NovaSyncRequest,
    x_sync_token: str | None = Header(default=None, alias="X-Sync-Token"),
):
    configured_token = settings.payguard_sync_token
    if configured_token is None:
        raise HTTPException(status_code=503, detail="Internal sync endpoint is disabled")

    if not x_sync_token or not hmac.compare_digest(
        x_sync_token,
        configured_token.get_secret_value(),
    ):
        raise HTTPException(status_code=401, detail="Invalid sync authorization")

    client = create_nova_client()
    try:
        return NovaSyncService(client, supabase, dry_run=request.dry_run).sync()
    except NovaApiError as exc:
        status = f" (HTTP {exc.status_code})" if exc.status_code else ""
        raise HTTPException(
            status_code=502,
            detail=f"Nova upstream request failed{status}",
        ) from exc
    except NovaSyncError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    finally:
        client.close()
