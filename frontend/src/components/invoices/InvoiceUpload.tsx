import {useState} from 'react'
import {useNavigate} from 'react-router-dom'
import {analyzeInvoice,STEPS} from '../../services/verificationService'
export default function InvoiceUpload(){const nav=useNavigate();const [file,setFile]=useState<File|null>(null);const [step,setStep]=useState(-1)
const run=async()=>{const id=await analyzeInvoice(setStep);nav('/invoices/'+id)}
return(<div className="card"><label className="block border-2 border-dashed rounded-xl p-10 text-center cursor-pointer hover:border-indigo-500"><b className="text-lg">Drop invoice PDF here</b><br/><span className="text-slate-500">or browse files · PDF, PNG, JPG</span><input type="file" hidden accept=".pdf,.png,.jpg,.jpeg" onChange={e=>setFile(e.target.files?.[0]??null)}/></label>
{file&&<div className="flex justify-between items-center mt-4"><span><b>{file.name}</b> · {(file.size/1024).toFixed(0)} KB</span><span className="flex gap-2"><button className="btn" onClick={()=>{setFile(null);setStep(-1)}}>Remove</button><button className="btn btn-p" disabled={step>=0} onClick={run}>Analyze Invoice</button></span></div>}
{step>=0&&<div className="mt-4 space-y-1">{STEPS.slice(0,step+1).map((s,i)=><div key={s}>{i<step?'✓':'⏳'} {s}</div>)}</div>}</div>)}
