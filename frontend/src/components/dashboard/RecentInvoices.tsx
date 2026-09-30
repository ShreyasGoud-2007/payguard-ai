import {Invoice} from '../../types/invoice'
import InvoiceTable from '../invoices/InvoiceTable'
export default function RecentInvoices({rows}:{rows:Invoice[]}){return <div className="card"><b>Recent Invoices</b><InvoiceTable rows={rows}/></div>}
