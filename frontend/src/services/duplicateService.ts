import {logEvent,notify} from './invoiceService'
import {updateInvoice} from './invoiceService'
export const comparison=(id:string)=>({current:{id,vendor:'PQR Solutions',number:'1036',amount:'₹3,54,000',date:'28 Sep',lines:'10 × Software licences'},match:{id:'INV-1018',vendor:'PQR Solutions',number:'1036',amount:'₹3,54,000',date:'14 Sep',lines:'10 × Software licences'}})
export function resolveDuplicate(id:string,isDuplicate:boolean){
if(isDuplicate){updateInvoice(id,{status:'Rejected'});logEvent('Marked as duplicate - rejected','Finance Manager',id);notify(id+' rejected as duplicate')}
else{updateInvoice(id,{status:'Review Required',similarity:20});logEvent('Cleared as not a duplicate','Finance Manager',id);notify(id+' cleared')}}
