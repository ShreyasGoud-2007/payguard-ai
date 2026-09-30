-- Additive Nova source-sync fields. Run after 001_initial_schema.sql.
-- Nova IDs are text (not UUIDs); local primary keys remain UUIDs.

alter table public.vendors
    add column if not exists nova_id text,
    add column if not exists source_created_at timestamptz,
    add column if not exists source_updated_at timestamptz,
    add column if not exists synced_at timestamptz,
    add column if not exists nova_payload jsonb,
    add column if not exists gst_number text,
    add column if not exists pan text,
    add column if not exists state text,
    add column if not exists state_code text,
    add column if not exists category text,
    add column if not exists criticality text,
    add column if not exists payment_terms_days integer,
    add column if not exists early_pay_discount_pct numeric(7, 4),
    add column if not exists late_penalty_pct_per_month numeric(7, 4);
create unique index if not exists vendors_nova_id_unique on public.vendors (nova_id);

alter table public.purchase_orders
    add column if not exists nova_id text,
    add column if not exists source_created_at timestamptz,
    add column if not exists source_updated_at timestamptz,
    add column if not exists synced_at timestamptz,
    add column if not exists nova_payload jsonb,
    add column if not exists source_status text,
    add column if not exists source_vendor_id text,
    add column if not exists order_total numeric(14, 2);
create unique index if not exists purchase_orders_nova_id_unique on public.purchase_orders (nova_id);

alter table public.purchase_order_items
    add column if not exists nova_id text,
    add column if not exists source_item_id text,
    add column if not exists source_gst_rate numeric(7, 4),
    add column if not exists nova_payload jsonb;
create unique index if not exists purchase_order_items_nova_id_unique on public.purchase_order_items (nova_id);
create index if not exists purchase_order_items_source_item_idx on public.purchase_order_items (po_id, source_item_id);

alter table public.goods_receipts
    add column if not exists nova_id text,
    add column if not exists source_created_at timestamptz,
    add column if not exists source_updated_at timestamptz,
    add column if not exists synced_at timestamptz,
    add column if not exists nova_payload jsonb,
    add column if not exists source_status text,
    add column if not exists source_po_id text;
create unique index if not exists goods_receipts_nova_id_unique on public.goods_receipts (nova_id);

alter table public.goods_receipt_items
    add column if not exists nova_id text,
    add column if not exists source_item_id text,
    add column if not exists quantity_rejected numeric(14, 3) not null default 0,
    add column if not exists reject_reason text,
    add column if not exists nova_payload jsonb;
create unique index if not exists goods_receipt_items_nova_id_unique on public.goods_receipt_items (nova_id);
create index if not exists goods_receipt_items_source_item_idx on public.goods_receipt_items (po_id, source_item_id);

alter table public.invoices
    add column if not exists nova_id text,
    add column if not exists source_created_at timestamptz,
    add column if not exists source_updated_at timestamptz,
    add column if not exists synced_at timestamptz,
    add column if not exists nova_payload jsonb,
    add column if not exists source_status text,
    add column if not exists source_approval_status text,
    add column if not exists source_vendor_name text,
    add column if not exists source_vendor_gst_number text,
    add column if not exists payment_terms_days integer,
    add column if not exists source_amount numeric(14, 2),
    add column if not exists gst_amount numeric(14, 2),
    add column if not exists cgst_amount numeric(14, 2),
    add column if not exists sgst_amount numeric(14, 2),
    add column if not exists igst_amount numeric(14, 2),
    add column if not exists currency text,
    add column if not exists paid_amount numeric(14, 2),
    add column if not exists balance_due numeric(14, 2),
    add column if not exists itc_eligible boolean,
    add column if not exists reverse_charge boolean,
    add column if not exists source_grn_id text,
    add column if not exists verification_result jsonb;
create unique index if not exists invoices_nova_id_unique on public.invoices (nova_id);
drop index if exists public.invoices_vendor_number_unique;
create unique index if not exists invoices_manual_vendor_number_unique
    on public.invoices (vendor_id, lower(trim(invoice_number)))
    where nova_id is null;

alter table public.invoices add column if not exists grn_id uuid;
do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.invoices'::regclass
          and conname = 'invoices_grn_id_fkey'
    ) then
        alter table public.invoices
            add constraint invoices_grn_id_fkey
            foreign key (grn_id) references public.goods_receipts(id) on delete restrict;
    end if;
end
$$;

alter table public.invoice_items
    add column if not exists nova_id text,
    add column if not exists source_item_id text,
    add column if not exists gst_amount numeric(14, 2),
    add column if not exists hsn_code text,
    add column if not exists nova_payload jsonb;
create unique index if not exists invoice_items_nova_id_unique on public.invoice_items (nova_id);
create index if not exists invoice_items_source_item_idx on public.invoice_items (invoice_id, source_item_id);

-- Keep source approvals distinct: Nova approvals are evidence, not PayGuard approvals.
create table if not exists public.nova_approvals (
    id uuid primary key default gen_random_uuid(),
    nova_id text not null unique,
    invoice_id uuid references public.invoices(id) on delete set null,
    doc_type text not null,
    source_doc_id text,
    source_action text,
    actor_id text,
    approval_level text,
    threshold_applied numeric(14, 2),
    acted_at timestamptz,
    source_created_at timestamptz,
    source_updated_at timestamptz,
    synced_at timestamptz not null default now(),
    nova_payload jsonb
);
create index if not exists nova_approvals_invoice_idx on public.nova_approvals (invoice_id, acted_at desc);
alter table public.nova_approvals enable row level security;

alter table public.payable_ledger
    add column if not exists nova_bill_id text,
    add column if not exists tax_amount numeric(14, 2),
    add column if not exists total_amount numeric(14, 2),
    add column if not exists source_payment_status text,
    add column if not exists updated_at timestamptz not null default now();

do $$
declare
    constraint_name text;
begin
    for constraint_name in
        select conname from pg_constraint
        where conrelid = 'public.payable_ledger'::regclass
          and contype = 'c'
          and pg_get_constraintdef(oid) ilike '%payment_status%'
    loop
        execute format('alter table public.payable_ledger drop constraint %I', constraint_name);
    end loop;
end
$$;

update public.payable_ledger
set source_payment_status = payment_status,
    payment_status = case upper(payment_status)
        when 'UNPAID' then 'pending'
        when 'PAID' then 'paid'
        when 'OVERDUE' then 'overdue'
        when 'DUE' then 'due'
        else lower(payment_status)
    end
where source_payment_status is null;

do $$
    constraint_name text;
do $$
        add constraint payable_ledger_payment_status_check
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.payable_ledger'::regclass
          and conname = 'payable_ledger_payment_status_check'
    ) then
        check (payment_status in ('pending', 'approved', 'due', 'overdue', 'paid', 'blocked', 'failed', 'on_hold'));
end
$$;
    end if;

alter table public.audit_logs alter column invoice_id drop not null;
alter table public.audit_logs
    add column if not exists entity_type text not null default 'invoice',
    add column if not exists entity_id text,
    add column if not exists previous_state text,
    add column if not exists new_state text,
    add column if not exists reason text,
    add column if not exists source text not null default 'payguard';
update public.audit_logs
set entity_id = invoice_id::text
where entity_id is null and invoice_id is not null;
create index if not exists audit_logs_entity_idx on public.audit_logs (entity_type, entity_id, created_at desc);
