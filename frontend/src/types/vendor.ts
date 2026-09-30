import {Risk} from './invoice'
export interface Vendor{id:string;name:string;status:'Verified'|'Under Review';invoices:number;value:number;risk:Risk;lastInvoice:string}
