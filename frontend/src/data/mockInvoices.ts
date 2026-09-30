import {Invoice} from '../types/invoice'
const v=(n:number)=>`VND-00${n}`
export const mockInvoices:Invoice[]=[
{id:'INV-1034',vendorId:v(1),vendor:'ABC Technologies Pvt Ltd',poId:'PO-1024',qty:{po:100,received:100,invoiced:100},poPrice:5000,invPrice:5000,similarity:4,status:'Approved',date:'24 Sep'},
{id:'INV-1035',vendorId:v(2),vendor:'XYZ Industries Pvt Ltd',poId:'PO-1025',qty:{po:100,received:80,invoiced:100},poPrice:50000,invPrice:50000,similarity:12,status:'Uploaded',date:'30 Sep',hidden:true},
{id:'INV-1036',vendorId:v(3),vendor:'PQR Solutions',poId:'PO-1026',qty:{po:10,received:10,invoiced:10},poPrice:30000,invPrice:30000,similarity:98,dupOf:'INV-1018',status:'Blocked',date:'28 Sep'},
{id:'INV-1037',vendorId:v(4),vendor:'Global Office Supplies',poId:'PO-1027',qty:{po:20,received:20,invoiced:20},poPrice:50000,invPrice:55000,similarity:8,status:'Review Required',date:'27 Sep'},
{id:'INV-1038',vendorId:v(5),vendor:'TechNova Systems',poId:'PO-1028',qty:{po:40,received:40,invoiced:40},poPrice:12000,invPrice:12000,similarity:3,status:'Pending',date:'29 Sep'},
{id:'INV-1039',vendorId:v(1),vendor:'ABC Technologies Pvt Ltd',poId:'PO-1029',qty:{po:15,received:15,invoiced:15},poPrice:22000,invPrice:22000,similarity:6,status:'Pending',date:'29 Sep'}]
