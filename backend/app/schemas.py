from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VendorSummary(BaseModel):
    vendor_id: str
    vendor_name: str
    vendor_code: Optional[str] = None
    status: str
    risk_level: Optional[str] = None


class PurchaseOrderSummary(BaseModel):
    po_id: str
    po_number: str
    vendor_name: str
    status: str
    quantity: float
    unit_price: float


class InvoiceEvaluation(BaseModel):
    invoice_number: Optional[str] = None
    status: str
    risk_level: str
    risk_score: int
    exception_codes: List[str] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)
    payable_eligible: bool
    approval_required: bool
    audit_ready: bool


class InvoiceRequest(BaseModel):
    invoice_number: str
    vendor: Dict[str, Any]
    po: Dict[str, Any]
    grn: Dict[str, Any]
    invoice_items: List[Dict[str, Any]]
    invoice_total: float
    tax_amount: float = 0.0
    duplicate_of: Optional[str] = None
