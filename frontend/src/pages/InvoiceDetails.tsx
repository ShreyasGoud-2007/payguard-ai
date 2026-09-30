import {useState} from 'react'
import {Link,useParams} from 'react-router-dom'
import {useStore} from '../services/invoiceService'
import {exceptions} from '../services/verificationService'
import {ApprovalAction} from '../types/approval'
import InvoiceCard from '../components/invoices/InvoiceCard'
import VerificationSummary from '../components/verification/VerificationSummary'
import ThreeWayMatch from '../components/verification/ThreeWayMatch'
import FinancialValidation from '../components/verification/FinancialValidation'
import DuplicateCheck from '../components/verification/DuplicateCheck'
import VendorVerification from '../components/verification/VendorVerification'
import ApprovalModal from '../components/approvals/ApprovalModal'
import StatusBadge from '../components/ui/StatusBadge'
export default function InvoiceDetails(){const {id}=useParams();const s=useStore();const [a,setA]=useState<ApprovalAction|null>(null)
const inv=s.invoices.find(i=>i.id===id&&!i.hidden);if(!inv)return <div className="card">Invoice not found. <Link to="/invoices" className="text-indigo-600">Back</Link></div>
const ex=exceptions(inv);const done=inv.status==='Approved'||inv.status==='Rejected'
return(<><Link to="/invoices" className="text-slate-500">← Invoices</Link><div className="mt-2"><InvoiceCard inv={inv}/></div>
<VerificationSummary inv={inv}/><ThreeWayMatch inv={inv}/><FinancialValidation inv={inv}/><DuplicateCheck inv={inv}/><VendorVerification inv={inv}/>
<div className="card"><b>Approval Recommendation</b><p className="my-2">{ex.length?<><StatusBadge label="Review Required"/> {ex.map(e=>e.title+': '+e.detail).join('; ')}<br/>Recommended action: <b>Route to Finance Manager</b>. Critical exceptions are never auto-approved.</>:<><StatusBadge label="Passed"/> All checks passed. Eligible for approval.</>}</p>
{done?<StatusBadge label={inv.status}/>:<div className="flex flex-wrap gap-2"><button className="btn btn-g" onClick={()=>setA('approve')}>{ex.length?'Approve (override)':'Approve'}</button><button className="btn btn-r" onClick={()=>setA('reject')}>Reject</button><button className="btn" onClick={()=>setA('review')}>Send for Review</button><button className="btn" onClick={()=>setA('clarify')}>Request Clarification</button></div>}</div>
{a&&<ApprovalModal inv={inv} action={a} onClose={()=>setA(null)}/>}</>)}
