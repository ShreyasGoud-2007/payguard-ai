import {Exc,Invoice,Risk} from '../types/invoice'
import {logEvent,updateInvoice} from './invoiceService'
export const subtotal=(i:Invoice)=>i.qty.invoiced*i.invPrice
export const tax=(i:Invoice)=>subtotal(i)*0.18
export const total=(i:Invoice)=>subtotal(i)+tax(i)
export const excess=(i:Invoice)=>Math.max(0,i.qty.invoiced-i.qty.received)*i.poPrice
export const checks=(i:Invoice):[string,boolean][]=>[['Vendor Verification',true],['Purchase Order Match',true],['Goods Receipt',i.qty.received>=i.qty.invoiced],['Quantity Validation',i.qty.po===i.qty.invoiced&&i.qty.received>=i.qty.invoiced],['Price Validation',i.invPrice===i.poPrice],['Tax Validation',true],['Duplicate Detection',i.similarity<90]]
export const riskScore=(i:Invoice)=>Math.min(100,(i.qty.received<i.qty.invoiced?72:0)+(i.invPrice!==i.poPrice?30:0)+(i.similarity>=90?60:0))
export const riskLevel=(i:Invoice):Risk=>{const s=riskScore(i);return s>=60?'High':s>=20?'Medium':'Low'}
export const exceptions=(i:Invoice):Exc[]=>{const e:Exc[]=[]
if(i.qty.received<i.qty.invoiced)e.push({severity:'High',title:'Quantity mismatch',detail:`${i.qty.invoiced} invoiced / ${i.qty.received} received. Potential excess ${'₹'+excess(i).toLocaleString('en-IN')}`})
if(i.similarity>=90)e.push({severity:'High',title:'Duplicate invoice',detail:`${i.similarity}% similarity with ${i.dupOf}`})
if(i.invPrice!==i.poPrice)e.push({severity:'Medium',title:'Price mismatch',detail:`Invoice ₹${i.invPrice.toLocaleString('en-IN')} / PO ₹${i.poPrice.toLocaleString('en-IN')}`})
return e}
export const verification=(i:Invoice)=>i.status==='Uploaded'?'Not run':exceptions(i).length?(i.similarity>=90?'Duplicate Suspected':'Exception'):'Verified'
export const STEPS=['Extracting invoice data','Identifying vendor','Matching purchase order','Checking goods receipt','Detecting duplicates','Validating financials','Calculating risk']
export async function analyzeInvoice(onStep:(n:number)=>void){for(let n=0;n<STEPS.length;n++){onStep(n);await new Promise(r=>setTimeout(r,500))}
updateInvoice('INV-1035',{hidden:false,status:'Review Required'})
;[['Invoice uploaded','Accounts Executive'],['Invoice data extracted','Verification Engine'],['Vendor verified','System'],['PO-1025 matched','System'],['Goods receipt mismatch detected (80 of 100)','System'],['Risk score calculated: 72/100','System'],['Exception assigned to Finance Manager','System']].forEach(([a,u])=>logEvent(a,u,'INV-1035'))
return 'INV-1035'}
