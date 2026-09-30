import {mockVendors} from '../data/mockVendors'
import {inr} from '../utils'
import RiskBadge from '../components/ui/RiskBadge'
import StatusBadge from '../components/ui/StatusBadge'
export default function Vendors(){return <><h1 className="h1">Vendors</h1><p className="sub">Vendor verification status and risk.</p><div className="card overflow-x-auto"><table className="w-full min-w-[640px]"><thead><tr>{['Vendor','ID','Status','Invoices','Total Value','Risk','Last Invoice'].map(h=><th key={h} className="th">{h}</th>)}</tr></thead><tbody>{mockVendors.map(v=><tr key={v.id}><td className="td font-semibold">{v.name}</td><td className="td">{v.id}</td><td className="td"><StatusBadge label={v.status}/></td><td className="td">{v.invoices}</td><td className="td">{inr(v.value)}</td><td className="td"><RiskBadge risk={v.risk}/></td><td className="td">{v.lastInvoice}</td></tr>)}</tbody></table></div></>}
