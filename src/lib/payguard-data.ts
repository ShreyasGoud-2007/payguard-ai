export type InvoiceStatus = "Flagged" | "Cleared" | "Dup check" | "Review" | "Approved" | "On hold";

export type Invoice = {
  id: string;
  vendor: string;
  initials: string;
  amount: number;
  status: InvoiceStatus;
  risk: "Critical" | "Watch" | "Clear";
  po: string;
  due: string;
  submitted: string;
  reason: string;
  category: string;
  riskScore?: number;
};

export const invoices: Invoice[] = [
  { id: "INV-1001", vendor: "Northwind Supply", initials: "NS", amount: 14250, status: "Approved", risk: "Clear", po: "PO-1001", due: "Sep 18", submitted: "Sep 10", reason: "Approved payable with clean three-way match", category: "Facilities", riskScore: 12 },
  { id: "INV-1002", vendor: "Aster Data Systems", initials: "AD", amount: 21640, status: "Review", risk: "Watch", po: "PO-1002", due: "Sep 21", submitted: "Sep 12", reason: "Quantity mismatch detected on line 3; approval pending", category: "Technology", riskScore: 75 },
  { id: "INV-1003", vendor: "Solstice Catering", initials: "SC", amount: 7830, status: "Flagged", risk: "Critical", po: "PO-1003", due: "Sep 20", submitted: "Sep 10", reason: "Price mismatch against approved purchase order", category: "Facilities", riskScore: 89 },
  { id: "INV-1004", vendor: "Delta Cloud", initials: "DC", amount: 9340, status: "Dup check", risk: "Watch", po: "PO-1004", due: "Sep 22", submitted: "Sep 11", reason: "Duplicate invoice detected against recent cloud billing", category: "Technology", riskScore: 68 },
  { id: "INV-8841", vendor: "Meridian Freight", initials: "MF", amount: 24900, status: "Flagged", risk: "Critical", po: "PO-2211", due: "Feb 28", submitted: "Feb 18", reason: "Vendor banking mismatch against PO-2211", category: "Operations" },
  { id: "INV-8840", vendor: "Northwind Supply", initials: "NS", amount: 6210, status: "Cleared", risk: "Clear", po: "PO-2209", due: "Mar 02", submitted: "Feb 18", reason: "Three-way match complete", category: "Facilities" },
  { id: "INV-8839", vendor: "Delta Cloud", initials: "DC", amount: 11480, status: "Dup check", risk: "Watch", po: "PO-2208", due: "Mar 04", submitted: "Feb 17", reason: "Potential duplicate with INV-8820", category: "Technology" },
  { id: "INV-8838", vendor: "Hartwell Legal", initials: "HL", amount: 8000, status: "Review", risk: "Watch", po: "PO-2207", due: "Mar 07", submitted: "Feb 17", reason: "PO variance is within tolerance", category: "Professional services" },
  { id: "INV-8837", vendor: "Cobalt Materials", initials: "CM", amount: 3340, status: "Cleared", risk: "Clear", po: "PO-2204", due: "Mar 08", submitted: "Feb 16", reason: "Three-way match complete", category: "Operations" },
  { id: "INV-8836", vendor: "Solstice Catering", initials: "SC", amount: 3940.5, status: "Flagged", risk: "Critical", po: "PO-2201", due: "Feb 26", submitted: "Feb 16", reason: "Tax ID does not match vendor master", category: "Facilities" },
  { id: "INV-8835", vendor: "Harborline Vending", initials: "HV", amount: 7115, status: "Approved", risk: "Clear", po: "PO-2198", due: "Feb 25", submitted: "Feb 15", reason: "Approved by finance operations", category: "Facilities" },
  { id: "INV-8834", vendor: "Aster Data Systems", initials: "AD", amount: 18900, status: "Review", risk: "Watch", po: "PO-2194", due: "Mar 12", submitted: "Feb 14", reason: "Line-item quantity variance", category: "Technology" },
];

export const vendors = [
  { name: "Meridian Freight", initials: "MF", category: "Logistics", spend: 184200, invoices: 24, health: "Watch", owner: "Mia Chen" },
  { name: "Northwind Supply", initials: "NS", category: "Facilities", spend: 94200, invoices: 18, health: "Healthy", owner: "Jon Bell" },
  { name: "Delta Cloud", initials: "DC", category: "Technology", spend: 286400, invoices: 12, health: "Watch", owner: "Mia Chen" },
  { name: "Hartwell Legal", initials: "HL", category: "Professional services", spend: 128000, invoices: 8, health: "Healthy", owner: "Ari Patel" },
  { name: "Solstice Catering", initials: "SC", category: "Facilities", spend: 38400, invoices: 16, health: "Blocked", owner: "Jon Bell" },
  { name: "Cobalt Materials", initials: "CM", category: "Operations", spend: 76200, invoices: 21, health: "Healthy", owner: "Ari Patel" },
];

export const purchaseOrders = [
  { id: "PO-1001", vendor: "Northwind Supply", owner: "Jon Bell", value: 15000, invoiced: 14250, status: "On track", created: "Sep 01" },
  { id: "PO-1002", vendor: "Aster Data Systems", owner: "Mia Chen", value: 22000, invoiced: 21640, status: "Variance", created: "Sep 02" },
  { id: "PO-1003", vendor: "Solstice Catering", owner: "Jon Bell", value: 7200, invoiced: 7830, status: "Over budget", created: "Sep 03" },
  { id: "PO-1004", vendor: "Delta Cloud", owner: "Mia Chen", value: 9000, invoiced: 9340, status: "Duplicate", created: "Sep 04" },
  { id: "PO-2211", vendor: "Meridian Freight", owner: "Mia Chen", value: 42000, invoiced: 24900, status: "Variance", created: "Feb 02" },
  { id: "PO-2209", vendor: "Northwind Supply", owner: "Jon Bell", value: 12000, invoiced: 6210, status: "On track", created: "Feb 04" },
  { id: "PO-2208", vendor: "Delta Cloud", owner: "Mia Chen", value: 24000, invoiced: 11480, status: "On track", created: "Feb 05" },
  { id: "PO-2207", vendor: "Hartwell Legal", owner: "Ari Patel", value: 8500, invoiced: 8000, status: "On track", created: "Feb 06" },
  { id: "PO-2201", vendor: "Solstice Catering", owner: "Jon Bell", value: 3000, invoiced: 3940.5, status: "Over budget", created: "Jan 28" },
];

export const auditEvents = [
  { time: "12:04:18", actor: "PayGuard AI", action: "Flagged vendor banking mismatch", target: "INV-8841", tone: "rose" },
  { time: "11:58:02", actor: "Mia Chen", action: "Approved payment", target: "INV-8835", tone: "lime" },
  { time: "11:43:27", actor: "PayGuard AI", action: "Matched invoice to purchase order", target: "INV-8840", tone: "cyan" },
  { time: "11:35:09", actor: "Jon Bell", action: "Added comment to exception", target: "INV-8836", tone: "amber" },
  { time: "11:22:41", actor: "PayGuard AI", action: "Detected likely duplicate", target: "INV-8839", tone: "amber" },
  { time: "10:48:53", actor: "Ari Patel", action: "Updated approval threshold", target: "Policy / AP-2048", tone: "mist" },
];

export const spendBars = [46, 62, 38, 70, 54, 80, 44];

export function formatCurrency(value: number) {
  return new Intl.NumberFormat("en-US", { style: "currency", currency: "USD", maximumFractionDigits: value % 1 ? 2 : 0 }).format(value);
}