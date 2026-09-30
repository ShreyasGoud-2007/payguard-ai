import {AuditEvent} from '../types/audit'
export const mockAuditLogs:AuditEvent[]=[
{time:'09:40 AM',action:'Invoice approved',user:'Finance Manager',invoiceId:'INV-1034'},
{time:'09:12 AM',action:'Duplicate suspected (98% vs INV-1018) - invoice blocked',user:'System',invoiceId:'INV-1036'},
{time:'09:05 AM',action:'Price mismatch: invoice Rs 55,000 vs PO Rs 50,000',user:'System',invoiceId:'INV-1037'}]
