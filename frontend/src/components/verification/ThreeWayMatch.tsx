import {Invoice} from '../../types/invoice'
import {mockGoodsReceipts} from '../../data/mockGoodsReceipts'
import {excess} from '../../services/verificationService'
import {inr} from '../../utils'
export default function ThreeWayMatch({inv}:{inv:Invoice}){const grn=mockGoodsReceipts.find(g=>g.poId===inv.poId);const bad=inv.qty.received<inv.qty.invoiced
const Box=({t,id,n,s,red}:{t:string;id?:string;n:number;s:string;red?:boolean})=><div className="card !mb-0 text-center"><div className="text-xs text-slate-500" title={t==='GOODS RECEIPT'?'Goods Receipt Note':t==='PURCHASE ORDER'?'Purchase Order':''}>{t}</div><b>{id}</b><div className={`text-3xl font-bold ${red?'text-red-600':''}`}>{n}</div>{s}</div>
return(<div className="card"><b title="PO + Goods Receipt + Invoice">3-Way Match</b><div className="grid md:grid-cols-3 gap-3 mt-3"><Box t="PURCHASE ORDER" id={inv.poId} n={inv.qty.po} s={`units @ ${inr(inv.poPrice)}`}/><Box t="GOODS RECEIPT" id={grn?.id} n={inv.qty.received} s="units received" red={bad}/><Box t="INVOICE" id={inv.id} n={inv.qty.invoiced} s={`units billed @ ${inr(inv.invPrice)}`}/></div>
{bad&&<div className="mt-3 p-3 rounded-lg bg-red-50 border-l-4 border-red-600"><b>Quantity mismatch detected</b><br/>{inv.qty.invoiced-inv.qty.received} units were invoiced but not recorded as received.<br/>Potential excess billing: {inv.qty.invoiced-inv.qty.received} × {inr(inv.poPrice)} = <b>{inr(excess(inv))}</b></div>}</div>)}
