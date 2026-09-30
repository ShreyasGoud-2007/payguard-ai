import {Invoice} from '../../types/invoice'
import StatusBadge from '../ui/StatusBadge'
export default function DuplicateCheck({inv}:{inv:Invoice}){const d=inv.similarity>=90
return(<div className="card"><b>Duplicate Detection</b><p className="mt-1">{d?`Potential match: ${inv.dupOf}`:'No exact duplicate'}<br/>Similarity: <b>{inv.similarity}%</b> <StatusBadge label={d?'Failed':'Passed'}/></p></div>)}
