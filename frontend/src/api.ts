export type Status='available'|'reserved'|'sold';
export type Stage='new'|'contacted'|'qualified'|'closed_lost';
export type Unit={id:string;building:string;floor:number;unit:number;rooms:number;area:number;price:number|null;status:Status};
export type Lead={id:number;unit_id:string;name:string;phone:string;stage:Stage;created_at:string};
export type Metrics={days:number;count:number;stages:Record<Stage,number>;bins:number[];unit_statuses:Record<Status,number>;as_of:string};
export type User={email:string;role:'admin'|'manager'};
export type Event={kind:string;actor:string;value:string;created_at:string};
export const stages:Record<Stage,string>={new:'Yangi murojaat',contacted:'Bog‘lanilgan',qualified:'Qiziqish bildirgan',closed_lost:'Yopilgan'};
export const statuses:Record<Status,string>={available:'Bo‘sh',reserved:'Bron qilingan',sold:'Sotilgan'};
export async function api<T>(url:string,init:RequestInit={}):Promise<T>{
  const res=await fetch(url,{credentials:'same-origin',...init,headers:{'Content-Type':'application/json',...(init.headers||{})}});
  const data=await res.json().catch(()=>({}));
  if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:`Server xatosi (${res.status})`);
  return data as T;
}
export const money=(amount:number|null)=>amount===null?'Narx so‘rov asosida':new Intl.NumberFormat('uz-UZ').format(amount)+' so‘m';
export const dateTime=(d:string)=>new Date(d).toLocaleString('uz-UZ',{dateStyle:'medium',timeStyle:'short'});
export const unitName=(u:Unit)=>`${u.building}-bino · ${u.floor}-qavat · №${u.unit}`;
