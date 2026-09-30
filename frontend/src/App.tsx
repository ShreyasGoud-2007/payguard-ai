import {Route,Routes} from 'react-router-dom'
import Layout from './components/layout/Layout'
import Dashboard from './pages/Dashboard'
import Invoices from './pages/Invoices'
import InvoiceDetails from './pages/InvoiceDetails'
import UploadInvoice from './pages/UploadInvoice'
import Approvals from './pages/Approvals'
import Exceptions from './pages/Exceptions'
import DuplicateDetection from './pages/DuplicateDetection'
import PayableLedger from './pages/PayableLedger'
import AuditTrail from './pages/AuditTrail'
import Vendors from './pages/Vendors'
import PurchaseOrders from './pages/PurchaseOrders'
import Settings from './pages/Settings'
export default function App(){return(<Routes><Route element={<Layout/>}>
<Route path="/" element={<Dashboard/>}/><Route path="/invoices" element={<Invoices/>}/><Route path="/invoices/upload" element={<UploadInvoice/>}/><Route path="/invoices/:id" element={<InvoiceDetails/>}/>
<Route path="/purchase-orders" element={<PurchaseOrders/>}/><Route path="/vendors" element={<Vendors/>}/><Route path="/approvals" element={<Approvals/>}/><Route path="/ledger" element={<PayableLedger/>}/>
<Route path="/exceptions" element={<Exceptions/>}/><Route path="/duplicates" element={<DuplicateDetection/>}/><Route path="/audit" element={<AuditTrail/>}/><Route path="/settings" element={<Settings/>}/>
</Route></Routes>)}
