import {Link} from 'react-router-dom'
import {useStore,visibleInvoices} from '../services/invoiceService'
import {exceptions} from '../services/verificationService'
import RiskBadge from '../components/ui/RiskBadge'
import StatusBadge from '../components/ui/StatusBadge'
export default function Exceptions(){const s=useStore();const rows=visibleInvoices(s).filter(i=>exceptions(i).length)
return <><h1 className="h1">Exception Center</h1><p className="sub">Every problem found before payment.</p>{rows.flatMap(i=>exceptions(i).map(e=><div key={i.id+e.title} className="card flex justify-between gap-2"><div><RiskBadge risk={e.severity}/> <b>{e.title}</b> · {i.id}<br/><span className="text-slate-500">{e.detail} · Assigned: Finance Manager</span> <StatusBadge label={i.status}/></div><Link to={'/invoices/'+i.id} className="btn h-fit">Review</Link></div>))}{!rows.length&&<div className="card">No exceptions.</div>}</>}
