from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from decimal import Decimal, InvalidOperation
from datetime import date, datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4
from difflib import SequenceMatcher
import json
import shutil

from .database import supabase
from .config import settings
from .routes.nova import router as nova_router


# ============================================================
# APP
# ============================================================

app = FastAPI(
    title="PayGuard AI API",
    description="Accounts Payable Control System",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(nova_router)


# ============================================================
# CONSTANTS
# ============================================================

UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB

ALLOWED_EXTENSIONS = {
    ".pdf",
    ".png",
    ".jpg",
    ".jpeg",
}

ALLOWED_INVOICE_TRANSITIONS = {
    "uploaded": {"pending_verification", "rejected"},
    "pending_verification": {
        "verification_failed",
        "pending_approval",
    },
    "verification_failed": {"pending_verification", "rejected"},
    "pending_approval": {"approved", "rejected"},
    "approved": {"posted", "rejected"},
    "rejected": set(),
    "posted": set(),
}


# ============================================================
# PYDANTIC MODELS
# ============================================================

class InvoiceItemCreate(BaseModel):
    description: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    tax_rate: Optional[Decimal] = Field(default=None, ge=0)
    total: Optional[Decimal] = Field(default=None, ge=0)


class InvoiceCreate(BaseModel):
    invoice_number: str
    vendor_id: UUID
    po_id: Optional[UUID] = None
    grn_id: Optional[UUID] = None
    invoice_date: Optional[date] = None
    due_date: Optional[date] = None
    subtotal: Optional[Decimal] = Field(default=None, ge=0)
    tax_amount: Optional[Decimal] = Field(default=None, ge=0)
    discount: Optional[Decimal] = Field(default=Decimal("0"), ge=0)
    total_amount: Optional[Decimal] = Field(default=None, ge=0)
    items: List[InvoiceItemCreate] = Field(default_factory=list)


class POItemCreate(BaseModel):
    description: str
    quantity: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    tax_rate: Optional[Decimal] = Field(default=None, ge=0)
    total: Optional[Decimal] = Field(default=None, ge=0)


class PurchaseOrderCreate(BaseModel):
    po_number: str
    vendor_id: UUID
    order_date: Optional[date] = None
    total_amount: Optional[Decimal] = Field(default=None, ge=0)
    items: List[POItemCreate] = Field(default_factory=list)


class GRItemCreate(BaseModel):
    po_item_id: UUID
    quantity_received: Decimal = Field(gt=0)


class GoodsReceiptCreate(BaseModel):
    grn_number: str
    po_id: UUID
    received_date: Optional[date] = None
    status: str = "received"
    items: List[GRItemCreate] = []


class ApprovalRequest(BaseModel):
    approver_name: str
    approver_role: str
    comments: Optional[str] = None


class RejectionRequest(BaseModel):
    approver_name: str
    approver_role: str
    comments: str


class VendorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    email: Optional[str] = None
    phone: Optional[str] = None
    tax_id: Optional[str] = None
    address: Optional[str] = None
    status: str = "active"


# ============================================================
# HELPERS
# ============================================================

def now_iso():
    return datetime.now(timezone.utc).isoformat()


def money(value: Any) -> Decimal:
    if value is None:
        return Decimal("0")

    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return Decimal("0")


def normalize_text(value: str) -> str:
    return " ".join(value.lower().strip().split())


def similarity(a: str, b: str) -> float:
    return SequenceMatcher(
        None,
        normalize_text(a),
        normalize_text(b),
    ).ratio()


def get_one(table: str, record_id: UUID):
    response = (
        supabase
        .table(table)
        .select("*")
        .eq("id", str(record_id))
        .execute()
    )

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail=f"{table} record not found",
        )

    return response.data[0]


def database_http_error(exc: Exception):
    code = getattr(exc, "code", None)

    if code == "23505":
        raise HTTPException(
            status_code=409,
            detail="A record with a conflicting unique value already exists",
        ) from exc

    if code in {"23503", "23514", "22P02"}:
        raise HTTPException(
            status_code=422,
            detail="Database rejected an invalid relationship or value",
        ) from exc

    raise HTTPException(
        status_code=503,
        detail="Database operation failed",
    ) from exc


def insert_record(table: str, data: dict):
    try:
        response = (
            supabase
            .table(table)
            .insert(data)
            .execute()
        )
    except Exception as exc:
        database_http_error(exc)

    if not response.data:
        raise HTTPException(
            status_code=500,
            detail=f"Could not create {table} record",
        )

    return response.data[0]


def update_record(table: str, record_id: UUID, data: dict):
    try:
        response = (
            supabase
            .table(table)
            .update(data)
            .eq("id", str(record_id))
            .execute()
        )
    except Exception as exc:
        database_http_error(exc)

    if not response.data:
        raise HTTPException(
            status_code=404,
            detail=f"{table} record not found",
        )

    return response.data[0]


def audit(
    invoice_id: UUID,
    action: str,
    performed_by: str = "system",
    details: Optional[dict] = None,
    previous_state: Optional[str] = None,
    new_state: Optional[str] = None,
    reason: Optional[str] = None,
):
    insert_record(
        "audit_logs",
        {
            "invoice_id": str(invoice_id),
            "action": action,
            "performed_by": performed_by,
            "entity_type": "invoice",
            "entity_id": str(invoice_id),
            "previous_state": previous_state,
            "new_state": new_state,
            "reason": reason,
            "source": "payguard",
            "details": details or {},
        },
    )


def change_invoice_status(
    invoice_id: UUID,
    new_status: str,
):
    invoice = get_one("invoices", invoice_id)

    old_status = invoice["status"]

    if old_status == new_status:
        return invoice

    allowed = ALLOWED_INVOICE_TRANSITIONS.get(old_status, set())

    if new_status not in allowed:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Invalid invoice status transition: "
                f"{old_status} -> {new_status}"
            ),
        )

    updated = update_record(
        "invoices",
        invoice_id,
        {
            "status": new_status,
            "updated_at": now_iso(),
        },
    )
    audit(
        invoice_id,
        "invoice_state_changed",
        details={"previous_state": old_status, "new_state": new_status},
        previous_state=old_status,
        new_state=new_status,
    )
    return updated


# ============================================================
# ROOT / HEALTH
# ============================================================

@app.get("/")
def root():
    return {
        "name": "PayGuard AI",
        "message": "Backend is running",
        "status": "healthy",
    }


@app.get("/health")
def health():
    return {"status": "healthy"}


@app.get("/health/db")
def database_health():
    try:
        response = (
            supabase
            .table("vendors")
            .select("id")
            .limit(1)
            .execute()
        )

        return {
            "status": "healthy",
            "database": "connected",
            "rows_checked": len(response.data),
        }

    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed",
        ) from exc


# ============================================================
# VENDORS
# ============================================================

@app.get("/api/vendors")
@app.get("/vendors")
def get_vendors():
    try:
        response = (
            supabase
            .table("vendors")
            .select("*")
            .order("created_at", desc=True)
            .execute()
        )

        return {
            "success": True,
            "count": len(response.data),
            "vendors": response.data,
        }

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve vendors",
        ) from exc


@app.get("/api/vendors/{vendor_id}")
@app.get("/vendors/{vendor_id}")
def get_vendor(vendor_id: UUID):
    return get_one("vendors", vendor_id)


@app.post("/api/vendors", status_code=201)
def create_vendor(payload: VendorCreate):
    if payload.status not in {"active", "inactive", "blocked"}:
        raise HTTPException(status_code=422, detail="Invalid vendor status")

    return {
        "success": True,
        "vendor": insert_record(
            "vendors",
            {
                **payload.model_dump(),
                "risk_level": "low",
                "risk_score": 0,
            },
        ),
    }


# ============================================================
# PURCHASE ORDERS
# ============================================================

@app.get("/api/purchase-orders")
@app.get("/purchase-orders")
def get_purchase_orders():
    response = (
        supabase.table("purchase_orders")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return {"success": True, "count": len(response.data), "purchase_orders": response.data}


@app.post("/api/purchase-orders")
def create_purchase_order(payload: PurchaseOrderCreate):

    vendor = get_one("vendors", payload.vendor_id)
    if vendor.get("status", "active") != "active":
        raise HTTPException(status_code=409, detail="Purchase orders require an active vendor")

    existing = (
        supabase
        .table("purchase_orders")
        .select("id")
        .eq("po_number", payload.po_number)
        .execute()
    )

    if existing.data:
        raise HTTPException(
            status_code=409,
            detail="Purchase order number already exists",
        )

    po = insert_record(
        "purchase_orders",
        {
            "po_number": payload.po_number,
            "vendor_id": str(vendor["id"]),
            "order_date": (
                payload.order_date.isoformat()
                if payload.order_date
                else None
            ),
            "total_amount": (
                str(payload.total_amount)
                if payload.total_amount is not None
                else None
            ),
            "status": "open",
        },
    )

    created_items = []

    for item in payload.items:

        total = (
            item.total
            if item.total is not None
            else item.quantity * item.unit_price
        )

        created_items.append(
            insert_record(
                "purchase_order_items",
                {
                    "po_id": po["id"],
                    "description": item.description,
                    "quantity": str(item.quantity),
                    "unit_price": str(item.unit_price),
                    "tax_rate": (
                        str(item.tax_rate)
                        if item.tax_rate is not None
                        else None
                    ),
                    "total": str(total),
                },
            )
        )

    return {
        "success": True,
        "purchase_order": po,
        "items": created_items,
    }


@app.get("/api/purchase-orders/{po_id}")
@app.get("/purchase-orders/{po_id}")
def get_purchase_order(po_id: UUID):

    po = get_one("purchase_orders", po_id)

    items = (
        supabase
        .table("purchase_order_items")
        .select("*")
        .eq("po_id", str(po_id))
        .execute()
    )

    return {
        "purchase_order": po,
        "items": items.data,
    }


# ============================================================
# GOODS RECEIPTS
# ============================================================

@app.get("/api/goods-receipts")
@app.get("/goods-receipts")
def get_goods_receipts():
    response = (
        supabase.table("goods_receipts")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return {"success": True, "count": len(response.data), "goods_receipts": response.data}


@app.post("/api/goods-receipts")
def create_goods_receipt(payload: GoodsReceiptCreate):

    get_one("purchase_orders", payload.po_id)

    po_items = (
        supabase.table("purchase_order_items")
        .select("id")
        .eq("po_id", str(payload.po_id))
        .execute()
    )
    valid_po_item_ids = {item["id"] for item in po_items.data}

    if any(str(item.po_item_id) not in valid_po_item_ids for item in payload.items):
        raise HTTPException(
            status_code=422,
            detail="Goods receipt item must belong to the selected purchase order",
        )

    gr = insert_record(
        "goods_receipts",
        {
            "grn_number": payload.grn_number,
            "po_id": str(payload.po_id),
            "received_date": (
                payload.received_date.isoformat()
                if payload.received_date
                else None
            ),
            "status": payload.status,
        },
    )

    created_items = []

    for item in payload.items:

        created_items.append(
            insert_record(
                "goods_receipt_items",
                {
                    "grn_id": gr["id"],
                    "po_id": str(payload.po_id),
                    "po_item_id": str(item.po_item_id),
                    "quantity_received": str(item.quantity_received),
                },
            )
        )

    return {
        "success": True,
        "goods_receipt": gr,
        "items": created_items,
    }


@app.get("/api/goods-receipts/{receipt_id}")
@app.get("/goods-receipts/{receipt_id}")
def get_goods_receipt(receipt_id: UUID):

    receipt = get_one("goods_receipts", receipt_id)

    items = (
        supabase
        .table("goods_receipt_items")
        .select("*")
        .eq("grn_id", str(receipt_id))
        .execute()
    )

    return {
        "goods_receipt": receipt,
        "items": items.data,
    }


# ============================================================
# INVOICE CREATION
# ============================================================

@app.get("/api/invoices")
@app.get("/api/purchase-bills")
@app.get("/invoices")
@app.get("/purchase-bills")
def get_invoices():
    response = (
        supabase.table("invoices")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return {"success": True, "count": len(response.data), "invoices": response.data}


def create_invoice_record(payload: InvoiceCreate):

    vendor = get_one("vendors", payload.vendor_id)
    if vendor.get("status", "active") != "active":
        raise HTTPException(status_code=409, detail="Invoices require an active vendor")

    po_id = payload.po_id
    if payload.grn_id:
        receipt = get_one("goods_receipts", payload.grn_id)
        receipt_po_id = UUID(str(receipt["po_id"]))
        if po_id and po_id != receipt_po_id:
            raise HTTPException(
                status_code=422,
                detail="Invoice goods receipt must belong to the selected purchase order",
            )
        po_id = receipt_po_id

    if po_id:
        po = get_one("purchase_orders", po_id)
        if str(po.get("vendor_id")) != str(payload.vendor_id):
            raise HTTPException(
                status_code=422,
                detail="Invoice vendor must match purchase order vendor",
            )

    existing = (
        supabase
        .table("invoices")
        .select("id")
        .eq("invoice_number", payload.invoice_number)
        .eq("vendor_id", str(payload.vendor_id))
        .execute()
    )

    if existing.data:
        raise HTTPException(
            status_code=409,
            detail="Invoice already exists for this vendor",
        )

    invoice = insert_record(
        "invoices",
        {
            "invoice_number": payload.invoice_number,
            "vendor_id": str(payload.vendor_id),
            "po_id": (
                str(po_id)
                if po_id
                else None
            ),
            "grn_id": str(payload.grn_id) if payload.grn_id else None,
            "invoice_date": (
                payload.invoice_date.isoformat()
                if payload.invoice_date
                else None
            ),
            "due_date": (
                payload.due_date.isoformat()
                if payload.due_date
                else None
            ),
            "subtotal": (
                str(payload.subtotal)
                if payload.subtotal is not None
                else None
            ),
            "tax_amount": (
                str(payload.tax_amount)
                if payload.tax_amount is not None
                else None
            ),
            "discount": str(payload.discount or 0),
            "total_amount": (
                str(payload.total_amount)
                if payload.total_amount is not None
                else None
            ),
            "status": "uploaded",
            "verification_status": "pending",
            "risk_level": "low",
            "risk_score": 0,
        },
    )

    created_items = []

    for item in payload.items:

        total = (
            item.total
            if item.total is not None
            else item.quantity * item.unit_price
        )

        created_items.append(
            insert_record(
                "invoice_items",
                {
                    "invoice_id": invoice["id"],
                    "description": item.description,
                    "quantity": str(item.quantity),
                    "unit_price": str(item.unit_price),
                    "tax_rate": (
                        str(item.tax_rate)
                        if item.tax_rate is not None
                        else None
                    ),
                    "total": str(total),
                },
            )
        )

    invoice_id = UUID(invoice["id"])

    audit(
        invoice_id,
        "invoice_created",
        details={
            "invoice_number": payload.invoice_number,
        },
    )

    return invoice, created_items


@app.post("/api/invoices")
def create_invoice(payload: InvoiceCreate):
    invoice, items = create_invoice_record(payload)

    return {
        "success": True,
        "invoice": invoice,
        "items": items,
    }


# ============================================================
# INVOICE UPLOAD
# ============================================================

@app.post("/api/invoices/upload")
@app.post("/api/invoice/upload")
async def upload_invoice(
    file: UploadFile = File(...),
    invoice_number: str = Form(...),
    vendor_id: UUID = Form(...),
    po_id: Optional[UUID] = Form(None),
    grn_id: Optional[UUID] = Form(None),
    invoice_date: Optional[date] = Form(None),
    due_date: Optional[date] = Form(None),
    subtotal: Optional[Decimal] = Form(None),
    tax_amount: Optional[Decimal] = Form(None),
    discount: Optional[Decimal] = Form(Decimal("0")),
    total_amount: Optional[Decimal] = Form(None),
):

    extension = Path(file.filename or "").suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail="Unsupported invoice file type",
        )

    vendor = get_one("vendors", vendor_id)
    if vendor.get("status", "active") != "active":
        raise HTTPException(status_code=409, detail="Invoices require an active vendor")

    if grn_id:
        receipt = get_one("goods_receipts", grn_id)
        receipt_po_id = UUID(str(receipt["po_id"]))
        if po_id and po_id != receipt_po_id:
            raise HTTPException(
                status_code=422,
                detail="Invoice goods receipt must belong to the selected purchase order",
            )
        po_id = receipt_po_id

    if po_id:
        po = get_one("purchase_orders", po_id)
        if str(po.get("vendor_id")) != str(vendor_id):
            raise HTTPException(
                status_code=422,
                detail="Invoice vendor must match purchase order vendor",
            )

    existing = (
        supabase
        .table("invoices")
        .select("id")
        .eq("invoice_number", invoice_number)
        .eq("vendor_id", str(vendor_id))
        .execute()
    )

    if existing.data:
        raise HTTPException(
            status_code=409,
            detail="Duplicate invoice detected",
        )

    safe_name = (
        f"{uuid4()}_{Path(file.filename).name}"
    )

    file_path = UPLOAD_DIR / safe_name

    size = 0

    try:
        with file_path.open("wb") as buffer:
            while True:
                chunk = await file.read(1024 * 1024)

                if not chunk:
                    break

                size += len(chunk)

                if size > MAX_FILE_SIZE:
                    file_path.unlink(missing_ok=True)

                    raise HTTPException(
                        status_code=400,
                        detail="Invoice file exceeds 10 MB limit",
                    )

                buffer.write(chunk)

    finally:
        await file.close()

    invoice = insert_record(
        "invoices",
        {
            "invoice_number": invoice_number,
            "vendor_id": str(vendor_id),
            "po_id": str(po_id) if po_id else None,
            "grn_id": str(grn_id) if grn_id else None,
            "invoice_date": invoice_date.isoformat() if invoice_date else None,
            "due_date": due_date.isoformat() if due_date else None,
            "subtotal": (
                str(subtotal)
                if subtotal is not None
                else None
            ),
            "tax_amount": (
                str(tax_amount)
                if tax_amount is not None
                else None
            ),
            "discount": str(discount or 0),
            "total_amount": (
                str(total_amount)
                if total_amount is not None
                else None
            ),
            "status": "uploaded",
            "verification_status": "pending",
            "risk_level": "low",
            "risk_score": 0,
            "file_path": str(file_path),
        },
    )

    invoice_id = UUID(invoice["id"])

    audit(
        invoice_id,
        "invoice_uploaded",
        details={
            "filename": file.filename,
            "file_size": size,
        },
    )

    return {
        "success": True,
        "message": "Invoice uploaded successfully",
        "invoice": invoice,
    }


# ============================================================
# INVOICE DETAILS
# ============================================================

@app.get("/api/invoices/{invoice_id}")
@app.get("/api/purchase-bills/{invoice_id}")
@app.get("/purchase-bills/{invoice_id}")
@app.get("/invoice/{invoice_id}")
def get_invoice(invoice_id: UUID):

    invoice = get_one("invoices", invoice_id)

    vendor = None
    po = None
    items = []
    approvals = []
    audit_logs = []
    payable = None

    if invoice.get("vendor_id"):
        vendor = get_one(
            "vendors",
            UUID(invoice["vendor_id"]),
        )

    if invoice.get("po_id"):
        po = get_one(
            "purchase_orders",
            UUID(invoice["po_id"]),
        )

    items_response = (
        supabase
        .table("invoice_items")
        .select("*")
        .eq("invoice_id", str(invoice_id))
        .execute()
    )

    items = items_response.data

    approvals_response = (
        supabase
        .table("approvals")
        .select("*")
        .eq("invoice_id", str(invoice_id))
        .order("created_at", desc=True)
        .execute()
    )

    approvals = approvals_response.data

    audit_response = (
        supabase
        .table("audit_logs")
        .select("*")
        .eq("invoice_id", str(invoice_id))
        .order("created_at", desc=True)
        .execute()
    )

    audit_logs = audit_response.data

    payable_response = (
        supabase
        .table("payable_ledger")
        .select("*")
        .eq("invoice_id", str(invoice_id))
        .execute()
    )

    if payable_response.data:
        payable = payable_response.data[0]

    return {
        "invoice": invoice,
        "vendor": vendor,
        "purchase_order": po,
        "items": items,
        "approvals": approvals,
        "payable": payable,
        "audit_logs": audit_logs,
    }


# ============================================================
# DUPLICATE DETECTION
# ============================================================

def detect_duplicates(invoice: dict):

    invoice_id = invoice["id"]
    vendor_id = invoice.get("vendor_id")
    invoice_number = invoice.get("invoice_number", "")
    total_amount = money(invoice.get("total_amount"))

    if not vendor_id:
        return {
            "is_duplicate": False,
            "is_suspicious": False,
            "similarity_score": 0.0,
            "matched_invoice_id": None,
            "signals": {},
            "reason": None,
        }

    response = (
        supabase
        .table("invoices")
        .select("*")
        .eq("vendor_id", vendor_id)
        .neq("id", invoice_id)
        .execute()
    )

    best_number_score = 0.0
    best_amount_score = 0.0
    best_signals = {}
    best_composite_score = -1.0
    best_invoice = None
    current_items = (
        supabase.table("invoice_items")
        .select("source_item_id,description,quantity,unit_price")
        .eq("invoice_id", str(invoice_id))
        .execute()
        .data
    )

    for other in response.data:

        other_number = other.get("invoice_number", "")

        if normalize_text(invoice_number) == normalize_text(
            other_number
        ):
            return {
                "is_duplicate": True,
                "is_suspicious": False,
                "similarity_score": 1.0,
                "matched_invoice_id": other["id"],
                "signals": {
                    "same_vendor": True,
                    "same_bill_number": True,
                    "same_amount": total_amount == money(other.get("total_amount")),
                    "same_bill_date": invoice.get("invoice_date") == other.get("invoice_date"),
                    "same_purchase_order": invoice.get("po_id") == other.get("po_id"),
                },
                "classification": "exact_duplicate",
                "reason": "Same vendor and invoice number",
            }

        number_score = similarity(
            invoice_number,
            other_number,
        )

        other_amount = money(other.get("total_amount"))

        amount_score = 0

        if total_amount > 0 and other_amount > 0:
            difference = abs(
                total_amount - other_amount
            )

            amount_score = max(
                Decimal("0"),
                Decimal("1")
                - (
                    difference
                    / max(total_amount, other_amount)
                ),
            )

        date_match = bool(
            invoice.get("invoice_date")
            and other.get("invoice_date")
            and invoice.get("invoice_date") == other.get("invoice_date")
        )
        po_match = bool(
            invoice.get("po_id")
            and other.get("po_id")
            and str(invoice.get("po_id")) == str(other.get("po_id"))
        )
        line_match = False

        if number_score >= 0.70 and amount_score >= 0.90 and current_items:
            other_items = (
                supabase.table("invoice_items")
                .select("source_item_id,description,quantity,unit_price")
                .eq("invoice_id", str(other["id"]))
                .execute()
                .data
            )
            current_source_ids = {
                str(item.get("source_item_id"))
                for item in current_items
                if item.get("source_item_id")
            }
            other_source_ids = {
                str(item.get("source_item_id"))
                for item in other_items
                if item.get("source_item_id")
            }
            line_match = bool(current_source_ids & other_source_ids)
            if not line_match:
                line_match = any(
                    similarity(left.get("description", ""), right.get("description", "")) >= 0.90
                    and abs(money(left.get("quantity")) - money(right.get("quantity"))) <= Decimal("0.001")
                    and abs(money(left.get("unit_price")) - money(right.get("unit_price"))) <= Decimal("0.01")
                    for left in current_items
                    for right in other_items
                )

        signals = {
            "same_vendor": True,
            "bill_number_similarity": round(number_score, 3),
            "amount_similarity": round(float(amount_score), 3),
            "same_bill_date": date_match,
            "same_purchase_order": po_match,
            "matching_line_item": line_match,
        }
        context_score = int(date_match) + int(po_match) + int(line_match)
        composite_score = (
            number_score * 0.4
            + float(amount_score) * 0.3
            + int(date_match) * 0.1
            + int(po_match) * 0.1
            + int(line_match) * 0.1
        )

        if composite_score > best_composite_score:
            best_composite_score = composite_score
            best_number_score = number_score
            best_amount_score = float(amount_score)
            best_signals = {**signals, "context_matches": context_score}
            best_invoice = other

    suspicious = (
        best_number_score >= 0.80
        and best_amount_score >= 0.95
        and best_signals.get("context_matches", 0) >= 1
    )

    reason = (
        "Similar bill number and amount with matching date, PO, or line items"
        if suspicious
        else None
    )

    return {
        "is_duplicate": False,
        "is_suspicious": suspicious,
        "classification": "suspicious_similarity" if suspicious else "none",
        "similarity_score": round(best_number_score, 3),
        "amount_similarity_score": round(best_amount_score, 3),
        "signals": best_signals,
        "matched_invoice_id": (
            best_invoice["id"]
            if best_invoice
            else None
        ),
        "reason": reason,
    }


@app.get("/invoice/{invoice_id}/verification")
def get_invoice_verification(invoice_id: UUID):
    invoice = get_one("invoices", invoice_id)
    return {
        "invoice_id": str(invoice_id),
        "status": invoice.get("verification_status"),
        "verification": invoice.get("verification_result"),
        "risk_score": invoice.get("risk_score"),
        "risk_level": invoice.get("risk_level"),
        "risk_reasons": invoice.get("risk_reasons", []),
    }


@app.get("/invoice/{invoice_id}/approvals")
def get_invoice_approvals(invoice_id: UUID):
    get_one("invoices", invoice_id)
    response = (
        supabase.table("approvals")
        .select("*")
        .eq("invoice_id", str(invoice_id))
        .order("created_at", desc=True)
        .execute()
    )
    return {"invoice_id": str(invoice_id), "count": len(response.data), "approvals": response.data}


@app.get("/api/invoices/{invoice_id}/duplicate-check")
def duplicate_check(invoice_id: UUID):

    invoice = get_one("invoices", invoice_id)

    result = detect_duplicates(invoice)

    audit(
        invoice_id,
        "duplicate_check_completed",
        details=result,
    )

    return result


# ============================================================
# FINANCIAL VALIDATION
# ============================================================

def financial_validation(invoice_id: UUID):

    invoice = get_one("invoices", invoice_id)

    response = (
        supabase
        .table("invoice_items")
        .select("*")
        .eq("invoice_id", str(invoice_id))
        .execute()
    )

    items = response.data

    issues = []

    calculated_subtotal = Decimal("0")
    calculated_tax = Decimal("0")
    line_tax_match = True
    tax_rates_present = False

    for item in items:

        quantity = money(item.get("quantity"))
        unit_price = money(item.get("unit_price"))
        line_subtotal = quantity * unit_price

        if quantity <= 0 or unit_price < 0:
            issues.append(
                f"Invalid quantity or unit price for {item.get('description')}"
            )

        calculated_subtotal += line_subtotal

        tax_rate = item.get("tax_rate")
        if tax_rate is not None:
            tax_rates_present = True
            expected_line_tax = line_subtotal * money(tax_rate) / Decimal("100")
            calculated_tax += expected_line_tax
            if item.get("gst_amount") is not None and abs(
                expected_line_tax - money(item.get("gst_amount"))
            ) > Decimal("0.01"):
                line_tax_match = False
                issues.append(
                    f"GST amount does not match rate for {item.get('description')}"
                )
        elif item.get("gst_amount") is not None:
            calculated_tax += money(item.get("gst_amount"))

        item_total = item.get("total")
        if item_total is not None and abs(line_subtotal - money(item_total)) > Decimal("0.01"):
            issues.append(
                f"Invoice line total does not match quantity and unit price for {item.get('description')}"
            )

    if not items:
        issues.append("Invoice has no line items")

    invoice_subtotal = invoice.get("subtotal")

    subtotal_match = invoice_subtotal is not None and abs(
        calculated_subtotal - money(invoice_subtotal)
    ) <= Decimal("0.01")

    if not subtotal_match:
        issues.append("Invoice subtotal is missing or does not match invoice items")

    tax_amount = money(invoice.get("tax_amount"))
    discount = money(invoice.get("discount"))

    calculated_tax_match = (
        not tax_rates_present
        or abs(calculated_tax - tax_amount) <= Decimal("0.01")
    )

    if not calculated_tax_match:
        issues.append("Invoice GST does not match line tax rates")

    source_gst_match = (
        invoice.get("gst_amount") is None
        or abs(money(invoice.get("gst_amount")) - tax_amount) <= Decimal("0.01")
    )
    if not source_gst_match:
        issues.append("Invoice GST amount does not match its tax amount")

    gst_components_present = any(
        invoice.get(field) is not None
        for field in ("cgst_amount", "sgst_amount", "igst_amount")
    )
    cgst_amount = money(invoice.get("cgst_amount"))
    sgst_amount = money(invoice.get("sgst_amount"))
    igst_amount = money(invoice.get("igst_amount"))
    tax_component_match = (
        not gst_components_present
        or abs(cgst_amount + sgst_amount + igst_amount - tax_amount) <= Decimal("0.01")
    )
    if not tax_component_match:
        issues.append("CGST, SGST, and IGST components do not sum to invoice GST")

    if igst_amount > Decimal("0.01") and (
        cgst_amount > Decimal("0.01") or sgst_amount > Decimal("0.01")
    ):
        tax_component_match = False
        issues.append("Invoice cannot combine IGST with CGST/SGST")

    if (invoice.get("cgst_amount") is not None) != (invoice.get("sgst_amount") is not None):
        tax_component_match = False
        issues.append("Both CGST and SGST must be provided together")
    elif invoice.get("cgst_amount") is not None and abs(cgst_amount - sgst_amount) > Decimal("0.01"):
        tax_component_match = False
        issues.append("CGST and SGST amounts must match")

    tax_match = (
        calculated_tax_match
        and source_gst_match
        and tax_component_match
        and line_tax_match
    )

    if discount > calculated_subtotal + tax_amount:
        issues.append("Invoice discount exceeds subtotal and tax")

    calculated_total = (
        calculated_subtotal
        + tax_amount
        - discount
    )

    invoice_total = invoice.get("total_amount")

    total_match = invoice_total is not None and abs(
        calculated_total - money(invoice_total)
    ) <= Decimal("0.01")

    if not total_match:
        issues.append("Invoice total is missing or does not match calculated total")

    return {
        "valid": len(issues) == 0,
        "calculated_subtotal": float(
            calculated_subtotal
        ),
        "calculated_total": float(
            calculated_total
        ),
        "subtotal_match": subtotal_match,
        "tax_match": tax_match,
        "line_tax_match": line_tax_match,
        "gst_component_match": tax_component_match,
        "source_gst_match": source_gst_match,
        "calculated_tax": float(calculated_tax),
        "total_match": total_match,
        "issues": issues,
    }


@app.get("/api/invoices/{invoice_id}/financial-validation")
def validate_financials(invoice_id: UUID):

    result = financial_validation(invoice_id)

    audit(
        invoice_id,
        "financial_validation_completed",
        details=result,
    )

    return result


# ============================================================
# PURCHASE VERIFICATION / 3-WAY MATCH
# ============================================================

def verify_invoice(invoice_id: UUID):

    invoice = get_one("invoices", invoice_id)

    issues = []

    vendor_match = True
    po_match = True
    po_status_match = True
    quantity_match = True
    price_match = True
    goods_received = True
    po_amount_match = True

    if not invoice.get("po_id"):

        issues.append("Invoice has no purchase order")

        po_match = False

        goods_received = False

    else:

        po = get_one(
            "purchase_orders",
            UUID(invoice["po_id"]),
        )

        if (
            invoice.get("vendor_id")
            != po.get("vendor_id")
        ):
            vendor_match = False
            issues.append(
                "Invoice vendor does not match PO vendor"
            )

        if str(po.get("status", "open")).lower() == "cancelled":
            po_status_match = False
            issues.append("Purchase order is cancelled")

        po_items_response = (
            supabase
            .table("purchase_order_items")
            .select("*")
            .eq("po_id", invoice["po_id"])
            .execute()
        )

        po_items = po_items_response.data

        gr_response = (
            supabase
            .table("goods_receipts")
            .select("*")
            .eq("po_id", invoice["po_id"])
            .execute()
        )

        goods_receipts = [
            receipt for receipt in gr_response.data
            if receipt.get("status", "received").lower() in {"received", "accepted", "completed"}
        ]

        if invoice.get("grn_id"):
            referenced_grn_id = str(invoice["grn_id"])
            referenced_grn = next(
                (receipt for receipt in gr_response.data if str(receipt["id"]) == referenced_grn_id),
                None,
            )
            if not referenced_grn:
                goods_received = False
                issues.append("Referenced goods receipt does not belong to the purchase order")
            elif referenced_grn not in goods_receipts:
                goods_received = False
                issues.append("Referenced goods receipt is not in an accepted state")
            else:
                goods_receipts = [referenced_grn]

        received_by_po_item = {}

        for gr in goods_receipts:

            gri_response = (
                supabase
                .table("goods_receipt_items")
                .select("*")
                .eq("grn_id", gr["id"])
                .execute()
            )

            for gri in gri_response.data:

                po_item_id = gri.get("po_item_id")
                accepted_quantity = max(
                    Decimal("0"),
                    money(gri.get("quantity_received"))
                    - money(gri.get("quantity_rejected")),
                )

                received_by_po_item[po_item_id] = (
                    received_by_po_item.get(
                        po_item_id,
                        Decimal("0"),
                    )
                    + accepted_quantity
                )

        if not goods_receipts:
            goods_received = False
            issues.append(
                "No goods receipt found for PO"
            )

        invoice_items_response = (
            supabase
            .table("invoice_items")
            .select("*")
            .eq("invoice_id", str(invoice_id))
            .execute()
        )

        invoice_items = invoice_items_response.data

        invoiced_by_po_item = {}

        for invoice_item in invoice_items:

            description = normalize_text(
                invoice_item.get("description", "")
            )

            source_item_id = str(invoice_item.get("source_item_id") or "")
            if source_item_id:
                matching_po = next(
                    (
                        item for item in po_items
                        if str(item.get("source_item_id") or "") == source_item_id
                    ),
                    None,
                )
            else:
                matching_po = max(
                    po_items,
                    key=lambda item: similarity(
                        description,
                        item.get("description", ""),
                    ),
                    default=None,
                )

                if matching_po and similarity(
                    description,
                    matching_po.get("description", ""),
                ) < 0.80:
                    matching_po = None

            if not matching_po:

                issues.append(
                    f"No matching PO item for: "
                    f"{invoice_item.get('description')}"
                )

                quantity_match = False
                price_match = False
                continue

            invoice_quantity = money(
                invoice_item.get("quantity")
            )
            po_item_id = matching_po["id"]
            invoiced_by_po_item[po_item_id] = (
                invoiced_by_po_item.get(po_item_id, Decimal("0"))
                + invoice_quantity
            )

            invoice_price = money(
                invoice_item.get("unit_price")
            )

            po_price = money(
                matching_po.get("unit_price")
            )

            price_tolerance = max(
                Decimal("0.01"),
                po_price * settings.price_tolerance_percent / Decimal("100"),
            )
            if abs(invoice_price - po_price) > price_tolerance:

                price_match = False

                issues.append(
                    f"Invoice price differs from PO price "
                    f"for {invoice_item.get('description')}"
                )

        other_invoices = (
            supabase.table("invoices")
            .select("id,total_amount")
            .eq("po_id", invoice["po_id"])
            .neq("status", "rejected")
            .neq("id", str(invoice_id))
            .execute()
        )
        invoiced_by_other_invoices = {}

        for other_invoice in other_invoices.data:
            other_items = (
                supabase.table("invoice_items")
                .select("*")
                .eq("invoice_id", other_invoice["id"])
                .execute()
            )

            for other_item in other_items.data:
                other_source_item_id = str(other_item.get("source_item_id") or "")
                if other_source_item_id:
                    candidate = next(
                        (
                            item for item in po_items
                            if str(item.get("source_item_id") or "") == other_source_item_id
                        ),
                        None,
                    )
                else:
                    candidate = max(
                        po_items,
                        key=lambda item: similarity(
                            other_item.get("description", ""),
                            item.get("description", ""),
                        ),
                        default=None,
                    )

                if candidate and (
                    other_source_item_id
                    or similarity(
                        other_item.get("description", ""),
                        candidate.get("description", ""),
                    ) >= 0.80
                ):
                    candidate_id = candidate["id"]
                    invoiced_by_other_invoices[candidate_id] = (
                        invoiced_by_other_invoices.get(candidate_id, Decimal("0"))
                        + money(other_item.get("quantity"))
                    )

        for po_item_id, invoice_quantity in invoiced_by_po_item.items():
            matching_po = next(item for item in po_items if item["id"] == po_item_id)
            po_quantity = money(matching_po.get("quantity"))
            received_quantity = received_by_po_item.get(po_item_id, Decimal("0"))
            total_invoiced_quantity = (
                invoice_quantity
                + invoiced_by_other_invoices.get(po_item_id, Decimal("0"))
            )

            if total_invoiced_quantity > po_quantity:
                quantity_match = False
                issues.append(
                    f"Total invoiced quantity exceeds PO quantity for {matching_po.get('description')}"
                )

            if total_invoiced_quantity > received_quantity:

                goods_received = False

                issues.append(
                    f"Total invoiced quantity exceeds received quantity for {matching_po.get('description')}"
                )

        po_total = po.get("total_amount")
        invoice_total = invoice.get("total_amount")
        previously_invoiced_amount = sum(
            (money(other.get("total_amount")) for other in other_invoices.data),
            Decimal("0"),
        )
        if (
            po_total is not None
            and invoice_total is not None
            and previously_invoiced_amount + money(invoice_total) > money(po_total) + Decimal("0.01")
        ):
            po_amount_match = False
            issues.append("Cumulative invoice total exceeds purchase order amount")

    financial = financial_validation(invoice_id)

    if not financial["valid"]:
        issues.extend(financial["issues"])

    duplicate = detect_duplicates(invoice)

    if duplicate["is_duplicate"] or duplicate.get("is_suspicious", False):
        issues.append(
            duplicate["reason"] or "Duplicate invoice detected"
        )

    verified = (
        vendor_match
        and po_match
        and po_status_match
        and quantity_match
        and price_match
        and goods_received
        and po_amount_match
        and financial["valid"]
        and not duplicate["is_duplicate"]
        and len(issues) == 0
    )

    risk_score = 0

    if not vendor_match:
        risk_score += 20

    if not po_match:
        risk_score += 20

    if not quantity_match:
        risk_score += 20

    if not price_match:
        risk_score += 15

    if not goods_received:
        risk_score += 15

    if not po_amount_match:
        risk_score += 15

    if not financial["valid"]:
        risk_score += 20

    if duplicate["is_duplicate"] or duplicate.get("is_suspicious", False):
        risk_score += 40

    risk_score = min(risk_score, 100)

    if risk_score >= 70:
        risk_level = "high"
    elif risk_score >= 30:
        risk_level = "medium"
    else:
        risk_level = "low"

    checks = [
        {
            "name": "vendor_match",
            "status": "passed" if vendor_match else "failed",
            "message": "Bill vendor matches its purchase order" if vendor_match else "Bill vendor does not match its purchase order",
            "details": {"vendor_match": vendor_match},
        },
        {
            "name": "purchase_order",
            "status": "passed" if po_match and po_status_match else "failed",
            "message": "Purchase order exists and is acceptable" if po_match and po_status_match else "Purchase order is missing, mismatched, or cancelled",
            "details": {"po_match": po_match, "status_acceptable": po_status_match},
        },
        {
            "name": "goods_receipt",
            "status": "passed" if goods_received else "failed",
            "message": "Required goods receipt is associated and sufficient" if goods_received else "Goods receipt is missing, mismatched, or insufficient",
            "details": {"goods_received": goods_received},
        },
        {
            "name": "quantity",
            "status": "passed" if quantity_match else "failed",
            "message": "Billed quantities are within PO limits" if quantity_match else "Billed quantities exceed ordered quantities",
            "details": {"quantity_match": quantity_match},
        },
        {
            "name": "price",
            "status": "passed" if price_match else "failed",
            "message": "Bill prices are within configured tolerance" if price_match else "Bill prices exceed configured tolerance",
            "details": {"price_match": price_match, "tolerance_percent": str(settings.price_tolerance_percent)},
        },
        {
            "name": "gst_and_totals",
            "status": "passed" if financial["valid"] else "failed",
            "message": "Line amounts, GST, and bill totals reconcile" if financial["valid"] else "Financial or GST validation failed",
            "details": financial,
        },
        {
            "name": "duplicate_detection",
            "status": "failed" if duplicate["is_duplicate"] else "warning" if duplicate.get("is_suspicious") else "passed",
            "message": duplicate.get("reason") or "No duplicate or suspicious bill match detected",
            "details": duplicate,
        },
        {
            "name": "purchase_order_exposure",
            "status": "passed" if po_amount_match else "failed",
            "message": "Cumulative billing is within PO value" if po_amount_match else "Cumulative billing exceeds PO value",
            "details": {"po_amount_match": po_amount_match},
        },
        {
            "name": "nova_approval",
            "status": "warning" if invoice.get("source_approval_status") else "passed",
            "message": "Nova approval is informational; PayGuard approval is still required" if invoice.get("source_approval_status") else "No Nova approval state was supplied",
            "details": {
                "source_approval_status": invoice.get("source_approval_status"),
                "payguard_approval_required": True,
            },
        },
    ]
    verification_result = {
        "passed": verified,
        "status": "verified" if verified else "exceptions",
        "checks": checks,
        "issues": issues,
    }

    update_record(
        "invoices",
        invoice_id,
        {
            "verification_status": (
                "verified"
                if verified
                else "failed"
            ),
            "risk_level": risk_level,
            "risk_score": risk_score,
            "risk_reasons": issues,
            "verification_result": verification_result,
            "updated_at": now_iso(),
        },
    )

    return {
        "verified": verified,
        "passed": verified,
        "status": verification_result["status"],
        "checks": checks,
        "vendor_match": vendor_match,
        "po_match": po_match,
        "quantity_match": quantity_match,
        "price_match": price_match,
        "goods_received": goods_received,
        "po_amount_match": po_amount_match,
        "duplicate": duplicate,
        "financial_validation": financial,
        "risk_score": risk_score,
        "risk_level": risk_level,
        "issues": issues,
    }


@app.post("/api/invoices/{invoice_id}/verify")
@app.post("/invoice/{invoice_id}/verify")
def verify_invoice_endpoint(invoice_id: UUID):

    invoice = get_one("invoices", invoice_id)

    if invoice["status"] not in {
        "uploaded",
        "pending_verification",
        "verification_failed",
    }:
        raise HTTPException(
            status_code=409,
            detail="Invoice cannot be verified in its current state",
        )

    if invoice["status"] == "verification_failed":
        change_invoice_status(invoice_id, "pending_verification")

    result = verify_invoice(invoice_id)

    if result["duplicate"]["is_duplicate"] or result["duplicate"].get("is_suspicious", False):
        audit(
            invoice_id,
            "duplicate_detected",
            details=result["duplicate"],
        )

    if result["verified"]:

        current = get_one("invoices", invoice_id)
        if current["status"] == "uploaded":
            change_invoice_status(invoice_id, "pending_verification")

        change_invoice_status(
            invoice_id,
            "pending_approval",
        )

    else:

        current = get_one(
            "invoices",
            invoice_id,
        )

        if current["status"] == "uploaded":
            change_invoice_status(
                invoice_id,
                "pending_verification",
            )

        current = get_one(
            "invoices",
            invoice_id,
        )

        if current["status"] == "pending_verification":
            change_invoice_status(
                invoice_id,
                "verification_failed",
            )

    audit(
        invoice_id,
        "invoice_verification_completed",
        details=result,
    )

    return result


# ============================================================
# RISK
# ============================================================

@app.get("/api/invoices/{invoice_id}/risk")
def get_invoice_risk(invoice_id: UUID):

    invoice = get_one("invoices", invoice_id)

    return {
        "invoice_id": invoice_id,
        "risk_score": invoice.get("risk_score"),
        "risk_level": invoice.get("risk_level"),
        "risk_reasons": invoice.get("risk_reasons", []),
        "verification_status": invoice.get(
            "verification_status"
        ),
    }


# ============================================================
# APPROVAL
# ============================================================

@app.post("/api/invoices/{invoice_id}/approve")
@app.post("/invoice/{invoice_id}/approve")
def approve_invoice(
    invoice_id: UUID,
    payload: ApprovalRequest,
):

    invoice = get_one("invoices", invoice_id)

    if invoice["status"] != "pending_approval":
        raise HTTPException(
            status_code=409,
            detail=(
                "Invoice is not waiting for approval"
            ),
        )

    if invoice["verification_status"] != "verified":
        raise HTTPException(
            status_code=409,
            detail="Invoice has not passed verification",
        )

    financial = financial_validation(invoice_id)

    if not financial["valid"]:
        raise HTTPException(
            status_code=409,
            detail={
                "message": "Financial validation failed",
                "issues": financial["issues"],
            },
        )

    duplicate = detect_duplicates(invoice)

    if duplicate["is_duplicate"] or duplicate.get("is_suspicious", False):
        raise HTTPException(
            status_code=409,
            detail="Duplicate or suspicious invoice cannot be approved",
        )

    amount = money(invoice.get("total_amount"))

    required_approvals = 2 if amount > settings.approval_threshold else 1

    existing = (
        supabase
        .table("approvals")
        .select("*")
        .eq("invoice_id", str(invoice_id))
        .eq("status", "approved")
        .execute()
    )

    already_approved = len(existing.data)

    if any(
        normalize_text(record.get("approver_name", ""))
        == normalize_text(payload.approver_name)
        for record in existing.data
    ):
        raise HTTPException(
            status_code=409,
            detail="An approver cannot approve the same invoice more than once",
        )

    if already_approved >= required_approvals:
        raise HTTPException(
            status_code=409,
            detail="Required approvals already completed",
        )

    approval = insert_record(
        "approvals",
        {
            "invoice_id": str(invoice_id),
            "approver_name": payload.approver_name,
            "approver_role": payload.approver_role,
            "status": "approved",
            "comments": payload.comments,
            "approved_at": now_iso(),
        },
    )

    total_approvals = already_approved + 1

    if total_approvals >= required_approvals:

        change_invoice_status(
            invoice_id,
            "approved",
        )

        final_status = "approved"

    else:
        final_status = "pending_approval"

    audit(
        invoice_id,
        "invoice_approved",
        performed_by=payload.approver_name,
        details={
            "approval_id": approval["id"],
            "required_approvals": required_approvals,
            "completed_approvals": total_approvals,
        },
    )

    return {
        "success": True,
        "approval": approval,
        "required_approvals": required_approvals,
        "completed_approvals": total_approvals,
        "invoice_status": final_status,
    }


@app.post("/api/invoices/{invoice_id}/reject")
@app.post("/invoice/{invoice_id}/reject")
def reject_invoice(
    invoice_id: UUID,
    payload: RejectionRequest,
):

    invoice = get_one("invoices", invoice_id)

    if invoice["status"] not in {
        "pending_approval",
        "verification_failed",
    }:
        raise HTTPException(
            status_code=409,
            detail="Invoice cannot be rejected in its current state",
        )

    approval = insert_record(
        "approvals",
        {
            "invoice_id": str(invoice_id),
            "approver_name": payload.approver_name,
            "approver_role": payload.approver_role,
            "status": "rejected",
            "comments": payload.comments,
            "approved_at": now_iso(),
        },
    )

    current = get_one(
        "invoices",
        invoice_id,
    )

    if current["status"] != "rejected":
        change_invoice_status(
            invoice_id,
            "rejected",
        )

    audit(
        invoice_id,
        "invoice_rejected",
        performed_by=payload.approver_name,
        details={
            "reason": payload.comments,
        },
    )

    return {
        "success": True,
        "approval": approval,
        "status": "rejected",
    }


# ============================================================
# PAYABLE LEDGER
# ============================================================

@app.post("/api/invoices/{invoice_id}/post-payable")
def post_payable(invoice_id: UUID):

    invoice = get_one("invoices", invoice_id)

    existing = (
        supabase.table("payable_ledger")
        .select("*")
        .eq("invoice_id", str(invoice_id))
        .execute()
    )
    if existing.data:
        return {
            "success": True,
            "message": "Invoice already exists in payable ledger",
            "already_exists": True,
            "payable": existing.data[0],
        }

    if invoice["status"] != "approved":
        raise HTTPException(
            status_code=409,
            detail="Only approved invoices can be posted",
        )

    if invoice["verification_status"] != "verified":
        raise HTTPException(
            status_code=409,
            detail="Invoice has not passed verification",
        )

    financial = financial_validation(invoice_id)

    if not financial["valid"]:
        raise HTTPException(
            status_code=409,
            detail="Financial validation failed",
        )

    duplicate = detect_duplicates(invoice)

    if duplicate["is_duplicate"] or duplicate.get("is_suspicious", False):
        raise HTTPException(
            status_code=409,
            detail="Duplicate or suspicious invoice cannot become payable",
        )

    amount = money(invoice.get("total_amount"))
    required_approvals = 2 if amount > settings.approval_threshold else 1
    approvals = (
        supabase.table("approvals")
        .select("id")
        .eq("invoice_id", str(invoice_id))
        .eq("status", "approved")
        .execute()
    )
    if len(approvals.data) < required_approvals:
        raise HTTPException(
            status_code=409,
            detail="Required approvals are not complete",
        )

    payable = insert_record(
        "payable_ledger",
        {
            "invoice_id": str(invoice_id),
            "vendor_id": invoice.get("vendor_id"),
            "approved_amount": invoice.get("total_amount"),
            "tax_amount": invoice.get("tax_amount"),
            "total_amount": invoice.get("total_amount"),
            "nova_bill_id": invoice.get("nova_id"),
            "approval_date": now_iso(),
            "due_date": invoice.get("due_date"),
            "payment_status": "pending",
            "payment_reference": None,
        },
    )

    change_invoice_status(
        invoice_id,
        "posted",
    )

    audit(
        invoice_id,
        "invoice_posted_to_payable",
        details={
            "payable_id": payable["id"],
            "amount": invoice.get("total_amount"),
        },
    )

    return {
        "success": True,
        "message": "Invoice posted to payable ledger",
        "payable": payable,
    }


@app.get("/api/payables")
@app.get("/payables")
def get_payables():

    response = (
        supabase
        .table("payable_ledger")
        .select("*")
        .order("created_at", desc=True)
        .execute()
    )

    return {
        "success": True,
        "count": len(response.data),
        "payables": response.data,
    }


# ============================================================
# AUDIT
# ============================================================

@app.get("/api/audit/{entity_id}")
@app.get("/audit/{entity_id}")
def get_audit(entity_id: str):
    try:
        invoice_id = UUID(entity_id)
    except ValueError:
        invoice_id = None

    query = supabase.table("audit_logs").select("*")
    if invoice_id:
        get_one("invoices", invoice_id)
        query = query.eq("invoice_id", str(invoice_id))
    else:
        query = query.eq("entity_id", entity_id)

    response = query.order("created_at", desc=True).execute()
    if not response.data and invoice_id is None:
        raise HTTPException(status_code=404, detail="Audit entity not found")

    return {
        "entity_id": entity_id,
        "invoice_id": str(invoice_id) if invoice_id else None,
        "count": len(response.data),
        "audit_logs": response.data,
    }