import {Component,lazy,Suspense,useState,type ReactNode} from 'react';
import type {Unit} from './api';
const Scene=lazy(()=>import('./Scene'));
export type SceneProps={units:Unit[];building:string;floor:number;chosen:string|null;onBuilding:(b:string)=>void;onFloor:(f:number)=>void;onUnit:(id:string)=>void};
class Boundary extends Component<{children:ReactNode;fallback:ReactNode},{failed:boolean}>{
 state={failed:false}; static getDerivedStateFromError(){return {failed:true}} render(){return this.state.failed?this.props.fallback:this.props.children}
}
export default function Explorer(props:SceneProps){
 const [active,setActive]=useState(false),[failed,setFailed]=useState(false);
 const fallback=<p role="status">3D ko‘rinish mavjud emas. Quyidagi 2D katalogdan xonadon tanlang.</p>;
 function start(){const canvas=document.createElement('canvas');const gl=canvas.getContext('webgl2');if(!gl){setFailed(true);return}gl.getExtension('WEBGL_lose_context')?.loseContext();setActive(true)}
 return <section className="explorer" aria-label="Interaktiv majmua"><div className="explorer-heading"><div><p className="eyebrow">MAJMUA → BINO → QAVAT → XONADON</p><h2>Makoningizni kashf eting.</h2></div><button onClick={()=>setActive(false)} disabled={!active}>2D katalog</button></div>{failed?fallback:active?<Boundary fallback={fallback}><Suspense fallback={<p role="status">3D sahna yuklanmoqda…</p>}><Scene {...props}/></Suspense></Boundary>:<div className="scene-invite"><span aria-hidden="true">▥</span><div><h3>Majmuaga yangi nuqtadan qarang.</h3><p>Aylantiring, yaqinlashtiring va xonadoningizni toping.</p></div><button className="button-dark" onClick={start}>3D majmuani ochish</button></div>}<p className="scene-note">Konsept 3D · texnik chizma emas. Barcha tanlovlar quyidagi tugmalar orqali ham mavjud.</p></section>
}
