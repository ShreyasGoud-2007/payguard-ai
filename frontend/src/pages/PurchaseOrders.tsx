import {useState} from 'react'
import {mockPurchaseOrders} from '../data/mockPurchaseOrders'
import {mockGoodsReceipts} from '../data/mockGoodsReceipts'
import {useStore} from '../services/invoiceService'
import {inr} from '../utils'
export default function PurchaseOrders(){const s=useStore();const [sel,setSel]=useState('PO-1025')
const po=mockPurchaseOrders.find(p=>p.id===sel)!;const g=mockGoodsReceipts.find(x=>x.poId===sel);const inv=s.invoices.find(i=>i.poId===sel)
return <><h1 className="h1">Purchase Orders</h1><p className="sub">PO → Goods Receipt → Invoice (3-way match).</p>
<div className="card overflow-x-auto"><table className="w-full min-w-[640px]"><thead><tr>{['PO','Vendor','Item','Qty','Amount','Date'].map(h=><th key={h} className="th">{h}</th>)}</tr></thead><tbody>{mockPurchaseOrders.map(p=><tr key={p.id} onClick={()=>setSel(p.id)} className={`cursor-pointer hover:bg-slate-50 ${p.id===sel?'bg-indigo-50':''}`}><td className="td font-semibold">{p.id}</td><td className="td">{p.vendor}</td><td className="td">{p.item}</td><td className="td">{p.qty}</td><td className="td">{inr(p.qty*p.price)}</td><td className="td">{p.date}</td></tr>)}</tbody></table></div>
<div className="card"><b>{po.id} flow</b><div className="mt-2">PO: {po.qty} units<br/>↓<br/>Goods Receipt {g?.id}: {g?.received} units<br/>↓<br/>Invoice {inv?.id}: {inv?.qty.invoiced} units {inv?.hidden&&'(not yet uploaded)'}</div></div></>}
