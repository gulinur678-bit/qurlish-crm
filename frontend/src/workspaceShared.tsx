import {useEffect,useRef,useState,type ReactNode} from 'react';
import {api} from './api';
export function useRemote<T>(url:string,version=0){
 const [data,setData]=useState<T|null>(null),[error,setError]=useState(''),[loading,setLoading]=useState(true),[tick,setTick]=useState(0);
 useEffect(()=>{const controller=new AbortController();setLoading(true);setError('');api<T>(url,{signal:controller.signal}).then(d=>{if(!controller.signal.aborted)setData(d)}).catch(e=>{if(!controller.signal.aborted)setError(e.message)}).finally(()=>{if(!controller.signal.aborted)setLoading(false)});return()=>controller.abort()},[url,version,tick]);
 return {data,error,loading,reload:()=>setTick(t=>t+1)};
}
export function useDebounce(value:string){const [v,setV]=useState(value);useEffect(()=>{const id=setTimeout(()=>setV(value),250);return()=>clearTimeout(id)},[value]);return v}
export function State({loading,error,retry,empty=false}:{loading?:boolean;error?:string;retry?:()=>void;empty?:boolean}){return <div className="ws-state" role={error?'alert':'status'}>{loading?'Ma’lumotlar yuklanmoqda…':error|| (empty?'Bu filtr bo‘yicha ma’lumot topilmadi.':'')}{error&&retry&&<button onClick={retry}>Qayta urinish</button>}</div>}
export function Pager({page,total,size=25,setPage}:{page:number;total:number;size?:number;setPage:(p:number)=>void}){const pages=Math.max(1,Math.ceil(total/size));return <div className="ws-pager"><span>Jami {total} ta · {page} / {pages} sahifa</span><div><button disabled={page<=1} onClick={()=>setPage(page-1)}>← Oldingi</button><button disabled={page>=pages} onClick={()=>setPage(page+1)}>Keyingi →</button></div></div>}
export function Dialog({title,close,children}:{title:string;close:()=>void;children:ReactNode}){
 const box=useRef<HTMLElement>(null),closeRef=useRef(close);closeRef.current=close;
 useEffect(()=>{const previous=document.activeElement as HTMLElement;const node=box.current;node?.querySelector<HTMLElement>('button')?.focus();const overflow=document.body.style.overflow;document.body.style.overflow='hidden';const key=(e:KeyboardEvent)=>{if(e.key==='Escape')closeRef.current();if(e.key==='Tab'){const els=Array.from(node?.querySelectorAll<HTMLElement>('button:not([disabled]),a[href],input,select,textarea,[tabindex="0"]')||[]);const first=els[0],last=els.at(-1);if(e.shiftKey&&document.activeElement===first){e.preventDefault();last?.focus()}else if(!e.shiftKey&&document.activeElement===last){e.preventDefault();first?.focus()}}};document.addEventListener('keydown',key);return()=>{document.body.style.overflow=overflow;document.removeEventListener('keydown',key);previous?.focus()}},[]);
 return <div className="ws-overlay" onMouseDown={e=>{if(e.target===e.currentTarget)close()}}><section ref={box} className="ws-dialog" role="dialog" aria-modal="true" aria-label={title}><header><h2>{title}</h2><button aria-label="Oynani yopish" onClick={close}>×</button></header>{children}</section></div>
}
