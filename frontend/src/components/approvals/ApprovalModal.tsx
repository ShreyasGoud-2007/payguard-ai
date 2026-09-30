import {useState} from 'react'
import {Invoice} from '../../types/invoice'
import {ApprovalAction} from '../../types/approval'
import {exceptions,total} from '../../services/verificationService'
import {submitAction} from '../../services/approvalService'
import {inr} from '../../utils'
const L:Record<ApprovalAction,[string,string]>={approve:['Approve','btn-g'],reject:['Reject','btn-r'],review:['Send for Review','btn-p'],clarify:['Request Clarification','btn-p']}
export default function ApprovalModal({inv,action,onClose}:{inv:Invoice;action:ApprovalAction;onClose:()=>void}){const [c,setC]=useState('');const [err,setErr]=useState(false)
const need=(action==='approve'&&exceptions(inv).length>0)||action==='clarify'
const ok=()=>{if(need&&!c.trim())return setErr(true);submitAction(inv.id,action,c);onClose()}
return(<div className="fixed inset-0 bg-black/40 grid place-items-center p-4 z-10"><div className="card max-w-md w-full !mb-0"><h3 className="font-bold text-base">{L[action][0]} {inv.id}?</h3>
<p className="text-slate-500 my-2">{inv.vendor} · {inr(total(inv))}{action==='approve'&&exceptions(inv).length>0&&<><br/>Unresolved exceptions exist. An override comment is required.</>}</p>
<textarea className={`w-full border rounded-lg p-2 ${err?'border-red-500':''}`} rows={3} placeholder={need?'Comment (required)':'Comment (optional)'} value={c} onChange={e=>setC(e.target.value)}/>
<div className="flex justify-end gap-2 mt-3"><button className="btn" onClick={onClose}>Cancel</button><button className={`btn ${L[action][1]}`} onClick={ok}>{L[action][0]}</button></div></div></div>)}
