from __future__ import annotations

import httpx
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.nova_service import NovaService, NovaServiceError


def test_nova_health():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path.endswith("/health")

        return httpx.Response(
            200,
            json={"status": "ok"},
        )

    service = NovaService(
        api_key="private-key",
        base_url="https://nova.example/v1",
        transport=httpx.MockTransport(handler),
    )

    result = __import__("asyncio").run(service.health())

    assert result["status"] == "ok"


def test_nova_get_invoices_uses_server_key():
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)

        assert request.method == "GET"
        assert request.headers["Authorization"] == "Bearer private-key"
        assert request.headers["Accept"] == "application/json"
        assert request.url.path.endswith("/invoices")

        return httpx.Response(
            200,
            json={
                "data": [
                    {
                        "id": "inv-1",
                        "invoice_number": "INV-1",
                        "total_amount": 1000,
                    }
                ],
                "pagination": {
                    "limit": 5,
                    "offset": 0,
                    "total": 1,
                    "has_more": False,
                },
            },
        )

    service = NovaService(
        api_key="private-key",
        base_url="https://nova.example/v1",
        transport=httpx.MockTransport(handler),
    )

    result = __import__("asyncio").run(
        service.get_invoices(limit=5)
    )

    assert len(requests) == 1
    assert result["data"][0]["invoice_number"] == "INV-1"


def test_nova_missing_key_fails():
    service = NovaService(
        api_key="",
        base_url="https://nova.example/v1",
    )

    with pytest.raises(NovaServiceError):
        __import__("asyncio").run(
            service.get_invoices()
        )


def test_nova_429_retries():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)

        if len(attempts) == 1:
            return httpx.Response(
                429,
                headers={"Retry-After": "0"},
                json={"error": {"code": "RATE_LIMITED"}},
            )

        return httpx.Response(
            200,
            json={
                "data": [],
                "pagination": {
                    "limit": 50,
                    "offset": 0,
                    "total": 0,
                    "has_more": False,
                },
            },
        )

    service = NovaService(
        api_key="private-key",
        base_url="https://nova.example/v1",
        transport=httpx.MockTransport(handler),
    )

    result = __import__("asyncio").run(
        service.get_invoices()
    )

    assert len(attempts) == 2
    assert result["data"] == []


def test_nova_502_retries():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)

        if len(attempts) < 3:
            return httpx.Response(
                502,
                json={"error": {"code": "BAD_GATEWAY"}},
            )

        return httpx.Response(
            200,
            json={
                "data": [],
                "pagination": {
                    "limit": 50,
                    "offset": 0,
                    "total": 0,
                    "has_more": False,
                },
            },
        )

    service = NovaService(
        api_key="private-key",
        base_url="https://nova.example/v1",
        transport=httpx.MockTransport(handler),
    )

    result = __import__("asyncio").run(
        service.get_invoices()
    )

    assert len(attempts) == 3
    assert result["data"] == []


def test_nova_401_does_not_retry():
    attempts = []

    def handler(request: httpx.Request) -> httpx.Response:
        attempts.append(request)

        return httpx.Response(
            401,
            json={
                "error": {
                    "code": "UNAUTHORIZED"
                }
            },
        )

    service = NovaService(
        api_key="bad-key",
        base_url="https://nova.example/v1",
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(NovaServiceError):
        __import__("asyncio").run(
            service.get_invoices()
        )

    assert len(attempts) == 1


def test_invoice_list_endpoint_uses_supabase(monkeypatch):
    class FakeSupabase:
        async def fetch_invoices(self):
            return [
                {
                    "invoice_number": "INV-1",
                    "vendor": {
                        "vendor_name": "Example Co",
                        "status": "ACTIVE",
                    },
                    "po": {},
                    "grn": {},
                    "invoice_items": [],
                    "invoice_total": 0,
                }
            ]

    monkeypatch.setattr(
        "app.main.supabase",
        FakeSupabase(),
    )

    with TestClient(app) as client:
        response = client.get("/invoices")

    assert response.status_code == 200

    result = response.json()

    assert result["data"][0]["invoice_number"] == "INV-1"

    assert (
        "MISSING_PO"
        in result["data"][0]["validation"]["exception_codes"]
    )


def test_invoice_verify_is_deterministic(monkeypatch):
    class FakeNova:
        pass

    monkeypatch.setattr(
        "app.main.nova",
        FakeNova(),
    )

    with TestClient(app) as client:
        response = client.post(
            "/invoices/verify",
            json={
                "invoice_number": "INV-1",
                "vendor": {
                    "status": "ACTIVE"
                },
                "po": {},
                "grn": {},
                "invoice_items": [],
                "invoice_total": 0,
            },
        )

    assert response.status_code == 200

    result = response.json()["data"]

    assert result["payable_eligible"] is False
    assert "MISSING_PO" in result["exception_codes"]