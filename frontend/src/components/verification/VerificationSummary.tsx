import {Invoice} from '../../types/invoice'
import {checks,riskLevel,riskScore} from '../../services/verificationService'
import RiskBadge from '../ui/RiskBadge'
import StatusBadge from '../ui/StatusBadge'
export default function VerificationSummary({inv}:{inv:Invoice}){const s=riskScore(inv)
return(<div className="grid md:grid-cols-2 gap-3 mb-3"><div className="card !mb-0"><div className="text-slate-500">Risk Score</div><div className="text-4xl font-bold">{s}<span className="text-base text-slate-400">/100</span></div><RiskBadge risk={riskLevel(inv)}/><div className="h-2 bg-slate-200 rounded mt-3"><div className="h-2 rounded bg-indigo-600" style={{width:s+'%'}}/></div></div>
<div className="card !mb-0">{checks(inv).map(([n,ok])=><div key={n} className="flex justify-between py-0.5"><span>{n}</span><StatusBadge label={ok?'Passed':'Failed'}/></div>)}</div></div>)}
