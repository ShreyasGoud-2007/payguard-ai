import { payguardApi } from "./payguard-api";

// Transform backend invoice format to match frontend expectations
function transformInvoice(backendInvoice: any) {
  return {
    id: backendInvoice.id,
    vendor: backendInvoice.vendor?.name || 'Unknown Vendor',
    initials: backendInvoice.vendor?.name?.substring(0, 2)?.toUpperCase() || 'UK',
    amount: backendInvoice.total_amount || 0,
    status: mapStatus(backendInvoice.status),
    risk: mapRiskLevel(backendInvoice.risk_level),
    po: backendInvoice.purchase_order?.po_number || backendInvoice.po_id || '',
    due: backendInvoice.due_date || '',
    submitted: backendInvoice.invoice_date || backendInvoice.created_at?.split('T')[0] || '',
    reason: getReasonFromStatus(backendInvoice),
    category: backendInvoice.vendor?.category || 'General',
    riskScore: backendInvoice.risk_score || 0,
  };
}

function mapStatus(backendStatus: string): "Flagged" | "Cleared" | "Dup check" | "Review" | "Approved" | "On hold" {
  const statusMap: Record<string, any> = {
    'APPROVED': 'Approved',
    'REJECTED': 'On hold',
    'UNDER_REVIEW': 'Review',
    'uploaded': 'Review',
    'pending_verification': 'Review',
    'verification_failed': 'Flagged',
    'pending_approval': 'Review',
  };
  return statusMap[backendStatus] || 'Review';
}

function mapRiskLevel(backendRisk: string): "Critical" | "Watch" | "Clear" {
  const riskMap: Record<string, any> = {
    'HIGH': 'Critical',
    'MEDIUM': 'Watch',
    'LOW': 'Clear',
  };
  return riskMap[backendRisk] || 'Clear';
}

function getReasonFromStatus(invoice: any): string {
  if (invoice.status === 'APPROVED') return 'Approved and ready for payment';
  if (invoice.verification_status === 'FAILED') return 'Failed verification checks';
  if (invoice.audit_logs?.[0]?.details) {
    const details = invoice.audit_logs[0].details;
    if (typeof details === 'string') return details;
    if (details.exception) return details.exception;
  }
  return 'Under review';
}

export const payguardService = {
  async listInvoices() {
    try {
      const backendInvoices = await payguardApi.listInvoices();
      return backendInvoices.map(transformInvoice);
    } catch (error) {
      console.error('Failed to fetch invoices:', error);
      // Fallback to empty array or throw error
      throw error;
    }
  },

  async getHealth() {
    try {
      const health = await payguardApi.getHealth();
      const dbHealth = await payguardApi.getDbHealth();
      
      return { 
        status: health.status === 'healthy' ? 'live' : 'offline', 
        lastSync: '3 sec ago', 
        source: 'real' as const,
        database: dbHealth.status
      };
    } catch (error) {
      return { 
        status: 'offline' as const, 
        lastSync: 'connection failed', 
        source: 'real' as const,
        database: 'disconnected'
      };
    }
  },

  async approveInvoice(id: string) {
    try {
      await payguardApi.approveInvoice(id, 'Frontend User', 'Approved via PayGuard UI');
      return { id, status: "Approved" as const };
    } catch (error) {
      console.error('Approval failed:', error);
      throw error;
    }
  },

  async holdInvoice(id: string) {
    try {
      await payguardApi.holdInvoice(id, 'Frontend User', 'Put on hold via PayGuard UI');
      return { id, status: "On hold" as const };
    } catch (error) {
      console.error('Hold failed:', error);
      throw error;
    }
  },

  // New methods for PDF upload
  async uploadInvoicePdf(file: File, metadata: {
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
    try {
      const result = await payguardApi.uploadInvoice(file, metadata);
      return {
        success: true,
        invoice: transformInvoice(result.invoice),
        message: result.message
      };
    } catch (error) {
      console.error('Upload failed:', error);
      throw error;
    }
  },

  async getVendors() {
    return payguardApi.getVendors();
  },

  async getPurchaseOrders() {
    return payguardApi.getPurchaseOrders();
  },

  async getGoodsReceipts() {
    return payguardApi.getGoodsReceipts();
  },

  async getPayables() {
    return payguardApi.getPayables();
  },

  async getInvoiceDetails(id: string) {
    return payguardApi.getInvoice(id);
  },

  async getAuditLogs(invoiceId: string) {
    return payguardApi.getAuditLogs(invoiceId);
  }
};
