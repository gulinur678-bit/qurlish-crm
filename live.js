'use strict';
// Live API integration: no synthetic inventory is submitted to the backend.
let liveUnits = new Map();
let liveMode = false;
let sending = false;
let requestKey = null;
const notice = document.createElement('p');
notice.id = 'inventory-notice'; notice.setAttribute('role','status'); notice.className='muted';
document.querySelector('#selection-summary').parentElement.appendChild(notice);
function setInventoryMessage(msg){notice.textContent=msg}
async function loadInventory(){
  try {
    let r=await fetch('/api/public/units',{headers:{Accept:'application/json'}});
    if(!r.ok) throw Error('API '+r.status);
    const data=await r.json(); liveUnits=new Map(data.units.map(x=>[x.id,x])); liveMode=true;
    unitOf=function(b,f,u){const id=`${buildingNames[b-1]}-${f}0${u}`;return liveUnits.get(id)||{id,building:buildingNames[b-1],floor:f,unit:u,rooms:'—',area:'—',price:null,status:'missing'}};
    statusNames.missing='Ma’lumot yo‘q';
    const fmt=formatMoney;
    // Backend is source of truth. Missing unit is not available or selectable for a lead.
    renderSelection();
    document.querySelectorAll('#units .unit').forEach(x=>{if(x.querySelector('.missing')) x.disabled=true});
    setInventoryMessage(data.units.length? 'Inventar API orqali yangilandi. Narx va mavjudlik serverdan olinadi.':'Bazadagi xonadonlar ro‘yxati bo‘sh. Administrator inventar kiritishi kerak.');
    const caption=document.querySelector('#lead-form .muted');caption.textContent='Murojaat serverga yuboriladi. Mavjudlik serverda qayta tekshiriladi.';
    document.querySelector('#submit-lead').textContent='Murojaat yuborish';
  }catch(err){liveMode=false;setInventoryMessage('Backendga ulanish yo‘q. Sintetik demo ko‘rsatilmoqda; murojaat yuborilmaydi.');}
}
// capture intercepts legacy demo handler, which stays available when API cannot be reached.
document.querySelector('#lead-form').addEventListener('submit', async function(e){
  if(!liveMode) return;
  e.preventDefault();e.stopImmediatePropagation();
  if(sending)return;
  const u=selected(),feedback=document.querySelector('#form-feedback'),submit=document.querySelector('#submit-lead');
  if(!liveUnits.has(u.id) || u.status!=='available'){feedback.textContent='Bu xonadon hozir mavjud emas.';feedback.className='error';return}
  const data=new FormData(e.currentTarget);
  if(!requestKey)requestKey=crypto.randomUUID();
  sending=true;submit.disabled=true;feedback.textContent='Yuborilmoqda…';feedback.className='';
  try{
    let r=await fetch('/api/public/leads',{method:'POST',headers:{'Content-Type':'application/json','Idempotency-Key':requestKey},body:JSON.stringify({unit_id:u.id,name:String(data.get('name')).trim(),phone:String(data.get('phone')).trim()})});
    const out=await r.json().catch(()=>({}));
    if(!r.ok)throw Error(typeof out.detail==='string'?out.detail:'Server xatosi ('+r.status+')');
    feedback.textContent='Murojaatingiz qabul qilindi. Raqam: #'+out.id;feedback.className='';
    // Keep the key for this successful submission to resist double submission.
  }catch(err){feedback.textContent=err.message||'Ulanishda xato. Qayta urinib ko‘ring.';feedback.className='error';}
  finally{sending=false;submit.disabled=false}
},true);
document.querySelector('#lead-dialog').addEventListener('close',()=>{requestKey=null});
loadInventory();
