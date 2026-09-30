import {Invoice} from '../../types/invoice'
import {mockVendors} from '../../data/mockVendors'
import StatusBadge from '../ui/StatusBadge'
export default function VendorVerification({inv}:{inv:Invoice}){const v=mockVendors.find(x=>x.id===inv.vendorId)
return(<div className="card"><b>Vendor Verification</b><p className="mt-1">{inv.vendor} <StatusBadge label={v?.status??'Pending'}/><br/>Vendor ID: {v?.id} · Registration: Active · Bank: Verified · Previous invoices: {v?.invoices}</p></div>)}
