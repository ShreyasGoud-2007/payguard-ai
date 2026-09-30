import {NavLink} from 'react-router-dom'
import {AlertTriangle,BookOpen,Building2,CheckSquare,Copy,FileText,History,LayoutDashboard,Settings,ShieldCheck,ShoppingCart} from 'lucide-react'
const G=[['MAIN',[['/','Dashboard',LayoutDashboard],['/invoices','Invoices',FileText],['/purchase-orders','Purchase Orders',ShoppingCart],['/vendors','Vendors',Building2],['/approvals','Approvals',CheckSquare],['/ledger','Payable Ledger',BookOpen]]],['CONTROL',[['/exceptions','Exceptions',AlertTriangle],['/duplicates','Duplicate Detection',Copy],['/audit','Audit Trail',History]]],['SYSTEM',[['/settings','Settings',Settings]]]] as const
export default function Sidebar(){return(<nav className="md:w-56 md:h-screen md:sticky top-0 bg-white border-r p-3 flex md:flex-col flex-wrap gap-1 shrink-0">
<div className="font-bold text-base flex items-center gap-2 p-2 w-full"><ShieldCheck className="text-indigo-600" size={20}/>PayGuard <span className="text-indigo-600">AI</span></div>
{G.map(([t,items])=><div key={t} className="contents md:block w-full"><div className="hidden md:block text-[11px] text-slate-400 font-semibold px-2 mt-3">{t}</div>
{items.map(([to,l,Icon])=><NavLink key={to} to={to} end={to==='/'} className={({isActive})=>`flex items-center gap-2 px-2 py-1.5 rounded-lg ${isActive?'bg-indigo-50 text-indigo-700 font-semibold':'hover:bg-slate-50'}`}><Icon size={16}/>{l}</NavLink>)}</div>)}
<div className="hidden md:block mt-auto p-2 text-xs text-slate-500"><b className="block text-slate-900">Finance Manager</b>Acme India Pvt Ltd</div></nav>)}
