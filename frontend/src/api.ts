export type Status='available'|'reserved'|'sold';
export type Stage='new'|'contacted'|'qualified'|'closed_lost';
export type Unit={id:string;building:string;floor:number;unit:number;rooms:number;area:number;price:number|null;status:Status};
export type Lead={id:number;unit_id:string;name:string;phone:string;stage:Stage;created_at:string};
export type Metrics={days:number;count:number;stages:Record<Stage,number>;bins:number[];unit_statuses:Record<Status,number>;as_of:string};
export type Role='admin'|'seller'|'viewer';
export type User={id:number;email:string;role:Role};
export type Event={kind:string;actor:string;value:string;created_at:string};
type TokenResponse={access_token:string;token_type:'bearer';expires_in:number;user:User};
export const stages:Record<Stage,string>={new:'Yangi murojaat',contacted:'Bog‘lanilgan',qualified:'Qiziqish bildirgan',closed_lost:'Yopilgan'};
export const statuses:Record<Status,string>={available:'Bo‘sh',reserved:'Bron qilingan',sold:'Sotilgan'};
let accessToken:string|null=null;
let refreshPromise:Promise<TokenResponse|null>|null=null;
let authGeneration=0;
const authChannel=typeof BroadcastChannel!=='undefined'?new BroadcastChannel('qurlish-auth'):null;
authChannel?.addEventListener('message',()=>authExpired());
function setAccessToken(token:string|null){accessToken=token}
function authExpired(){authGeneration++;setAccessToken(null);if(typeof window!=='undefined')window.dispatchEvent(new Event('crm:unauthorized'))}
async function withAuthLock<T>(work:()=>Promise<T>):Promise<T>{
  return navigator.locks?navigator.locks.request('qurlish-auth',work):work();
}
async function request(url:string,init:RequestInit,token:string|null){
  const headers=new Headers(init.headers);
  if(!headers.has('Content-Type'))headers.set('Content-Type','application/json');
  if(token)headers.set('Authorization',`Bearer ${token}`);else headers.delete('Authorization');
  return fetch(url,{credentials:'same-origin',...init,headers});
}
async function refreshAccess():Promise<TokenResponse|null>{
  // Without cross-tab locking, fail closed instead of replaying a shared cookie.
  if(!navigator.locks)return null;
  if(!refreshPromise){
    const generation=authGeneration;
    refreshPromise=withAuthLock(async()=>{
        if(generation!==authGeneration)return null;
        const res=await fetch('/api/auth/refresh',{method:'POST',credentials:'same-origin'});
        if(!res.ok)return null;
        const data=await res.json() as TokenResponse;
        if(generation!==authGeneration)return null;
        setAccessToken(data.access_token);
        return data;
    }).finally(()=>{refreshPromise=null});
  }
  return refreshPromise;
}
async function responseData<T>(res:Response):Promise<T>{
  const data=await res.json().catch(()=>({}));
  if(!res.ok)throw new Error(typeof data.detail==='string'?data.detail:`Server xatosi (${res.status})`);
  return data as T;
}
export async function api<T>(url:string,init:RequestInit={}):Promise<T>{
  const generation=authGeneration;
  let res=await request(url,init,accessToken);
  if(res.status===401&&accessToken&&!url.startsWith('/api/auth/')){
    try{
      const renewed=await refreshAccess();
      if(renewed){
        res=await request(url,init,accessToken);
        if(res.status===401)authExpired();
      }
      else authExpired();
    }catch{authExpired()}
  }
  const data=await responseData<T>(res);
  if(generation!==authGeneration&&!url.startsWith('/api/public/'))throw new Error('Sessiya o‘zgargan');
  return data;
}
export async function login(email:string,password:string):Promise<User>{
  const generation=++authGeneration;
  return withAuthLock(async()=>{
    if(generation!==authGeneration)throw new Error('Sessiya o‘zgargan');
    const data=await responseData<TokenResponse>(await request('/api/auth/login',{method:'POST',body:JSON.stringify({email,password})},null));
    if(generation!==authGeneration)throw new Error('Sessiya o‘zgargan');
    setAccessToken(data.access_token);
    authChannel?.postMessage('session-changed');
    return data.user;
  });
}
export async function restoreSession():Promise<User>{const data=await refreshAccess();if(!data){authExpired();throw new Error('Sessiya tugagan')}return data.user}
export async function logout():Promise<void>{
  const token=accessToken;
  authExpired();
  authChannel?.postMessage('logout');
  await withAuthLock(async()=>{
    await responseData(await request('/api/auth/logout',{method:'POST'},token));
  });
}
export const money=(amount:number|null)=>amount===null?'Narx so‘rov asosida':new Intl.NumberFormat('uz-UZ').format(amount)+' so‘m';
export const dateTime=(d:string)=>new Date(d).toLocaleString('uz-UZ',{dateStyle:'medium',timeStyle:'short'});
export const unitName=(u:Unit)=>`${u.building}-bino · ${u.floor}-qavat · №${u.unit}`;
