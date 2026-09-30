import {useStore,visibleInvoices} from '../services/invoiceService'
import ApprovalTable from '../components/approvals/ApprovalTable'
export default function Approvals(){const s=useStore();const rows=visibleInvoices(s).filter(i=>['Review Required','Blocked','Pending'].includes(i.status))
return <><h1 className="h1">Approval Queue</h1><p className="sub">Review invoices requiring human authorization.</p><div className="card"><ApprovalTable rows={rows}/></div></>}
