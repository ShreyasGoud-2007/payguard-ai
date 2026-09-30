import {Invoice} from '../../types/invoice'
import {total} from '../../services/verificationService'
import {inr} from '../../utils'
import StatusBadge from '../ui/StatusBadge'
export default function InvoiceCard({inv}:{inv:Invoice}){return(<div className="card flex justify-between items-start flex-wrap gap-2"><div><h1 className="h1">Invoice #{inv.id}</h1><div className="text-slate-500">{inv.vendor} · <b className="text-slate-900 text-base">{inr(total(inv))}</b> · Received {inv.date}</div></div><StatusBadge label={inv.status}/></div>)}
