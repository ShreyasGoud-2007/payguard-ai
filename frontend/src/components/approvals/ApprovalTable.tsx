import {useState} from 'react'
import {Invoice} from '../../types/invoice'
import {ApprovalAction} from '../../types/approval'
import {exceptions,riskLevel,total} from '../../services/verificationService'
import {inr} from '../../utils'
import RiskBadge from '../ui/RiskBadge'
import ApprovalModal from './ApprovalModal'
export default function ApprovalTable({rows}:{rows:Invoice[]}){const [m,setM]=useState<{inv:Invoice;a:ApprovalAction}|null>(null)
return(<div className="overflow-x-auto"><table className="w-full min-w-[720px]"><thead><tr>{['Invoice','Vendor','Amount','Risk','Exception','Approver','Action'].map(h=><th key={h} className="th">{h}</th>)}</tr></thead>
<tbody>{rows.map(i=><tr key={i.id}><td className="td font-semibold">{i.id}</td><td className="td">{i.vendor}</td><td className="td">{inr(total(i))}</td><td className="td"><RiskBadge risk={riskLevel(i)}/></td><td className="td">{exceptions(i)[0]?.title??'None'}</td><td className="td">{total(i)>100000?'Finance Head':'Finance Manager'}</td>
<td className="td flex gap-1"><button className="btn btn-g" onClick={()=>setM({inv:i,a:'approve'})}>Approve</button><button className="btn btn-r" onClick={()=>setM({inv:i,a:'reject'})}>Reject</button><button className="btn" onClick={()=>setM({inv:i,a:'clarify'})}>Clarify</button></td></tr>)}</tbody></table>
{!rows.length&&<p className="text-center text-slate-500 py-8">Queue is empty.</p>}{m&&<ApprovalModal inv={m.inv} action={m.a} onClose={()=>setM(null)}/>}</div>)}
