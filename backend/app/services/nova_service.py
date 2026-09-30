from __future__ import annotations

import asyncio
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings


class NovaServiceError(RuntimeError):
    """Raised when Nova API communication fails."""


class NovaService:
    """
    Server-side client for the hackathon Nova read-only REST API.

    Nova is an external accounting data source.
    It does NOT make PayGuard's deterministic approval/payable decision.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = (
            api_key if api_key is not None else settings.NOVA_API_KEY
        )

        self.base_url = (
            base_url
            if base_url is not None
            else "https://www.aczen.in/nova-api/v1"
        ).rstrip("/")

        self.transport = transport

    def _headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise NovaServiceError("NOVA_API_KEY is not configured")

        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
        }

    async def _get(
        self,
        resource: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:

        url = f"{self.base_url}/{resource.lstrip('/')}"

        max_attempts = 3
        attempt = 0

        while attempt < max_attempts:
            attempt += 1

            try:
                async with httpx.AsyncClient(
                    transport=self.transport,
                    timeout=20.0,
                ) as client:

                    response = await client.get(
                        url,
                        headers=self._headers(),
                        params=params or {},
                    )

                # Successful response
                if response.status_code < 400:
                    return response.json()

                # 429 = rate limit
                if response.status_code == 429:
                    retry_after = response.headers.get("Retry-After")

                    if attempt >= max_attempts:
                        raise NovaServiceError(
                            "Nova rate limit exceeded after retries"
                        )

                    try:
                        wait_seconds = float(retry_after or "2")
                    except ValueError:
                        wait_seconds = 2.0

                    await asyncio.sleep(wait_seconds)
                    continue

                # 502 = temporary upstream failure
                if response.status_code == 502:
                    if attempt >= max_attempts:
                        raise NovaServiceError(
                            "Nova returned 502 after retries"
                        )

                    await asyncio.sleep(2 ** (attempt - 1))
                    continue

                # 400 / 401 / 404 / 405 and other errors
                try:
                    error_body = response.json()
                except Exception:
                    error_body = response.text

                raise NovaServiceError(
                    f"Nova API request failed "
                    f"(HTTP {response.status_code}): {error_body}"
                )

            except httpx.HTTPError as exc:
                if attempt >= max_attempts:
                    raise NovaServiceError(
                        "Unable to connect to Nova API"
                    ) from exc

                await asyncio.sleep(2 ** (attempt - 1))

        raise NovaServiceError("Nova request failed")

    async def health(self) -> Dict[str, Any]:
        """
        Nova health endpoint does not require authentication.
        """
        url = f"{self.base_url}/health"

        try:
            async with httpx.AsyncClient(
                transport=self.transport,
                timeout=20.0,
            ) as client:
                response = await client.get(url)

            response.raise_for_status()
            return response.json()

        except (httpx.HTTPError, ValueError) as exc:
            raise NovaServiceError(
                "Nova health check failed"
            ) from exc

    async def get_invoices(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return await self._get(
            "/invoices",
            params={
                "limit": min(max(limit, 1), 200),
                "offset": max(offset, 0),
            },
        )

    async def get_invoice(
        self,
        invoice_id: str,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return await self._get(
            f"/invoices/{invoice_id}"
        )

    async def get_vendors(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return await self._get(
            "/vendors",
            params={
                "limit": min(max(limit, 1), 200),
                "offset": max(offset, 0),
            },
        )

    async def get_purchase_orders(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return await self._get(
            "/purchase-orders",
            params={
                "limit": min(max(limit, 1), 200),
                "offset": max(offset, 0),
            },
        )

    async def get_goods_receipts(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return await self._get(
            "/goods-receipts",
            params={
                "limit": min(max(limit, 1), 200),
                "offset": max(offset, 0),
            },
        )

    async def get_purchase_bills(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return await self._get(
            "/purchase-bills",
            params={
                "limit": min(max(limit, 1), 200),
                "offset": max(offset, 0),
            },
        )

    async def get_vendor_payments(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return await self._get(
            "/vendor-payments",
            params={
                "limit": min(max(limit, 1), 200),
                "offset": max(offset, 0),
            },
        )

    async def get_approvals(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return await self._get(
            "/approvals",
            params={
                "limit": min(max(limit, 1), 200),
                "offset": max(offset, 0),
            },
        )

    async def get_vendor_bank_accounts(
        self,
        limit: int = 50,
        offset: int = 0,
    ) -> Dict[str, Any] | List[Dict[str, Any]]:
        return await self._get(
            "/vendor-bank-accounts",
            params={
                "limit": min(max(limit, 1), 200),
                "offset": max(offset, 0),
            },
        )