'use strict';

const el = id => document.getElementById(id);
const esc = value => String(value ?? '').replace(/[&<>"']/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[char]));
const stageLabels = {new:'Yangi',contacted:'Bog‘lanilgan',qualified:'Qiziqish bildirgan',closed_lost:'Yopilgan (sotilmadi)'};
let currentLead = null;
let currentUser = null;
let accessToken = null;
let refreshPromise = null;
let authGeneration = 0;
const authChannel = typeof BroadcastChannel !== 'undefined' ? new BroadcastChannel('qurlish-auth') : null;
function clearAuth() {
  authGeneration++;
  accessToken = null;
  currentUser = null;
  leads = [];
  currentLead = null;
  el('login').hidden = false;
  el('workspace').hidden = true;
}
authChannel?.addEventListener('message', clearAuth);
async function withAuthLock(work) {
  return navigator.locks ? navigator.locks.request('qurlish-auth', work) : work();
}
let leads = [];

async function refreshAuth() {
  if (!navigator.locks) return null;
  if (!refreshPromise) {
    const generation = authGeneration;
    refreshPromise = withAuthLock(async () => {
        if (generation !== authGeneration) return null;
        const response = await fetch('/api/auth/refresh', {method:'POST', credentials:'same-origin'});
        if (!response.ok) return null;
        const data = await response.json();
        if (generation !== authGeneration) return null;
        accessToken = data.access_token;
        return data;
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

async function request(url, options = {}) {
  const headers = new Headers(options.headers);
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  const response = await fetch(url, {...options, credentials:'same-origin', headers});
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : `API xatosi ${response.status}`);
  return data;
}

async function api(url, options = {}) {
  if (url === '/api/auth/login') {
    const generation = ++authGeneration;
    return withAuthLock(async () => {
      if (generation !== authGeneration) throw Error('Sessiya o‘zgargan');
      const data = await request(url, options);
      if (generation !== authGeneration) throw Error('Sessiya o‘zgargan');
      accessToken = data.access_token;
      currentUser = data.user;
      authChannel?.postMessage('session-changed');
      return currentUser;
    });
  }
  if (url === '/api/auth/logout') {
    const token = accessToken;
    clearAuth();
    authChannel?.postMessage('logout');
    return withAuthLock(() => request(url, {...options, headers: token ? {Authorization:`Bearer ${token}`} : {}}));
  }

  const generation = authGeneration;
  let response;
  try {
    response = await fetchWithToken(url, options);
    if (response.status === 401 && accessToken) {
      const renewed = await refreshAuth();
      if (renewed) response = await fetchWithToken(url, options);
      else clearAuth();
    }
  } catch (error) {
    throw error;
  }
  const data = await response.json().catch(() => ({}));
  if (generation !== authGeneration) throw Error('Sessiya o‘zgargan');
  if (!response.ok) throw Error(typeof data.detail === 'string' ? data.detail : `API xatosi ${response.status}`);
  return data;
}

async function fetchWithToken(url, options) {
  const headers = new Headers(options.headers);
  if (!headers.has('Content-Type')) headers.set('Content-Type', 'application/json');
  if (accessToken) headers.set('Authorization', `Bearer ${accessToken}`);
  return fetch(url, {...options, credentials:'same-origin', headers});
}

function feedback(message) { el('staff-feedback').textContent = message; }

async function init() {
  try {
    const session = await refreshAuth();
    if (!session) throw Error('Sessiya tugagan');
    currentUser = session.user;
    const user = await api('/api/crm/me');
    el('login').hidden = true;
    el('workspace').hidden = false;
    el('who').textContent = `${user.email} · ${user.role}`;
    el('note-form').hidden = user.role === 'viewer';
    await load();
  } catch {
    accessToken = null;
    currentUser = null;
    el('login').hidden = false;
    el('workspace').hidden = true;
  }
}

el('login-form').addEventListener('submit', async event => {
  event.preventDefault();
  const form = new FormData(event.target);
  try {
    await api('/api/auth/login', {method:'POST', body:JSON.stringify({email:form.get('email'), password:form.get('password')})});
    el('login-error').textContent = '';
    await init();
  } catch (error) {
    el('login-error').textContent = error.message;
  }
});

el('logout').addEventListener('click', async () => {
  await api('/api/auth/logout', {method:'POST'}).catch(() => {});
  location.reload();
});

async function load() {
  feedback('Yuklanmoqda…');
  try {
    const days = el('days').value;
    const [metrics, result] = await Promise.all([api(`/api/crm/metrics?days=${days}`), api(`/api/crm/leads?days=${days}`)]);
    leads = result.leads;
    render(metrics);
    feedback('Yangilandi: ' + new Date(metrics.as_of).toLocaleString('uz-UZ'));
  } catch (error) {
    feedback('Xatolik: ' + error.message);
    el('kpis').textContent = 'Ma’lumotlarni yuklab bo‘lmadi';
    el('live-chart').textContent = '';
    el('live-kanban').textContent = '';
    el('live-contacts').textContent = '';
  }
}

function render(metrics) {
  el('kpis').innerHTML = `<div class="stat"><span>Murojaatlar</span><strong>${metrics.count}</strong><small>ta / ${metrics.days} kun</small></div><div class="stat"><span>Yangi</span><strong>${metrics.stages.new}</strong><small>ta</small></div><div class="stat"><span>Faol</span><strong>${metrics.stages.contacted + metrics.stages.qualified}</strong><small>ta</small></div>`;
  const max = Math.max(1, ...metrics.bins);
  el('live-chart').innerHTML = metrics.bins.map((count, index) => `<div class="bar" style="height:${Math.max(3, 100 * count / max)}%" title="${count} ta"><span>${index + 1}</span></div>`).join('');
  el('live-chart').setAttribute('aria-label', `${metrics.days} kun ichida: ${metrics.bins.join(', ')} ta`);
  el('live-funnel').innerHTML = Object.entries(stageLabels).map(([stage, label]) => `<p>${label}: ${metrics.stages[stage]} ta</p>`).join('');
  el('unit-status').textContent = Object.entries({available:'Bo‘sh', reserved:'Bron', sold:'Sotilgan'}).map(([status, label]) => `${label}: ${metrics.unit_statuses[status]} ta`).join(' · ');
  renderBoard();
  renderContacts();
}

function actionSelect(lead) {
  const disabled = currentUser?.role === 'viewer' ? 'disabled' : '';
  return `<label>Bosqich <select class="stage-select" data-lead="${lead.id}" aria-label="${esc(lead.name)} bosqichini o‘zgartirish" ${disabled}>${Object.entries(stageLabels).map(([stage, label]) => `<option value="${stage}" ${lead.stage === stage ? 'selected' : ''}>${label}</option>`).join('')}</select></label>`;
}

function renderBoard() {
  el('live-kanban').innerHTML = Object.entries(stageLabels).map(([stage, label]) => `<div class="staff-col"><h3>${label} · ${leads.filter(lead => lead.stage === stage).length}</h3>${leads.filter(lead => lead.stage === stage).map(lead => `<article class="staff-lead"><strong>${esc(lead.name)}</strong><p>${esc(lead.unit_id)}</p>${actionSelect(lead)}<button type="button" data-history="${lead.id}">Tarix / eslatma</button></article>`).join('')}</div>`).join('');
}

function renderContacts() {
  el('live-contacts').innerHTML = leads.length ? `<table class="staff-table"><thead><tr><th>Mijoz</th><th>Xonadon</th><th>Aloqa</th><th>Bosqich</th><th>Amallar</th></tr></thead><tbody>${leads.map(lead => `<tr><td>${esc(lead.name)}</td><td>${esc(lead.unit_id)}</td><td><a href="tel:${esc(lead.phone.replace(/[^+0-9]/g, ''))}">${esc(lead.phone)}</a></td><td>${actionSelect(lead)}</td><td><button data-history="${lead.id}">Tarix / eslatma</button></td></tr>`).join('')}</tbody></table>` : 'Bu davrda murojaat yo‘q.';
}

document.addEventListener('change', async event => {
  if (!event.target.matches('[data-lead]') || currentUser?.role === 'viewer') return;
  const control = event.target;
  const id = Number(control.dataset.lead);
  const previous = leads.find(lead => lead.id === id)?.stage;
  control.disabled = true;
  try {
    await api(`/api/crm/leads/${id}/stage`, {method:'PATCH', body:JSON.stringify({stage:control.value})});
    await load();
  } catch (error) {
    control.value = previous;
    feedback('Server rad etdi; avvalgi holat qaytarildi: ' + error.message);
  } finally {
    control.disabled = currentUser?.role === 'viewer';
  }
});

document.addEventListener('click', async event => {
  const button = event.target.closest('[data-history]');
  if (!button) return;
  currentLead = Number(button.dataset.history);
  const lead = leads.find(item => item.id === currentLead);
  el('history-title').textContent = lead.name + ' · ' + lead.unit_id;
  el('history').hidden = false;
  el('history').scrollIntoView({behavior:'auto'});
  try { await loadEvents(); } catch (error) { feedback(error.message); }
});

async function loadEvents() {
  const events = await api(`/api/crm/leads/${currentLead}/events`);
  el('events').innerHTML = events.length ? events.map(item => `<p><strong>${esc(item.kind)}</strong> · ${esc(item.actor)} · ${esc(item.created_at)}<br>${esc(item.value)}</p>`).join('') : 'Hozircha tarix yo‘q';
}

el('note-form').addEventListener('submit', async event => {
  event.preventDefault();
  if (currentUser?.role === 'viewer') return;
  try {
    await api(`/api/crm/leads/${currentLead}/notes`, {method:'POST', body:JSON.stringify({note:el('note').value})});
    el('note').value = '';
    await loadEvents();
    feedback('Ichki eslatma saqlandi');
  } catch (error) { feedback(error.message); }
});

el('close-history').addEventListener('click', () => { el('history').hidden = true; currentLead = null; });
for (const [button, section] of [['dashboard-btn','dashboard'], ['kanban-btn','board'], ['list-btn','people']]) {
  el(button).addEventListener('click', () => { for (const id of ['dashboard','board','people']) el(id).hidden = id !== section; });
}
el('days').addEventListener('change', load);
el('refresh').addEventListener('click', load);
init();
