import {Invoice} from '../../types/invoice'
import {subtotal,tax,total} from '../../services/verificationService'
import {inr} from '../../utils'
import StatusBadge from '../ui/StatusBadge'
export default function FinancialValidation({inv}:{inv:Invoice}){const e=inv.qty.po*inv.poPrice
const rows:[string,number,number][]=[['Subtotal',e,subtotal(inv)],['Tax (GST 18%)',e*.18,tax(inv)],['Discount',0,0],['Shipping',0,0],['Total',e*1.18,total(inv)]]
return(<div className="card overflow-x-auto"><b>Financial Validation</b><table className="w-full mt-2 min-w-[480px]"><thead><tr>{['Item','Expected','Invoice','Difference','Status'].map(h=><th key={h} className="th">{h}</th>)}</tr></thead><tbody>{rows.map(([n,x,y])=><tr key={n}><td className="td">{n}</td><td className="td">{inr(x)}</td><td className="td">{inr(y)}</td><td className="td">{inr(y-x)}</td><td className="td"><StatusBadge label={x===y?'Passed':'Failed'}/></td></tr>)}</tbody></table></div>)}
