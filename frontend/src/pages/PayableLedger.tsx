import {useStore} from '../services/invoiceService'
import {total} from '../services/verificationService'
import {inr} from '../utils'
import StatusBadge from '../components/ui/StatusBadge'
export default function PayableLedger(){const s=useStore();const rows=s.invoices.filter(i=>s.ledger.includes(i.id))
return <><h1 className="h1">Payable Ledger</h1><p className="sub">Approved financial obligations.</p><div className="card !bg-indigo-50 text-indigo-700 font-semibold">Only invoices that have completed required verification and approval are included in the payable ledger.</div>
<div className="card overflow-x-auto"><table className="w-full min-w-[560px]"><thead><tr>{['Invoice','Vendor','Approved Amount','Due','Payment Status'].map(h=><th key={h} className="th">{h}</th>)}</tr></thead><tbody>{rows.map(i=><tr key={i.id}><td className="td font-semibold">{i.id}</td><td className="td">{i.vendor}</td><td className="td">{inr(total(i))}</td><td className="td">30 days</td><td className="td"><StatusBadge label="Scheduled"/></td></tr>)}</tbody></table>{!rows.length&&<p className="text-center text-slate-500 py-8">Nothing approved yet.</p>}</div></>}
