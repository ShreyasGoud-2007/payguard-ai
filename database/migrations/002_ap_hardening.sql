-- =============================================================================
-- PayGuard AI — AP Control hardening
-- Additive migration for missing AP workflow tables and validation columns.
-- Safe for existing shared schema: this migration does not drop or rewrite tables.
-- =============================================================================

CREATE TABLE IF NOT EXISTS purchase_orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_number VARCHAR(100) NOT NULL UNIQUE,
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE RESTRICT,
    status VARCHAR(30) NOT NULL DEFAULT 'DRAFT'
        CHECK (status IN ('DRAFT','APPROVED','REJECTED','CANCELLED')),
    po_date DATE NOT NULL DEFAULT CURRENT_DATE,
    total_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS purchase_order_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    po_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE CASCADE,
    line_number INTEGER NOT NULL,
    description TEXT NOT NULL,
    quantity NUMERIC(12,4) NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(15,2) NOT NULL CHECK (unit_price >= 0),
    line_total NUMERIC(15,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (po_id, line_number)
);

CREATE TABLE IF NOT EXISTS goods_receipts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grn_number VARCHAR(100) NOT NULL UNIQUE,
    po_id UUID NOT NULL REFERENCES purchase_orders(id) ON DELETE RESTRICT,
    vendor_id UUID NOT NULL REFERENCES vendors(id) ON DELETE RESTRICT,
    received_date DATE NOT NULL DEFAULT CURRENT_DATE,
    status VARCHAR(30) NOT NULL DEFAULT 'RECEIVED'
        CHECK (status IN ('RECEIVED','PARTIAL','PENDING','REJECTED')),
    total_received_quantity NUMERIC(12,4) NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS goods_receipt_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    grn_id UUID NOT NULL REFERENCES goods_receipts(id) ON DELETE CASCADE,
    po_item_id UUID REFERENCES purchase_order_items(id) ON DELETE SET NULL,
    description TEXT NOT NULL,
    quantity_received NUMERIC(12,4) NOT NULL CHECK (quantity_received >= 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (grn_id, description)
);

CREATE TABLE IF NOT EXISTS invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    po_item_id UUID REFERENCES purchase_order_items(id) ON DELETE SET NULL,
    line_number INTEGER NOT NULL,
    description TEXT NOT NULL,
    quantity NUMERIC(12,4) NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(15,2) NOT NULL CHECK (unit_price >= 0),
    tax_amount NUMERIC(15,2) NOT NULL DEFAULT 0,
    total_amount NUMERIC(15,2) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (invoice_id, line_number)
);

CREATE TABLE IF NOT EXISTS approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    approver_id UUID REFERENCES users(id) ON DELETE SET NULL,
    approval_state VARCHAR(30) NOT NULL DEFAULT 'PENDING'
        CHECK (approval_state IN ('PENDING','APPROVED','REJECTED','ESCALATED')),
    approved_amount NUMERIC(15,2) NOT NULL DEFAULT 0 CHECK (approved_amount >= 0),
    comments TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    invoice_id UUID REFERENCES invoices(id) ON DELETE SET NULL,
    entity_type VARCHAR(50) NOT NULL,
    entity_id UUID,
    action VARCHAR(100) NOT NULL,
    actor VARCHAR(255),
    actor_role VARCHAR(50),
    details JSONB NOT NULL DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE invoices
    ADD COLUMN IF NOT EXISTS po_id UUID REFERENCES purchase_orders(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS verification_status VARCHAR(30) NOT NULL DEFAULT 'PENDING',
    ADD COLUMN IF NOT EXISTS risk_level VARCHAR(20) NOT NULL DEFAULT 'LOW',
    ADD COLUMN IF NOT EXISTS risk_score INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS duplicate_check_status VARCHAR(30) NOT NULL DEFAULT 'CLEAR',
    ADD COLUMN IF NOT EXISTS duplicate_of_invoice_id UUID REFERENCES invoices(id) ON DELETE SET NULL,
    ADD COLUMN IF NOT EXISTS payable_eligible BOOLEAN NOT NULL DEFAULT FALSE;

ALTER TABLE invoices
    DROP CONSTRAINT IF EXISTS chk_total_amount_valid;

ALTER TABLE invoices
    ADD CONSTRAINT chk_total_amount_valid
        CHECK (total_amount = subtotal_amount + tax_amount);

CREATE INDEX IF NOT EXISTS idx_invoices_verification_status
    ON invoices(verification_status);

CREATE INDEX IF NOT EXISTS idx_invoices_risk_level
    ON invoices(risk_level);

CREATE INDEX IF NOT EXISTS idx_invoices_due_date
    ON invoices(due_date);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_vendor_id
    ON purchase_orders(vendor_id);

CREATE INDEX IF NOT EXISTS idx_purchase_orders_status
    ON purchase_orders(status);

CREATE INDEX IF NOT EXISTS idx_goods_receipts_po_id
    ON goods_receipts(po_id);

CREATE INDEX IF NOT EXISTS idx_goods_receipts_vendor_id
    ON goods_receipts(vendor_id);

CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice_id
    ON invoice_items(invoice_id);

CREATE INDEX IF NOT EXISTS idx_approvals_invoice_id
    ON approvals(invoice_id);

CREATE INDEX IF NOT EXISTS idx_approvals_state
    ON approvals(approval_state);

CREATE INDEX IF NOT EXISTS idx_audit_logs_invoice_id
    ON audit_logs(invoice_id);

CREATE INDEX IF NOT EXISTS idx_audit_logs_action
    ON audit_logs(action);

CREATE INDEX IF NOT EXISTS idx_audit_logs_created_at
    ON audit_logs(created_at DESC);

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS set_updated_at_purchase_orders ON purchase_orders;
CREATE TRIGGER set_updated_at_purchase_orders
    BEFORE UPDATE ON purchase_orders
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS set_updated_at_goods_receipts ON goods_receipts;
CREATE TRIGGER set_updated_at_goods_receipts
    BEFORE UPDATE ON goods_receipts
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

DROP TRIGGER IF EXISTS set_updated_at_approvals ON approvals;
CREATE TRIGGER set_updated_at_approvals
    BEFORE UPDATE ON approvals
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

-- =============================================================================
-- Use this migration only for additive AP workflow improvements.
-- =============================================================================
