import { invoices } from "./payguard-data";

export const payguardService = {
  async listInvoices() {
    return Promise.resolve(invoices);
  },
  async getHealth() {
    return Promise.resolve({ status: "live", lastSync: "3 sec ago", source: "mock" as const });
  },
  async approveInvoice(id: string) {
    return Promise.resolve({ id, status: "Approved" as const });
  },
  async holdInvoice(id: string) {
    return Promise.resolve({ id, status: "On hold" as const });
  },
};