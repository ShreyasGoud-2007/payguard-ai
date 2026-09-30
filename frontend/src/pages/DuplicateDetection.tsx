import {Link} from 'react-router-dom'
import {comparison,resolveDuplicate} from '../services/duplicateService'
export default function DuplicateDetection(){const {current:c,match:m}=comparison('INV-1036');const F=[['Vendor','vendor'],['Invoice Number','number'],['Amount','amount'],['Invoice Date','date'],['Line Items','lines']] as const
return(<><h1 className="h1">Duplicate &amp; Similarity Detection</h1><p className="sub">Compare {c.id} against {m.id}. Similarity: <b>98%</b></p>
<div className="card overflow-x-auto"><table className="w-full"><thead><tr><th className="th">Field</th><th className="th">{c.id}</th><th className="th">{m.id}</th></tr></thead><tbody>{F.map(([l,k])=><tr key={k} className={c[k]===m[k]?'bg-red-50':''}><td className="td">{l}</td><td className="td">{c[k]}</td><td className="td">{m[k]}</td></tr>)}</tbody></table>
<p className="mt-3 text-slate-500">High similarity detected based on vendor, invoice amount, normalized invoice number and line-item similarity.</p>
<div className="flex gap-2 mt-3"><Link className="btn" to="/invoices/INV-1036">View Invoice</Link><button className="btn btn-r" onClick={()=>resolveDuplicate('INV-1036',true)}>Mark as Duplicate</button><button className="btn" onClick={()=>resolveDuplicate('INV-1036',false)}>Not a Duplicate</button></div></div></>)}
