import {AlertTriangle,CheckCircle2,Clock,FileText,ShieldAlert} from 'lucide-react'
import {useStore,visibleInvoices} from '../services/invoiceService'
import {exceptions,excess,riskLevel,total} from '../services/verificationService'
import {inr} from '../utils'
import KPICard from '../components/dashboard/KPICard'
import RiskOverview from '../components/dashboard/RiskOverview'
import RecentInvoices from '../components/dashboard/RecentInvoices'
import ExceptionPanel from '../components/dashboard/ExceptionPanel'
const H:[string,number][]=[['PO Match Rate',96],['3-Way Match Rate',88],['Duplicate Detection',100],['Approval Completion',74],['Exception Resolution',61]]
export default function Dashboard(){const s=useStore();const v=visibleInvoices(s);const open=v.filter(i=>exceptions(i).length&&!['Approved','Rejected'].includes(i.status));const ap=v.filter(i=>i.status==='Approved')
return(<><h1 className="h1">Accounts Payable Control Center</h1><p className="sub">Verify every invoice before it becomes a financial obligation.</p>
<div className="card !bg-indigo-50 !border-indigo-100 text-indigo-700 font-semibold">Invoice received ≠ payable. Nothing is paid until it is verified and approved.</div>
<div className="grid grid-cols-2 lg:grid-cols-5 gap-3 mb-3"><KPICard label="Invoices Received" value={v.length} note="+12% this week" icon={FileText}/><KPICard label="Pending Verification" value={v.filter(i=>i.status==='Pending').length} note="awaiting checks" icon={Clock}/><KPICard label="Exceptions" value={open.length} note="need attention" icon={AlertTriangle}/><KPICard label="Approved Payables" value={inr(ap.reduce((a,i)=>a+total(i),0))} note="verified & approved" icon={CheckCircle2}/><KPICard label="Potential Risk Detected" value={inr(open.reduce((a,i)=>a+(excess(i)||total(i)),0))} note="blocked from payment" icon={ShieldAlert}/></div>
<div className="grid md:grid-cols-2 gap-3 mb-3"><div className="card !mb-0"><b>Control Health</b>{H.map(([n,p])=><div key={n} className="mt-2"><div className="flex justify-between"><span>{n}</span><b>{p}%</b></div><div className="h-2 bg-slate-200 rounded"><div className="h-2 rounded bg-green-600" style={{width:p+'%'}}/></div></div>)}</div>
<RiskOverview data={(['Low','Medium','High'] as const).map(n=>({name:n,count:v.filter(i=>riskLevel(i)===n).length}))}/></div>
<ExceptionPanel rows={open}/><RecentInvoices rows={v}/></>)}
