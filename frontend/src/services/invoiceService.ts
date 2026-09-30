// In-memory store. Replace internals with FastAPI/Supabase calls later; keep the exported function signatures.
import {useSyncExternalStore} from 'react'
import {Invoice} from '../types/invoice'
import {AuditEvent} from '../types/audit'
import {mockInvoices} from '../data/mockInvoices'
import {mockAuditLogs} from '../data/mockAuditLogs'
interface State{invoices:Invoice[];audit:AuditEvent[];ledger:string[];toast:string}
let state:State={invoices:mockInvoices.map(i=>({...i})),audit:[...mockAuditLogs],ledger:['INV-1034'],toast:''}
const subs=new Set<()=>void>()
export const setState=(p:Partial<State>)=>{state={...state,...p};subs.forEach(f=>f())}
export const useStore=()=>useSyncExternalStore(f=>{subs.add(f);return()=>subs.delete(f)},()=>state)
export const getState=()=>state
export const visibleInvoices=(s:State)=>s.invoices.filter(i=>!i.hidden)
export const updateInvoice=(id:string,p:Partial<Invoice>)=>setState({invoices:state.invoices.map(i=>i.id===id?{...i,...p}:i)})
export const logEvent=(action:string,user:string,invoiceId?:string)=>setState({audit:[{time:new Date().toLocaleTimeString('en-IN',{hour:'2-digit',minute:'2-digit'}),action,user,invoiceId},...state.audit]})
export const notify=(t:string)=>{setState({toast:t});setTimeout(()=>setState({toast:''}),2500)}
