import {useState} from 'react'
import {Link} from 'react-router-dom'
import {useStore,visibleInvoices} from '../services/invoiceService'
import {exceptions,verification} from '../services/verificationService'
import InvoiceTable from '../components/invoices/InvoiceTable'
const F=['All','Pending','Verified','Exception','Approved','Rejected']
export default function Invoices(){const s=useStore();const [f,setF]=useState('All');const [q,setQ]=useState('')
const rows=visibleInvoices(s).filter(i=>(i.id+i.vendor+i.poId).toLowerCase().includes(q.toLowerCase())&&(f==='All'||i.status===f||(f==='Verified'&&verification(i)==='Verified')||(f==='Exception'&&exceptions(i).length>0)))
return(<><div className="flex justify-between flex-wrap gap-2"><div><h1 className="h1">Invoices</h1><p className="sub">Review, verify and control incoming invoices.</p></div><Link to="/invoices/upload" className="btn btn-p h-fit">Upload Invoice</Link></div>
<div className="flex flex-wrap gap-2 mb-3">{F.map(x=><button key={x} className={`btn ${f===x?'btn-p':''}`} onClick={()=>setF(x)}>{x}</button>)}<input className="border rounded-lg px-3" placeholder="Search invoice, vendor, PO" value={q} onChange={e=>setQ(e.target.value)}/></div><div className="card"><InvoiceTable rows={rows}/></div></>)}
