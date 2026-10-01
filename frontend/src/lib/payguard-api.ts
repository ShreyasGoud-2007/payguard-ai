// Real API client for PayGuard backend
const API_BASE_URL = 'http://127.0.0.1:8000';

export const payguardApi = {
  // Health checks
  async getHealth() {
    const response = await fetch(`${API_BASE_URL}/health`);
    if (!response.ok) throw new Error('Backend unhealthy');
    return response.json();
  },

  async getDbHealth() {
    const response = await fetch(`${API_BASE_URL}/health/db`);
    if (!response.ok) throw new Error('Database unhealthy');
    return response.json();
  },

  // Invoices
  async listInvoices() {
    const response = await fetch(`${API_BASE_URL}/invoices`);
    if (!response.ok) throw new Error('Failed to fetch invoices');
    const data = await response.json();
    return data.invoices || [];
  },

  async getInvoice(id: string) {
    const response = await fetch(`${API_BASE_URL}/invoice/${id}`);
    if (!response.ok) throw new Error('Failed to fetch invoice');
    return response.json();
  },

  async uploadInvoice(file: File, metadata: {
    invoice_number: string;
    vendor_id: string;
    po_id?: string;
    grn_id?: string;
    invoice_date?: string;
    due_date?: string;
    subtotal?: number;
    tax_amount?: number;
    total_amount: number;
  }) {
    const formData = new FormData();
    formData.append('file', file);
    Object.entries(metadata).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        formData.append(key, value.toString());
      }
    });

    const response = await fetch(`${API_BASE_URL}/api/invoice/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Upload failed');
    }

    return response.json();
  },

  async approveInvoice(id: string, approverName: string, comments?: string) {
    const response = await fetch(`${API_BASE_URL}/invoice/${id}/approve`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        approver_name: approverName,
        approver_role: 'AP_MANAGER',
        comments 
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Approval failed');
    }
    return response.json();
  },

  async holdInvoice(id: string, approverName: string, reason: string) {
    const response = await fetch(`${API_BASE_URL}/invoice/${id}/reject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        approver_name: approverName,
        approver_role: 'AP_MANAGER',
        comments: reason 
      }),
    });
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Hold failed');
    }
    return response.json();
  },

  // Vendors
  async getVendors() {
    const response = await fetch(`${API_BASE_URL}/vendors`);
    if (!response.ok) throw new Error('Failed to fetch vendors');
    const data = await response.json();
    return data.vendors || [];
  },

  // Purchase Orders
  async getPurchaseOrders() {
    const response = await fetch(`${API_BASE_URL}/purchase-orders`);
    if (!response.ok) throw new Error('Failed to fetch purchase orders');
    const data = await response.json();
    return data.purchase_orders || [];
  },

  // Goods Receipts
  async getGoodsReceipts() {
    const response = await fetch(`${API_BASE_URL}/goods-receipts`);
    if (!response.ok) throw new Error('Failed to fetch goods receipts');
    const data = await response.json();
    return data.goods_receipts || [];
  },

  // Payables
  async getPayables() {
    const response = await fetch(`${API_BASE_URL}/payables`);
    if (!response.ok) throw new Error('Failed to fetch payables');
    const data = await response.json();
    return data.payables || [];
  },

  // Audit
  async getAuditLogs(invoiceId: string) {
    const response = await fetch(`${API_BASE_URL}/audit/${invoiceId}`);
    if (!response.ok) throw new Error('Failed to fetch audit logs');
    const data = await response.json();
    return data.audit_logs || [];
  },
};
