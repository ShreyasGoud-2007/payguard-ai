-- =============================================================================
-- PayGuard AI — Complete Database Schema
-- Migration: 001_initial_schema.sql
-- =============================================================================

CREATE TYPE approver_role AS ENUM (
    'STAFF',
    'MANAGER',
    'SENIOR_MANAGER',
    'DIRECTOR',
    'CFO',
    'ADMIN'
);

CREATE TYPE approval_status AS ENUM (
    'PENDING',
    'APPROVED',
    'REJECTED',
    'ESCALATED'
);

CREATE TYPE invoice_status AS ENUM (
    'RECEIVED',
    'UNDER_REVIEW',
    'PENDING_APPROVAL',
    'APPROVED',
    'REJECTED',
    'PAID',
    'CANCELLED',
    'DISPUTED'
);

CREATE TYPE settlement_status AS ENUM (
    'UNPAID',
    'PARTIALLY_PAID',
    'PAID',
    'OVERDUE'
);

CREATE TYPE vendor_status AS ENUM (
    'ACTIVE',
    'INACTIVE',
    'BLACKLISTED'
);

-- =============================================================================
-- USERS TABLE
-- =============================================================================

CREATE TABLE users (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    auth_provider_id    VARCHAR(255)    UNIQUE,
    email               VARCHAR(320)    NOT NULL UNIQUE,
    full_name           VARCHAR(255)    NOT NULL,
    role                approver_role   NOT NULL DEFAULT 'STAFF',
    department          VARCHAR(100),
    is_active           BOOLEAN         NOT NULL DEFAULT TRUE,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_role ON users(role);

-- =============================================================================
-- VENDORS TABLE
-- =============================================================================

CREATE TABLE vendors (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    vendor_name         VARCHAR(255)    NOT NULL,
    tax_id              VARCHAR(50)     UNIQUE,
    email               VARCHAR(320),
    phone               VARCHAR(30),
    address_line1       VARCHAR(255),
    address_line2       VARCHAR(255),
    city                VARCHAR(100),
    state_province      VARCHAR(100),
    postal_code         VARCHAR(20),
    country_code        CHAR(2),
    payment_terms_days  INTEGER         NOT NULL DEFAULT 30,
    CONSTRAINT chk_payment_terms_positive
        CHECK (payment_terms_days > 0),
    bank_account_ref    VARCHAR(255),
    status              vendor_status   NOT NULL DEFAULT 'ACTIVE',
    created_by          UUID            REFERENCES users(id) ON DELETE SET NULL,
    updated_by          UUID            REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_vendors_status     ON vendors(status);
CREATE INDEX idx_vendors_country    ON vendors(country_code);
CREATE INDEX idx_vendors_name       ON vendors(vendor_name);

-- =============================================================================
-- INVOICES TABLE
-- =============================================================================

CREATE TABLE invoices (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number      VARCHAR(100)    NOT NULL UNIQUE,
    vendor_id           UUID            NOT NULL
                            REFERENCES vendors(id) ON DELETE RESTRICT,
    subtotal_amount     NUMERIC(15,2)   NOT NULL,
    tax_amount          NUMERIC(15,2)   NOT NULL DEFAULT 0.00,
    total_amount        NUMERIC(15,2)   NOT NULL,
    CONSTRAINT chk_total_amount_valid
        CHECK (total_amount = subtotal_amount + tax_amount),
    CONSTRAINT chk_amounts_non_negative
        CHECK (subtotal_amount >= 0 AND tax_amount >= 0 AND total_amount >= 0),
    currency_code       CHAR(3)         NOT NULL DEFAULT 'USD',
    invoice_date        DATE            NOT NULL,
    received_date       DATE            NOT NULL DEFAULT CURRENT_DATE,
    due_date            DATE            NOT NULL,
    CONSTRAINT chk_due_date_after_invoice_date
        CHECK (due_date >= invoice_date),
    gl_account_code     VARCHAR(50),
    description         TEXT,
    attachment_url      VARCHAR(2048),
    status              invoice_status  NOT NULL DEFAULT 'RECEIVED',
    created_by          UUID            NOT NULL
                            REFERENCES users(id) ON DELETE RESTRICT,
    updated_by          UUID            REFERENCES users(id) ON DELETE SET NULL,
    created_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_invoices_vendor_id     ON invoices(vendor_id);
CREATE INDEX idx_invoices_status        ON invoices(status);
CREATE INDEX idx_invoices_due_date      ON invoices(due_date);
CREATE INDEX idx_invoices_total_amount  ON invoices(total_amount);
CREATE INDEX idx_invoices_invoice_date  ON invoices(invoice_date);
CREATE INDEX idx_invoices_vendor_status ON invoices(vendor_id, status);

-- =============================================================================
-- INVOICE LINE ITEMS TABLE
-- =============================================================================

CREATE TABLE invoice_line_items (
    id                  UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id          UUID            NOT NULL
                            REFERENCES invoices(id) ON DELETE CASCADE,
    line_number         INTEGER         NOT NULL,
    description         TEXT            NOT NULL,
    quantity            NUMERIC(10,4)   NOT NULL DEFAULT 1,
    unit_price          NUMERIC(15,2)   NOT NULL,
    line_total          NUMERIC(15,2)   NOT NULL,
    CONSTRAINT chk_line_total_valid
        CHECK (ABS(line_total - (quantity * unit_price)) < 0.01),
    gl_account_code     VARCHAR(50),
    CONSTRAINT uq_invoice_line_number
        UNIQUE (invoice_id, line_number),
    CONSTRAINT chk_quantity_positive
        CHECK (quantity > 0),
    CONSTRAINT chk_unit_price_non_negative
        CHECK (unit_price >= 0)
);

CREATE INDEX idx_line_items_invoice_id ON invoice_line_items(invoice_id);

-- =============================================================================
-- APPROVAL THRESHOLDS TABLE
-- =============================================================================

CREATE TABLE approval_thresholds (
    id                      UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    threshold_name          VARCHAR(100)    NOT NULL,
    min_amount              NUMERIC(15,2)   NOT NULL DEFAULT 0.00,
    max_amount              NUMERIC(15,2),
    required_approver_role  approver_role   NOT NULL,
    escalation_days         INTEGER         NOT NULL DEFAULT 3,
    escalation_role         approver_role,
    priority                INTEGER         NOT NULL DEFAULT 1,
    is_active               BOOLEAN         NOT NULL DEFAULT TRUE,
    CONSTRAINT chk_min_amount_non_negative
        CHECK (min_amount >= 0),
    CONSTRAINT chk_max_greater_than_min
        CHECK (max_amount IS NULL OR max_amount > min_amount),
    CONSTRAINT chk_escalation_days_positive
        CHECK (escalation_days > 0),
    created_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at              TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_thresholds_active     ON approval_thresholds(is_active);
CREATE INDEX idx_thresholds_priority   ON approval_thresholds(priority);
CREATE INDEX idx_thresholds_amounts    ON approval_thresholds(min_amount, max_amount);

-- =============================================================================
-- APPROVAL REQUESTS TABLE
-- =============================================================================

CREATE TABLE approval_requests (
    id                          UUID            PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id                  UUID            NOT NULL
                                    REFERENCES invoices(id) ON DELETE RESTRICT,
    threshold_id                UUID            REFERENCES approval_thresholds(id)
                                    ON DELETE SET NULL,
    assigned_approver_id        UUID            REFERENCES users(id) ON DELETE SET NULL,
    required_role               approver_role   NOT NULL,
    status                      approval_status NOT NULL DEFAULT 'PENDING',
    routing_note                TEXT,
    due_by                      TIMESTAMPTZ,
    actioned_at                 TIMESTAMPTZ,
    approver_comments           TEXT,
    escalated_from_request_id   UUID            REFERENCES approval_requests(id)
                                    ON DELETE SET NULL,
    created_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW(),
    updated_at                  TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_approval_req_invoice_id    ON approval_requests(invoice_id);
CREATE INDEX idx_approval_req_approver_id   ON approval_requests(assigned_approver_id);
CREATE INDEX idx_approval_req_status        ON approval_requests(status);
CREATE INDEX idx_approval_req_due_by        ON approval_requests(due_by);
CREATE INDEX idx_approval_req_required_role ON approval_requests(required_role);

-- =============================================================================
-- APPROVAL AUDIT LOG TABLE
-- =============================================================================

CREATE TABLE approval_audit_log (
    id                          BIGSERIAL       PRIMARY KEY,
    invoice_id                  UUID            NOT NULL
                                    REFERENCES invoices(id) ON DELETE RESTRICT,
    approval_request_id         UUID            NOT NULL
                                    REFERENCES approval_requests(id) ON DELETE RESTRICT,
    actor_user_id               UUID            NOT NULL
                                    REFERENCES users(id) ON DELETE RESTRICT,
    actor_role_at_time          approver_role   NOT NULL,
    previous_status             approval_status,
    new_status                  approval_status NOT NULL,
    invoice_status_changed_to   invoice_status,
    invoice_amount_snapshot     NUMERIC(15,2)   NOT NULL,
    comments                    TEXT,
    metadata                    JSONB           DEFAULT '{}',
    action_timestamp            TIMESTAMPTZ     NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_audit_log_invoice_id       ON approval_audit_log(invoice_id);
CREATE INDEX idx_audit_log_actor_user_id    ON approval_audit_log(actor_user_id);
CREATE INDEX idx_audit_log_action_timestamp ON approval_audit_log(action_timestamp DESC);
CREATE INDEX idx_audit_log_new_status       ON approval_audit_log(new_status);
CREATE INDEX idx_audit_log_metadata         ON approval_audit_log USING GIN (metadata);

-- =============================================================================
-- PAYABLE LEDGER TABLE
-- =============================================================================

CREATE TABLE payable_ledger (
    id                  UUID                PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id          UUID                NOT NULL UNIQUE
                            REFERENCES invoices(id) ON DELETE RESTRICT,
    vendor_id           UUID                NOT NULL
                            REFERENCES vendors(id) ON DELETE RESTRICT,
    total_amount        NUMERIC(15,2)       NOT NULL,
    amount_paid         NUMERIC(15,2)       NOT NULL DEFAULT 0.00,
    remaining_balance   NUMERIC(15,2)       NOT NULL,
    CONSTRAINT chk_remaining_balance_valid
        CHECK (ABS(remaining_balance - (total_amount - amount_paid)) < 0.01),
    CONSTRAINT chk_amount_paid_not_exceed_total
        CHECK (amount_paid <= total_amount),
    CONSTRAINT chk_amount_paid_non_negative
        CHECK (amount_paid >= 0),
    CONSTRAINT chk_total_amount_positive
        CHECK (total_amount > 0),
    currency_code       CHAR(3)             NOT NULL DEFAULT 'USD',
    payment_due_date    DATE                NOT NULL,
    last_payment_date   DATE,
    next_payment_date   DATE,
    settlement_status   settlement_status   NOT NULL DEFAULT 'UNPAID',
    payment_reference   VARCHAR(255),
    gl_account_code     VARCHAR(50),
    notes               TEXT,
    posted_by           UUID                NOT NULL
                            REFERENCES users(id) ON DELETE RESTRICT,
    posted_at           TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    created_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ         NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_ledger_invoice_id          ON payable_ledger(invoice_id);
CREATE INDEX idx_ledger_vendor_id           ON payable_ledger(vendor_id);
CREATE INDEX idx_ledger_settlement_status   ON payable_ledger(settlement_status);
CREATE INDEX idx_ledger_payment_due_date    ON payable_ledger(payment_due_date);
CREATE INDEX idx_ledger_status_due_date     ON payable_ledger(settlement_status, payment_due_date);

-- =============================================================================
-- TRIGGERS
-- =============================================================================

CREATE OR REPLACE FUNCTION trigger_set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER set_updated_at_users
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_vendors
    BEFORE UPDATE ON vendors
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_invoices
    BEFORE UPDATE ON invoices
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_approval_thresholds
    BEFORE UPDATE ON approval_thresholds
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_approval_requests
    BEFORE UPDATE ON approval_requests
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE TRIGGER set_updated_at_payable_ledger
    BEFORE UPDATE ON payable_ledger
    FOR EACH ROW EXECUTE FUNCTION trigger_set_updated_at();

CREATE OR REPLACE FUNCTION trigger_log_approval_action()
RETURNS TRIGGER AS $$
DECLARE
    v_actor_role        approver_role;
    v_invoice_amount    NUMERIC(15,2);
    v_invoice_status    invoice_status;
BEGIN
    IF OLD.status IS NOT DISTINCT FROM NEW.status THEN
        RETURN NEW;
    END IF;

    SELECT role INTO v_actor_role
    FROM users
    WHERE id = NEW.assigned_approver_id;

    SELECT total_amount, status INTO v_invoice_amount, v_invoice_status
    FROM invoices
    WHERE id = NEW.invoice_id;

    INSERT INTO approval_audit_log (
        invoice_id,
        approval_request_id,
        actor_user_id,
        actor_role_at_time,
        previous_status,
        new_status,
        invoice_status_changed_to,
        invoice_amount_snapshot,
        action_timestamp
    ) VALUES (
        NEW.invoice_id,
        NEW.id,
        NEW.assigned_approver_id,
        COALESCE(v_actor_role, NEW.required_role),
        OLD.status,
        NEW.status,
        v_invoice_status,
        v_invoice_amount,
        NOW()
    );

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER log_approval_action
    AFTER UPDATE OF status ON approval_requests
    FOR EACH ROW EXECUTE FUNCTION trigger_log_approval_action();

CREATE OR REPLACE FUNCTION trigger_update_settlement_status()
RETURNS TRIGGER AS $$
BEGIN
    NEW.remaining_balance := NEW.total_amount - NEW.amount_paid;

    IF NEW.amount_paid >= NEW.total_amount THEN
        NEW.settlement_status := 'PAID';
    ELSIF NEW.amount_paid > 0 AND NEW.amount_paid < NEW.total_amount THEN
        NEW.settlement_status := 'PARTIALLY_PAID';
    ELSIF NEW.payment_due_date < CURRENT_DATE AND NEW.amount_paid = 0 THEN
        NEW.settlement_status := 'OVERDUE';
    ELSE
        NEW.settlement_status := 'UNPAID';
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_settlement_status
    BEFORE UPDATE OF amount_paid ON payable_ledger
    FOR EACH ROW EXECUTE FUNCTION trigger_update_settlement_status();

-- =============================================================================
-- SEED DATA
-- =============================================================================

INSERT INTO approval_thresholds
    (threshold_name, min_amount, max_amount, required_approver_role,
     escalation_days, escalation_role, priority)
VALUES
    ('Low Value — Staff Approval',      0.00,       999.99,     'STAFF',            5,  'MANAGER',          1),
    ('Standard — Manager Approval',     1000.00,    9999.99,    'MANAGER',          3,  'SENIOR_MANAGER',   2),
    ('High Value — Senior Manager',     10000.00,   49999.99,   'SENIOR_MANAGER',   3,  'DIRECTOR',         3),
    ('Executive Review — Director',     50000.00,   99999.99,   'DIRECTOR',         2,  'CFO',              4),
    ('CFO Authorization — Top Tier',    100000.00,  NULL,       'CFO',              2,  NULL,               5);

-- =============================================================================
-- VIEWS
-- =============================================================================

CREATE OR REPLACE VIEW v_pending_approvals AS
SELECT
    ar.id                           AS request_id,
    ar.status                       AS approval_status,
    ar.due_by,
    ar.routing_note,
    i.id                            AS invoice_id,
    i.invoice_number,
    i.total_amount,
    i.currency_code,
    i.due_date                      AS invoice_due_date,
    i.description                   AS invoice_description,
    v.id                            AS vendor_id,
    v.vendor_name,
    v.email                         AS vendor_email,
    u.full_name                     AS assigned_approver_name,
    u.email                         AS assigned_approver_email,
    ar.required_role,
    at.threshold_name
FROM
    approval_requests ar
    JOIN invoices i          ON i.id  = ar.invoice_id
    JOIN vendors v           ON v.id  = i.vendor_id
    LEFT JOIN users u        ON u.id  = ar.assigned_approver_id
    LEFT JOIN approval_thresholds at ON at.id = ar.threshold_id
WHERE
    ar.status = 'PENDING';

CREATE OR REPLACE VIEW v_payable_ledger_dashboard AS
SELECT
    pl.id                           AS ledger_id,
    pl.settlement_status,
    pl.total_amount,
    pl.amount_paid,
    pl.remaining_balance,
    pl.payment_due_date,
    pl.last_payment_date,
    pl.currency_code,
    pl.payment_reference,
    i.invoice_number,
    i.invoice_date,
    i.description                   AS invoice_description,
    v.vendor_name,
    v.email                         AS vendor_email,
    v.payment_terms_days,
    CASE
        WHEN pl.settlement_status = 'PAID' THEN 0
        ELSE (CURRENT_DATE - pl.payment_due_date)
    END                             AS days_overdue,
    (pl.payment_due_date <= CURRENT_DATE + INTERVAL '7 days'
     AND pl.settlement_status NOT IN ('PAID'))  AS is_due_soon
FROM
    payable_ledger pl
    JOIN invoices i  ON i.id = pl.invoice_id
    JOIN vendors v   ON v.id = pl.vendor_id;

CREATE OR REPLACE VIEW v_invoice_audit_trail AS
SELECT
    aal.id                          AS log_id,
    aal.action_timestamp,
    i.invoice_number,
    aal.invoice_amount_snapshot,
    aal.previous_status,
    aal.new_status,
    u.full_name                     AS actor_name,
    u.email                         AS actor_email,
    aal.actor_role_at_time,
    aal.comments,
    aal.metadata
FROM
    approval_audit_log aal
    JOIN invoices i  ON i.id  = aal.invoice_id
    JOIN users u     ON u.id  = aal.actor_user_id
ORDER BY
    aal.action_timestamp ASC;

-- =============================================================================
-- END OF SCHEMA
-- =============================================================================     ss