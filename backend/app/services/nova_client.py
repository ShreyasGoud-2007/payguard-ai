from __future__ import annotations

import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any, Callable

import httpx


class NovaApiError(RuntimeError):
    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


class NovaClient:
    RESOURCE_PATHS = {
        "vendors": "vendors",
        "purchase_orders": "purchase-orders",
        "goods_receipts": "goods-receipts",
        "purchase_bills": "purchase-bills",
        "approvals": "approvals",
        "vendor_payments": "vendor-payments",
        "vendor_bank_accounts": "vendor-bank-accounts",
    }

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://www.aczen.in/nova-api/v1",
        *,
        timeout_seconds: float = 20.0,
        page_size: int = 100,
        max_retries: int = 3,
        retry_backoff_seconds: float = 0.5,
        transport: httpx.BaseTransport | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        if not api_key:
            raise ValueError("Nova API key is required")
        if page_size < 1 or max_retries < 0:
            raise ValueError("Invalid Nova pagination or retry configuration")

        self.base_url = base_url.rstrip("/")
        self.page_size = page_size
        self.max_retries = max_retries
        self.retry_backoff_seconds = retry_backoff_seconds
        self.sleep = sleep
        self._client = httpx.Client(
            base_url=self.base_url,
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=timeout_seconds,
            transport=transport,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> NovaClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    @staticmethod
    def _retry_after(value: str | None) -> float | None:
        if not value:
            return None
        try:
            return max(0.0, float(value))
        except ValueError:
            try:
                retry_at = parsedate_to_datetime(value)
                if retry_at.tzinfo is None:
                    retry_at = retry_at.replace(tzinfo=timezone.utc)
                return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
            except (TypeError, ValueError, OverflowError):
                return None

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                response = self._client.get(path, params=params)
            except httpx.TransportError as exc:
                last_error = exc
                if attempt >= self.max_retries:
                    break
                self.sleep(self.retry_backoff_seconds * (2 ** attempt))
                continue

            if response.status_code in {429, 502} and attempt < self.max_retries:
                delay = self._retry_after(response.headers.get("Retry-After"))
                if delay is None:
                    delay = self.retry_backoff_seconds * (2 ** attempt)
                self.sleep(delay)
                continue

            if not response.is_success:
                raise NovaApiError(
                    f"Nova request for {path} failed with HTTP {response.status_code}",
                    response.status_code,
                )

            try:
                return response.json()
            except ValueError as exc:
                raise NovaApiError(f"Nova returned invalid JSON for {path}") from exc

        raise NovaApiError(
            f"Nova request for {path} failed after bounded retries",
        ) from last_error

    def get_me(self) -> dict[str, Any]:
        payload = self._get_json("me")
        if not isinstance(payload, dict):
            raise NovaApiError("Nova returned an invalid profile response")
        data = payload.get("data", payload)
        if not isinstance(data, dict):
            raise NovaApiError("Nova returned an invalid profile response")
        return data

    def list_resource(self, resource: str, **filters: Any) -> list[dict[str, Any]]:
        path = self.RESOURCE_PATHS.get(resource, resource)
        offset = 0
        records: list[dict[str, Any]] = []
        seen_offsets: set[int] = set()

        while True:
            if offset in seen_offsets:
                raise NovaApiError(f"Nova pagination did not advance for {path}")
            seen_offsets.add(offset)

            params = {**filters, "limit": self.page_size, "offset": offset}
            payload = self._get_json(path, params)
            if isinstance(payload, list):
                page_records = payload
                pagination: dict[str, Any] = {}
            elif isinstance(payload, dict) and isinstance(payload.get("data"), list):
                page_records = payload["data"]
                pagination = payload.get("pagination") or {}
            else:
                raise NovaApiError(f"Nova returned an invalid collection response for {path}")

            if any(not isinstance(record, dict) for record in page_records):
                raise NovaApiError(f"Nova returned invalid records for {path}")
            records.extend(page_records)

            if "has_more" in pagination:
                has_more = bool(pagination["has_more"])
            elif pagination.get("total") is not None:
                has_more = offset + len(page_records) < int(pagination["total"])
            else:
                has_more = len(page_records) == self.page_size

            if not has_more or not page_records:
                return records

            next_offset = pagination.get("offset", offset) + len(page_records)
            if next_offset <= offset:
                next_offset = offset + len(page_records)
            offset = next_offset

    def list_vendors(self) -> list[dict[str, Any]]:
        return self.list_resource("vendors")

    def list_purchase_orders(self) -> list[dict[str, Any]]:
        return self.list_resource("purchase_orders")

    def list_goods_receipts(self) -> list[dict[str, Any]]:
        return self.list_resource("goods_receipts")

    def list_purchase_bills(self) -> list[dict[str, Any]]:
        return self.list_resource("purchase_bills")

    def list_approvals(self, **filters: Any) -> list[dict[str, Any]]:
        return self.list_resource("approvals", **filters)

    def list_vendor_payments(self) -> list[dict[str, Any]]:
        return self.list_resource("vendor_payments")

    def list_vendor_bank_accounts(self) -> list[dict[str, Any]]:
        return self.list_resource("vendor_bank_accounts")
