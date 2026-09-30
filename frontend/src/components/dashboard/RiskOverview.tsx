import {Bar,BarChart,Cell,ResponsiveContainer,Tooltip,XAxis,YAxis} from 'recharts'
export default function RiskOverview({data}:{data:{name:string;count:number}[]}){const col:Record<string,string>={Low:'#16a34a',Medium:'#d97706',High:'#dc2626'}
return(<div className="card !mb-0"><b>Risk Overview</b><div className="h-40 mt-2"><ResponsiveContainer><BarChart data={data}><XAxis dataKey="name"/><YAxis allowDecimals={false}/><Tooltip/><Bar dataKey="count" radius={4}>{data.map(d=><Cell key={d.name} fill={col[d.name]}/>)}</Bar></BarChart></ResponsiveContainer></div></div>)}
