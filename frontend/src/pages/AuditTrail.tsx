import {useState} from 'react'
import {useStore} from '../services/invoiceService'
export default function AuditTrail(){const s=useStore();const [f,setF]=useState('All')
const rows=s.audit.filter(e=>f==='All'||(f==='System'?e.user==='System'||e.user==='Verification Engine':e.user!=='System'&&e.user!=='Verification Engine'))
return <><h1 className="h1">Audit Trail</h1><p className="sub">Complete history of invoice verification and approval actions.</p><div className="flex gap-2 mb-3">{['All','System','User'].map(x=><button key={x} className={`btn ${f===x?'btn-p':''}`} onClick={()=>setF(x)}>{x}</button>)}</div>
<div className="card border-l-2 ml-2">{rows.map((e,i)=><div key={i} className="pb-3 pl-3"><b>{e.time}</b> · {e.action}<br/><span className="text-slate-500">by {e.user}{e.invoiceId&&' · '+e.invoiceId}</span></div>)}</div></>}
