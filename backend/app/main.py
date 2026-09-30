from __future__ import annotations

from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from app.config import settings
from app.services.nova_service import NovaService
from app.services.supabase_service import (
    SupabaseAuthenticationError,
    SupabaseService,
    SupabaseServiceError,
)
from app.services.validation import evaluate_invoice


app = FastAPI(
    title="PayGuard AI — Accounts Payable Control System",
    version="1.0.0",
    description="AP control validation layer for invoice verification, risk scoring, approvals, payable ledger gating, and audit logging.",
)

supabase = SupabaseService()
nova = NovaService()


def _database_unavailable(exc: SupabaseServiceError) -> HTTPException:
    return HTTPException(status_code=503, detail=str(exc))


@app.get("/health")
async def health() -> Dict[str, Any]:
    return {
        "status": "ok",
        "service": "payguard-ai",
        "supabase_configured": bool(
            supabase.url and supabase.key
        ),
        "nova_configured": bool(
            nova.api_key and nova.base_url
        ),
        "price_tolerance": settings.PRICE_TOLERANCE,
    }


@app.get("/invoices")
async def list_invoices() -> Dict[str, Any]:
    try:
        invoices = await supabase.fetch_invoices()
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    evaluated = [
        {
            **invoice,
            "validation": evaluate_invoice(invoice),
        }
        for invoice in invoices
    ]

    return {
        "data": evaluated,
        "count": len(evaluated),
    }


@app.get("/invoices/{invoice_number}")
async def get_invoice(invoice_number: str) -> Dict[str, Any]:
    try:
        invoice = await supabase.fetch_invoice(invoice_number)
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    if not invoice:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    return {
        "data": {
            **invoice,
            "validation": evaluate_invoice(invoice),
        }
    }


@app.get("/vendors")
async def list_vendors() -> Dict[str, Any]:
    try:
        vendors = await supabase.fetch_vendors()
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    return {
        "data": vendors,
        "count": len(vendors),
    }


@app.get("/purchase-orders")
async def list_purchase_orders() -> Dict[str, Any]:
    try:
        purchase_orders = await supabase.fetch_purchase_orders()
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    return {
        "data": purchase_orders,
        "count": len(purchase_orders),
    }


@app.get("/goods-receipts")
async def list_goods_receipts() -> Dict[str, Any]:
    try:
        receipts = await supabase.fetch_goods_receipts()
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    return {
        "data": receipts,
        "count": len(receipts),
    }


@app.get("/exceptions")
async def list_exceptions() -> Dict[str, Any]:
    try:
        exceptions = await supabase.fetch_exceptions()
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    return {
        "data": exceptions,
        "count": len(exceptions),
    }


@app.get("/payable-ledger")
async def list_payable_ledger() -> Dict[str, Any]:
    try:
        payable = await supabase.fetch_payable_ledger()
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    return {
        "data": payable,
        "count": len(payable),
    }


@app.get("/audit-log")
async def list_audit_log() -> Dict[str, Any]:
    try:
        audit_log = await supabase.fetch_audit_log()
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    return {
        "data": audit_log,
        "count": len(audit_log),
    }


@app.get("/dashboard")
async def dashboard() -> Dict[str, Any]:
    try:
        invoices = await supabase.fetch_invoices()
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    items = [
        evaluate_invoice(invoice)
        for invoice in invoices
    ]

    return {
        "total_invoices": len(items),
        "pending_invoices": sum(
            1
            for item in items
            if item["status"] == "UNDER_REVIEW"
        ),
        "approved_invoices": sum(
            1
            for item in items
            if item["status"] == "APPROVED"
        ),
        "rejected_invoices": sum(
            1
            for item in items
            if item["status"] == "REJECTED"
        ),
        "high_risk_invoices": sum(
            1
            for item in items
            if item["risk_level"] == "HIGH"
        ),
        "duplicate_invoices": sum(
            1
            for item in items
            if "DUPLICATE_INVOICE"
            in item["exception_codes"]
        ),
        "total_payable_amount": sum(
            float(invoice.get("invoice_total") or 0)
            for invoice in invoices
            if evaluate_invoice(invoice)["payable_eligible"]
        ),
        "invoices_requiring_review": sum(
            1
            for item in items
            if item["approval_required"]
        ),
    }


@app.post("/invoices/verify")
async def verify_invoice(
    invoice: Dict[str, Any],
) -> Dict[str, Any]:
    try:
        result = evaluate_invoice(invoice)
    except Exception as exc:
        raise HTTPException(
            status_code=422,
            detail=str(exc),
        ) from exc

    return JSONResponse(
        content={"data": result},
        status_code=200,
    )


@app.post("/approvals/{invoice_number}/approve")
async def approve_invoice(
    invoice_number: str,
    authorization: str | None = Header(default=None),
) -> Dict[str, Any]:
    access_token = _access_token(authorization)

    try:
        result = await supabase.decide_approval(
            invoice_number,
            True,
            access_token,
        )
    except SupabaseAuthenticationError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    return result


@app.post("/approvals/{invoice_number}/reject")
async def reject_invoice(
    invoice_number: str,
    authorization: str | None = Header(default=None),
) -> Dict[str, Any]:
    access_token = _access_token(authorization)

    try:
        result = await supabase.decide_approval(
            invoice_number,
            False,
            access_token,
        )
    except SupabaseAuthenticationError as exc:
        raise HTTPException(
            status_code=403,
            detail=str(exc),
        ) from exc
    except SupabaseServiceError as exc:
        raise _database_unavailable(exc) from exc

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="Invoice not found",
        )

    return result


def _access_token(
    authorization: str | None,
) -> str:
    if (
        not authorization
        or not authorization.startswith("Bearer ")
    ):
        raise HTTPException(
            status_code=401,
            detail="A Supabase Bearer token is required",
        )

    return authorization.removeprefix("Bearer ").strip()