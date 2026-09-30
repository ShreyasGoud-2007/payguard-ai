-- =============================================================================
-- PayGuard AI demo seed data
-- Intended for a fresh local or development database only.
-- Do not run against the shared production or team Supabase instance.
-- =============================================================================

BEGIN;

-- The demo scenarios were designed to match the AP control workflow:
-- INV-1001 = clean approved invoice
-- INV-1002 = quantity mismatch
-- INV-1003 = price mismatch
-- INV-1004 = duplicate invoice suspicion

WITH user_seed AS (
    INSERT INTO users (id, email, full_name, role, is_active)
    VALUES
        ('11111111-1111-1111-1111-111111111111', 'ops@abc-tech.local', 'Operations User', 'STAFF', TRUE)
    ON CONFLICT (email) DO NOTHING
    RETURNING id
)
SELECT 1;

WITH vendor_seed AS (
    INSERT INTO vendors (id, vendor_name, tax_id, email, phone, status)
    VALUES (
        '22222222-2222-2222-2222-222222222222',
        'ABC Technologies Pvt Ltd',
        'TAX-ABCTECH-001',
        'accounts@abctechnologies.example',
        '+91-99999-99999',
        'ACTIVE'
    )
    ON CONFLICT (tax_id) DO NOTHING
    RETURNING id
)
SELECT 1;

WITH po_seed AS (
    INSERT INTO purchase_orders (id, po_number, vendor_id, status, po_date, total_amount)
    VALUES
        ('33333333-3333-3333-3333-333333333333', 'PO-1001', '22222222-2222-2222-2222-222222222222', 'APPROVED', CURRENT_DATE - 10, 85000.00),
        ('33333333-3333-3333-4444-333333333333', 'PO-1002', '22222222-2222-2222-2222-222222222222', 'APPROVED', CURRENT_DATE - 9, 48000.00),
        ('33333333-3333-3333-5555-333333333333', 'PO-1003', '22222222-2222-2222-2222-222222222222', 'APPROVED', CURRENT_DATE - 8, 19000.00)
    ON CONFLICT (po_number) DO NOTHING
    RETURNING id
)
SELECT 1;

WITH grn_seed AS (
    INSERT INTO goods_receipts (id, grn_number, po_id, vendor_id, received_date, status, total_received_quantity)
    VALUES
        ('44444444-4444-4444-4444-444444444444', 'GRN-1001', '33333333-3333-3333-3333-333333333333', '22222222-2222-2222-2222-222222222222', CURRENT_DATE - 7, 'RECEIVED', 100),
        ('44444444-4444-4444-5555-444444444444', 'GRN-1002', '33333333-3333-3333-4444-333333333333', '22222222-2222-2222-2222-222222222222', CURRENT_DATE - 6, 'RECEIVED', 40),
        ('44444444-4444-4444-6666-444444444444', 'GRN-1003', '33333333-3333-3333-5555-333333333333', '22222222-2222-2222-2222-222222222222', CURRENT_DATE - 5, 'RECEIVED', 20)
    ON CONFLICT (grn_number) DO NOTHING
    RETURNING id
)
SELECT 1;

INSERT INTO invoices (
    id,
    invoice_number,
    vendor_id,
    subtotal_amount,
    tax_amount,
    total_amount,
    invoice_date,
    received_date,
    due_date,
    description,
    status,
    created_by,
    verification_status,
    risk_level,
    risk_score,
    payable_eligible
)
VALUES
    ('55555555-5555-5555-5555-555555555555', 'INV-1001', '22222222-2222-2222-2222-222222222222', 85000.00, 0.00, 85000.00, CURRENT_DATE - 5, CURRENT_DATE - 4, CURRENT_DATE + 20, 'Business Laptop invoice', 'APPROVED', '11111111-1111-1111-1111-111111111111', 'APPROVED', 'LOW', 0, TRUE),
    ('55555555-5555-5555-6666-555555555555', 'INV-1002', '22222222-2222-2222-2222-222222222222', 72000.00, 0.00, 72000.00, CURRENT_DATE - 5, CURRENT_DATE - 3, CURRENT_DATE + 15, 'Monitor invoice mismatch', 'UNDER_REVIEW', '11111111-1111-1111-1111-111111111111', 'UNDER_REVIEW', 'HIGH', 50, FALSE),
    ('55555555-5555-5555-7777-555555555555', 'INV-1003', '22222222-2222-2222-2222-222222222222', 19180.00, 0.00, 19180.00, CURRENT_DATE - 4, CURRENT_DATE - 2, CURRENT_DATE + 18, 'Printer price mismatch', 'UNDER_REVIEW', '11111111-1111-1111-1111-111111111111', 'UNDER_REVIEW', 'MEDIUM', 30, FALSE),
    ('55555555-5555-5555-8888-555555555555', 'INV-1004', '22222222-2222-2222-2222-222222222222', 85000.00, 0.00, 85000.00, CURRENT_DATE - 4, CURRENT_DATE - 2, CURRENT_DATE + 12, 'Possible duplicate invoice', 'UNDER_REVIEW', '11111111-1111-1111-1111-111111111111', 'UNDER_REVIEW', 'HIGH', 50, FALSE)
ON CONFLICT (invoice_number) DO NOTHING;

INSERT INTO invoice_items (id, invoice_id, line_number, description, quantity, unit_price, tax_amount, total_amount)
VALUES
    ('66666666-6666-6666-6666-666666666666', '55555555-5555-5555-5555-555555555555', 1, 'Business Laptop', 100, 850.00, 0.00, 85000.00),
    ('66666666-6666-6666-7777-666666666666', '55555555-5555-5555-6666-555555555555', 1, 'Computer Monitor', 60, 1200.00, 0.00, 72000.00),
    ('66666666-6666-6666-8888-666666666666', '55555555-5555-5555-7777-555555555555', 1, 'Laser Printer', 20, 959.00, 0.00, 19180.00),
    ('66666666-6666-6666-9999-666666666666', '55555555-5555-5555-8888-555555555555', 1, 'Business Laptop', 100, 850.00, 0.00, 85000.00)
ON CONFLICT DO NOTHING;

INSERT INTO approvals (id, invoice_id, approver_id, approval_state, approved_amount, comments)
VALUES
    ('77777777-7777-7777-7777-777777777777', '55555555-5555-5555-5555-555555555555', '11111111-1111-1111-1111-111111111111', 'APPROVED', 85000.00, 'Approved with no AP exceptions'),
    ('77777777-7777-7777-8888-777777777777', '55555555-5555-5555-6666-555555555555', '11111111-1111-1111-1111-111111111111', 'PENDING', 0.00, 'Under review due to quantity mismatch'),
    ('77777777-7777-7777-9999-777777777777', '55555555-5555-5555-7777-555555555555', '11111111-1111-1111-1111-111111111111', 'PENDING', 0.00, 'Under review due to price variance'),
    ('77777777-7777-7777-aaaa-777777777777', '55555555-5555-5555-8888-555555555555', '11111111-1111-1111-1111-111111111111', 'PENDING', 0.00, 'Duplicate suspected and sent for manual review')
ON CONFLICT DO NOTHING;

INSERT INTO payable_ledger (id, invoice_id, vendor_id, total_amount, amount_paid, remaining_balance, currency_code, payment_due_date, settlement_status, posted_by)
VALUES
    ('88888888-8888-8888-8888-888888888888', '55555555-5555-5555-5555-555555555555', '22222222-2222-2222-2222-222222222222', 85000.00, 0.00, 85000.00, 'USD', CURRENT_DATE + 20, 'UNPAID', '11111111-1111-1111-1111-111111111111')
ON CONFLICT (invoice_id) DO NOTHING;

INSERT INTO audit_logs (invoice_id, entity_type, entity_id, action, actor, actor_role, details)
VALUES
    ('55555555-5555-5555-5555-555555555555', 'INVOICE', '55555555-5555-5555-5555-555555555555', 'INVOICE_VERIFIED', 'Operations User', 'STAFF', '{"status":"APPROVED","reason":"Clean invoice matched to PO and GRN"}'),
    ('55555555-5555-5555-6666-555555555555', 'INVOICE', '55555555-5555-5555-6666-555555555555', 'QUANTITY_MISMATCH', 'Operations User', 'STAFF', '{"status":"UNDER_REVIEW","reason":"Invoice quantity exceeds received quantity"}'),
    ('55555555-5555-5555-7777-555555555555', 'INVOICE', '55555555-5555-5555-7777-555555555555', 'PRICE_MISMATCH', 'Operations User', 'STAFF', '{"status":"UNDER_REVIEW","reason":"Invoice unit price differs from PO price"}'),
    ('55555555-5555-5555-8888-555555555555', 'INVOICE', '55555555-5555-5555-8888-555555555555', 'DUPLICATE_SUSPECTED', 'Operations User', 'STAFF', '{"status":"UNDER_REVIEW","reason":"Possible duplicate invoice detected against INV-1001"}')
ON CONFLICT DO NOTHING;

COMMIT;
