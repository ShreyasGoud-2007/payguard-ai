import {useNavigate} from 'react-router-dom'
import {Invoice} from '../../types/invoice'
import {riskLevel,total,verification} from '../../services/verificationService'
import {inr} from '../../utils'
import RiskBadge from '../ui/RiskBadge'
import StatusBadge from '../ui/StatusBadge'
export default function InvoiceTable({rows}:{rows:Invoice[]}){const nav=useNavigate()
if(!rows.length)return <p className="text-center text-slate-500 py-8">No invoices match.</p>
return(<div className="overflow-x-auto"><table className="w-full min-w-[720px]"><thead><tr>{['Invoice','Vendor','PO','Amount','Risk','Verification','Status','Date'].map(h=><th key={h} className="th">{h}</th>)}</tr></thead>
<tbody>{rows.map(i=><tr key={i.id} onClick={()=>nav('/invoices/'+i.id)} className="cursor-pointer hover:bg-slate-50"><td className="td font-semibold">{i.id}</td><td className="td">{i.vendor}</td><td className="td">{i.poId}</td><td className="td">{inr(total(i))}</td><td className="td"><RiskBadge risk={riskLevel(i)}/></td><td className="td">{verification(i)}</td><td className="td"><StatusBadge label={i.status}/></td><td className="td">{i.date}</td></tr>)}</tbody></table></div>)}
