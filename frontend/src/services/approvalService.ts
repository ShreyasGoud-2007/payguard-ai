import {ApprovalAction} from '../types/approval'
import {getState,logEvent,notify,setState,updateInvoice} from './invoiceService'
export function submitAction(id:string,a:ApprovalAction,comment=''){const c=comment?` (${comment})`:''
if(a==='approve'){updateInvoice(id,{status:'Approved'});if(!getState().ledger.includes(id))setState({ledger:[...getState().ledger,id]});logEvent('Invoice approved'+c,'Finance Manager',id);notify(id+' approved - added to Payable Ledger')}
if(a==='reject'){updateInvoice(id,{status:'Rejected'});setState({ledger:getState().ledger.filter(x=>x!==id)});logEvent('Invoice rejected'+c,'Finance Manager',id);notify(id+' rejected')}
if(a==='review'){updateInvoice(id,{status:'Review Required'});logEvent('Sent for review - routed to Finance Manager','Finance Manager',id);notify('Sent to approval queue')}
if(a==='clarify'){logEvent('Clarification requested'+c,'Finance Manager',id);notify('Clarification requested')}}
