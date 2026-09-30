import {Outlet} from 'react-router-dom'
import Sidebar from './Sidebar'
import Header from './Header'
import {useStore} from '../../services/invoiceService'
export default function Layout(){const {toast}=useStore()
return(<div className="flex flex-col md:flex-row min-h-screen"><Sidebar/><div className="flex-1 min-w-0"><Header/><main className="p-4 md:p-6 max-w-6xl"><Outlet/></main></div>
{toast&&<div className="fixed bottom-4 right-4 bg-slate-900 text-white px-4 py-2 rounded-lg">{toast}</div>}</div>)}
