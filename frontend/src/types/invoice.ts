export type Status='Uploaded'|'Pending'|'Review Required'|'Blocked'|'Approved'|'Rejected'
export type Risk='Low'|'Medium'|'High'
export interface Invoice{id:string;vendorId:string;vendor:string;poId:string;qty:{po:number;received:number;invoiced:number};poPrice:number;invPrice:number;similarity:number;dupOf?:string;status:Status;date:string;hidden?:boolean}
export interface Exc{severity:Risk;title:string;detail:string}
