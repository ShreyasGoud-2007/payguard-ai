import {Bell,Search} from 'lucide-react'
import {useLocation} from 'react-router-dom'
export default function Header(){const p=useLocation().pathname.split('/').filter(Boolean).join(' / ')||'dashboard'
return(<header className="flex items-center justify-between gap-3 px-6 py-3 bg-white border-b"><span className="capitalize text-slate-500">{p}</span>
<div className="flex items-center gap-3"><div className="relative hidden sm:block"><Search size={14} className="absolute left-2 top-2.5 text-slate-400"/><input placeholder="Search" className="border rounded-lg pl-7 py-1.5"/></div><Bell size={18} className="text-slate-500"/><span className="w-7 h-7 rounded-full bg-indigo-600 text-white grid place-items-center text-xs">FM</span></div></header>)}
