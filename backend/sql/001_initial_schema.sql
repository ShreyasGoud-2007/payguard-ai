-- PayGuard AI initial PostgreSQL schema (run in the Supabase SQL editor).
-- The backend uses a server-side Supabase service-role key; do not expose it to clients.

create table if not exists public.vendors (
    id uuid primary key default gen_random_uuid(),
    name text not null check (length(trim(name)) > 0),
    vendor_code text,
    email text,
    phone text,
    tax_id text,
    address text,
    status text not null default 'active' check (status in ('active', 'inactive', 'blocked')),
    risk_level text not null default 'low' check (risk_level in ('low', 'medium', 'high')),
    risk_score integer not null default 0 check (risk_score between 0 and 100),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

alter table public.vendors add column if not exists vendor_code text;
alter table public.vendors add column if not exists address text;
alter table public.vendors
    add column if not exists risk_score integer not null default 0;

create table if not exists public.purchase_orders (
    id uuid primary key default gen_random_uuid(),
    po_number text not null,
    vendor_id uuid not null references public.vendors(id) on delete restrict,
    order_date date,
    total_amount numeric(14, 2) check (total_amount is null or total_amount >= 0),
    status text not null default 'open' check (status in ('open', 'partially_received', 'received', 'closed', 'cancelled')),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create unique index if not exists purchase_orders_id_vendor_id_unique
    on public.purchase_orders (id, vendor_id);

create unique index if not exists purchase_orders_number_unique
    on public.purchase_orders (lower(trim(po_number)));

create table if not exists public.purchase_order_items (
    id uuid primary key default gen_random_uuid(),
    po_id uuid not null references public.purchase_orders(id) on delete cascade,
    description text not null check (length(trim(description)) > 0),
    quantity numeric(14, 3) not null check (quantity > 0),
    unit_price numeric(14, 4) not null check (unit_price >= 0),
    tax_rate numeric(7, 4) check (tax_rate is null or tax_rate >= 0),
    total numeric(14, 2) not null check (total >= 0),
    created_at timestamptz not null default now()
);

create unique index if not exists purchase_order_items_id_po_id_unique
    on public.purchase_order_items (id, po_id);

create table if not exists public.goods_receipts (
    id uuid primary key default gen_random_uuid(),
    grn_number text not null,
    po_id uuid not null references public.purchase_orders(id) on delete restrict,
    received_date date,
    status text not null default 'received' check (status in ('received', 'accepted', 'completed', 'rejected', 'cancelled')),
    created_at timestamptz not null default now()
);

create unique index if not exists goods_receipts_id_po_id_unique
    on public.goods_receipts (id, po_id);

create unique index if not exists goods_receipts_number_unique
    on public.goods_receipts (lower(trim(grn_number)));

create table if not exists public.goods_receipt_items (
    id uuid primary key default gen_random_uuid(),
    grn_id uuid not null,
    po_id uuid not null,
    po_item_id uuid not null,
    quantity_received numeric(14, 3) not null check (quantity_received > 0),
    created_at timestamptz not null default now(),
    foreign key (grn_id, po_id) references public.goods_receipts(id, po_id) on delete cascade,
    foreign key (po_item_id, po_id) references public.purchase_order_items(id, po_id) on delete restrict,
    unique (grn_id, po_item_id)
);

alter table public.goods_receipt_items add column if not exists po_id uuid;
update public.goods_receipt_items receipt_item
set po_id = receipt.po_id
from public.goods_receipts receipt
where receipt_item.grn_id = receipt.id
  and receipt_item.po_id is null;
alter table public.goods_receipt_items alter column po_id set not null;

do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.goods_receipt_items'::regclass
          and conname = 'goods_receipt_items_grn_po_fkey'
    ) then
        alter table public.goods_receipt_items
            add constraint goods_receipt_items_grn_po_fkey
            foreign key (grn_id, po_id)
            references public.goods_receipts (id, po_id)
            on delete cascade;
    end if;
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.goods_receipt_items'::regclass
          and conname = 'goods_receipt_items_po_item_po_fkey'
    ) then
        alter table public.goods_receipt_items
            add constraint goods_receipt_items_po_item_po_fkey
            foreign key (po_item_id, po_id)
            references public.purchase_order_items (id, po_id)
            on delete restrict;
    end if;
end
$$;

create unique index if not exists goods_receipt_items_grn_po_item_unique
    on public.goods_receipt_items (grn_id, po_item_id);

create table if not exists public.invoices (
    id uuid primary key default gen_random_uuid(),
    invoice_number text not null,
    vendor_id uuid not null references public.vendors(id) on delete restrict,
    po_id uuid,
    invoice_date date,
    due_date date,
    subtotal numeric(14, 2) check (subtotal is null or subtotal >= 0),
    tax_amount numeric(14, 2) check (tax_amount is null or tax_amount >= 0),
    discount numeric(14, 2) not null default 0 check (discount >= 0),
    total_amount numeric(14, 2) check (total_amount is null or total_amount >= 0),
    status text not null default 'uploaded' check (status in ('uploaded', 'pending_verification', 'verification_failed', 'pending_approval', 'approved', 'rejected', 'posted')),
    verification_status text not null default 'pending' check (verification_status in ('pending', 'verified', 'failed')),
    risk_level text not null default 'low' check (risk_level in ('low', 'medium', 'high')),
    risk_score integer not null default 0 check (risk_score between 0 and 100),
    risk_reasons jsonb not null default '[]'::jsonb,
    file_path text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    foreign key (po_id, vendor_id) references public.purchase_orders(id, vendor_id) on delete restrict
);

alter table public.invoices
    add column if not exists risk_reasons jsonb not null default '[]'::jsonb;

create unique index if not exists invoices_vendor_number_unique
    on public.invoices (vendor_id, lower(trim(invoice_number)));
do $$
begin
    if not exists (
        select 1 from pg_constraint
        where conrelid = 'public.invoices'::regclass
          and conname = 'invoices_po_vendor_fkey'
    ) then
        alter table public.invoices
            add constraint invoices_po_vendor_fkey
            foreign key (po_id, vendor_id)
            references public.purchase_orders (id, vendor_id)
            on delete restrict;
    end if;
end
$$;
create index if not exists invoices_status_created_idx
    on public.invoices (status, created_at desc);

create table if not exists public.invoice_items (
    id uuid primary key default gen_random_uuid(),
    invoice_id uuid not null references public.invoices(id) on delete cascade,
    description text not null check (length(trim(description)) > 0),
    quantity numeric(14, 3) not null check (quantity > 0),
    unit_price numeric(14, 4) not null check (unit_price >= 0),
    tax_rate numeric(7, 4) check (tax_rate is null or tax_rate >= 0),
    total numeric(14, 2) not null check (total >= 0),
    created_at timestamptz not null default now()
);

create table if not exists public.approvals (
    id uuid primary key default gen_random_uuid(),
    invoice_id uuid not null references public.invoices(id) on delete restrict,
    approver_name text not null check (length(trim(approver_name)) > 0),
    approver_role text not null check (length(trim(approver_role)) > 0),
    status text not null check (status in ('approved', 'rejected')),
    comments text,
    approved_at timestamptz not null default now(),
    created_at timestamptz not null default now()
);
create unique index if not exists approvals_one_per_approver_unique
    on public.approvals (invoice_id, lower(trim(approver_name)))
    where status = 'approved';
create index if not exists approvals_invoice_status_idx
    on public.approvals (invoice_id, status);

create table if not exists public.payable_ledger (
    id uuid primary key default gen_random_uuid(),
    invoice_id uuid not null unique references public.invoices(id) on delete restrict,
    vendor_id uuid not null references public.vendors(id) on delete restrict,
    approved_amount numeric(14, 2) not null check (approved_amount >= 0),
    approval_date timestamptz not null default now(),
    due_date date,
    payment_status text not null default 'pending' check (payment_status in ('pending', 'approved', 'due', 'overdue', 'paid', 'blocked', 'failed', 'on_hold')),
    payment_reference text,
    created_at timestamptz not null default now()
);
create unique index if not exists payable_ledger_invoice_unique
    on public.payable_ledger (invoice_id);

create table if not exists public.audit_logs (
    id uuid primary key default gen_random_uuid(),
    invoice_id uuid not null references public.invoices(id) on delete restrict,
    action text not null,
    performed_by text not null default 'system',
    details jsonb not null default '{}'::jsonb,
    created_at timestamptz not null default now()
);
create index if not exists audit_logs_invoice_created_idx
    on public.audit_logs (invoice_id, created_at desc);

-- All access is through the private backend using a service-role key.
alter table public.vendors enable row level security;
alter table public.purchase_orders enable row level security;
alter table public.purchase_order_items enable row level security;
alter table public.goods_receipts enable row level security;
alter table public.goods_receipt_items enable row level security;
alter table public.invoices enable row level security;
alter table public.invoice_items enable row level security;
alter table public.approvals enable row level security;
alter table public.payable_ledger enable row level security;
alter table public.audit_logs enable row level security;
