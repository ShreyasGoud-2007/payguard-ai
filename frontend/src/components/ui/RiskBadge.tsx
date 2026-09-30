import {Risk} from '../../types/invoice'
const C={Low:'bg-green-100 text-green-700',Medium:'bg-amber-100 text-amber-700',High:'bg-red-100 text-red-700'}
export default function RiskBadge({risk}:{risk:Risk}){return <span className={`px-2 py-0.5 rounded-full text-xs font-semibold ${C[risk]}`}>{risk}</span>}
