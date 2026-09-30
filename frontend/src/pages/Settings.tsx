import {useState} from 'react'
import {notify} from '../services/invoiceService'
export default function Settings(){const [t,setT]=useState([{r:'Below ₹10,000',a:'Department Manager'},{r:'₹10,000–₹1,00,000',a:'Finance Manager'},{r:'₹1,00,000+',a:'Finance Head'}])
return <><h1 className="h1">Settings</h1><p className="sub">Approval thresholds (editable).</p><div className="card">{t.map((x,i)=><div key={i} className="flex flex-wrap gap-2 items-center mb-2"><span className="w-44">{x.r}</span>→<input className="border rounded-lg px-2 py-1" value={x.a} onChange={e=>setT(t.map((y,j)=>j===i?{...y,a:e.target.value}:y))}/></div>)}<button className="btn btn-p" onClick={()=>notify('Settings saved')}>Save</button></div></>}
