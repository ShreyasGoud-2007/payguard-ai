import {Link} from 'react-router-dom'
import {Invoice} from '../../types/invoice'
import {exceptions} from '../../services/verificationService'
export default function ExceptionPanel({rows}:{rows:Invoice[]}){return(<div className="card"><b>Exceptions Requiring Attention</b>{rows.flatMap(i=>exceptions(i).map(e=><div key={i.id+e.title} className="mt-2 p-3 rounded-lg bg-red-50 border-l-4 border-red-600 flex justify-between gap-2"><div><b>{e.title}</b> · {i.id}<br/><span className="text-slate-500">{e.detail}</span></div><Link className="btn h-fit" to={'/invoices/'+i.id}>Review</Link></div>))}{!rows.length&&<p className="text-slate-500 mt-2">No open exceptions.</p>}</div>)}
