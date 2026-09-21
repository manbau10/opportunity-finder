/* Opportunity Finder - dashboard behaviour */
'use strict';

const state = {
  q: '', min_score: 45, roles: [], countries: [], sources: [],
  status: 'open', window: 'any', deadline: 'live', sort: 'score'
};
const appConfig = window.APP || { track: 'academic', csrf: '', profileReady: false };
let lastItems = [];

const $  = (s) => document.querySelector(s);
const $$ = (s) => Array.from(document.querySelectorAll(s));
const esc = (s) => String(s == null ? '' : s)
  .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/* ------------------------------------------------------------------ theme */
const savedTheme = (() => { try { return localStorage.getItem('of-theme'); } catch (e) { return null; } })();
if (savedTheme) document.documentElement.setAttribute('data-theme', savedTheme);
else if (window.matchMedia && matchMedia('(prefers-color-scheme: dark)').matches)
  document.documentElement.setAttribute('data-theme', 'dark');

$('#themeBtn').addEventListener('click', () => {
  const next = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
  document.documentElement.setAttribute('data-theme', next);
  try { localStorage.setItem('of-theme', next); } catch (e) {}
});

/* ------------------------------------------------------------------ toast */
let toastTimer = null;
function toast(msg) {
  const el = $('#toast');
  el.textContent = msg;
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.hidden = true; }, 2200);
}

/* ------------------------------------------------------------------ fetch */
function query() {
  const p = new URLSearchParams();
  p.set('min_score', state.min_score);
  p.set('status', state.status);
  p.set('window', state.window);
  p.set('deadline', state.deadline);
  p.set('sort', state.sort);
  if (state.q) p.set('q', state.q);
  if (state.roles.length) p.set('roles', state.roles.join(','));
  if (state.countries.length) p.set('countries', state.countries.join(','));
  if (state.sources.length) p.set('sources', state.sources.join(','));
  return p.toString();
}

async function load() {
  const res = await fetch('/api/opportunities?' + query() + '&track=' + encodeURIComponent(appConfig.track));
  const data = await res.json();
  if (data.setup_required) {
    lastItems = []; renderStats({}); renderFacets({roles:[],countries:[],sources:[]});
    renderList([]); $('#empty').innerHTML = '<h3>Upload your ' + esc(appConfig.track) +
      ' CV to begin</h3><p><a class="btn primary" href="/profile">Upload CV</a></p>'; return;
  }
  lastItems = data.items;
  renderStats(data.summary);
  renderFacets(data.facets);
  renderList(data.items);
  updateFilterHint();
}

/* ------------------------------------------------------------------ stats */
function renderStats(s) {
  const when = s.last_refresh
    ? new Date(s.last_refresh).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : 'never';
  const cells = [
    ['hot',  s.new_today,    'found today'],
    ['hot',  s.strong,       'strong matches (70+)'],
    ['',     s.total,        'live opportunities'],
    ['warn', s.closing_soon, 'closing within 7 days'],
    ['',     s.saved,        'saved'],
    ['',     s.applied,      'applied']
  ];
  $('#stats').innerHTML = cells.map(([cls, n, k]) =>
    `<div class="stat ${cls}"><div class="n">${n ?? 0}</div><div class="k">${k}</div></div>`
  ).join('') +
  `<div class="stat"><div class="n" style="font-size:14px;padding-top:7px">${esc(when)}</div>
     <div class="k">last refresh</div></div>`;
}

/* ------------------------------------------------------------------ facets */
function renderFacets(f) {
  $('#roleFacets').innerHTML = f.roles.map(r =>
    `<button class="chip ${state.roles.includes(r.key) ? 'on' : ''}" data-role="${esc(r.key)}">
       ${esc(r.name)}<span class="n">${r.n}</span></button>`).join('');

  const listHTML = (rows, attr, stateKey, keyField, nameField) => rows.map(r => {
    const key = r[keyField];
    return `<label class="facet"><input type="checkbox" data-${attr}="${esc(key)}"
      ${state[stateKey].includes(key) ? 'checked' : ''}>
      <span>${esc(r[nameField])}</span><span class="n">${r.n}</span></label>`;
  }).join('');

  $('#countryFacets').innerHTML = listHTML(f.countries, 'country', 'countries', 'name', 'name');
  $('#sourceFacets').innerHTML  = listHTML(f.sources, 'source', 'sources', 'key', 'name');

  $$('[data-role]').forEach(b => b.onclick = () => { toggle('roles', b.dataset.role); load(); });
  $$('[data-country]').forEach(b => b.onchange = () => { toggle('countries', b.dataset.country); load(); });
  $$('[data-source]').forEach(b => b.onchange = () => { toggle('sources', b.dataset.source); load(); });
}

function toggle(key, value) {
  const arr = state[key];
  const i = arr.indexOf(value);
  if (i >= 0) arr.splice(i, 1); else arr.push(value);
}

/* ------------------------------------------------------------------ cards */
function ring(score) {
  const r = 24, c = 2 * Math.PI * r;
  const on = c * Math.max(0, Math.min(100, score)) / 100;
  const colour = score >= 70 ? 'var(--accent)' : score >= 55 ? 'var(--warn)' : 'var(--text-3)';
  return `<div class="ring">
    <svg width="56" height="56" viewBox="0 0 56 56">
      <circle cx="28" cy="28" r="${r}" fill="none" stroke="var(--surface-2)" stroke-width="5"/>
      <circle cx="28" cy="28" r="${r}" fill="none" stroke="${colour}" stroke-width="5"
              stroke-linecap="round" stroke-dasharray="${on.toFixed(1)} ${c.toFixed(1)}"/>
    </svg>
    <div class="num" style="color:${colour}">${score}</div>
  </div>`;
}

function deadlineTag(item) {
  if (item.days_left === null || item.days_left === undefined) {
    return item.deadline
      ? `<span class="tag deadline safe">closes ${esc(item.deadline)}</span>`
      : '<span class="tag">no deadline listed</span>';
  }
  const d = item.days_left;
  if (d < 0)  return `<span class="tag deadline gone">closed ${-d}d ago</span>`;
  if (d === 0) return '<span class="tag deadline">closes today</span>';
  if (d <= 14) return `<span class="tag deadline">${d} day${d === 1 ? '' : 's'} left</span>`;
  return `<span class="tag deadline safe">${d} days left</span>`;
}

function isNewToday(item) {
  return (item.first_seen || '').slice(0, 10) === new Date().toISOString().slice(0, 10);
}

function card(item) {
  const flags = (item.positives || []).slice(0, 1)
      .map(f => `<span class="tag good">${esc(f)}</span>`).join('')
    + (item.flags || []).slice(0, 2)
      .map(f => `<span class="tag flag">${esc(f)}</span>`).join('');
  const terms = (item.matched_terms || []).slice(0, 7).map(esc).join(', ');
  return `<article class="card ${isNewToday(item) ? 'is-new' : ''} ${item.status === 'dismissed' ? 'dismissed' : ''}" data-id="${esc(item.id)}">
    <div>${ring(item.score)}<div class="cap">match</div></div>
    <div>
      <h2>${esc(item.title)}</h2>
      <div class="org">${esc(item.org || 'Institution not stated')}${
        item.location ? `<span class="place">${esc(item.location)}</span>` : ''}</div>
      <div class="meta">
        ${isNewToday(item) ? '<span class="tag new">NEW</span>' : ''}
        <span class="tag role">${esc(item.role_label || '')}</span>
        ${deadlineTag(item)}
        <span class="tag">${esc(item.source)}</span>
        ${item.country ? `<span class="tag">${esc(item.country)}</span>` : ''}
        ${flags}
      </div>
      ${terms ? `<div class="terms"><b>Matches your work on:</b> ${esc(terms)}</div>` : ''}
    </div>
    <div class="card-actions">
      <a class="btn tiny primary" href="${esc(item.url)}" target="_blank" rel="noopener"
         onclick="event.stopPropagation()">Open advert</a>
      <button class="btn tiny" data-act="saved">${item.status === 'saved' ? '★ Saved' : '☆ Save'}</button>
      <button class="btn tiny" data-act="applied">${item.status === 'applied' ? '✓ Applied' : 'Applied'}</button>
      <button class="btn tiny ghost" data-act="dismissed">Hide</button>
      <button class="btn tiny pack-btn" data-pack="${esc(item.id)}">Create application pack</button>
    </div>
  </article>`;
}

function renderList(items) {
  $('#resultCount').innerHTML = `<strong>${items.length}</strong> opportunit${items.length === 1 ? 'y' : 'ies'}`;
  $('#list').innerHTML = items.map(card).join('');
  $('#empty').hidden = items.length > 0;
  if (!items.length) {
    $('#empty').innerHTML = `<h3>Nothing matches these filters</h3>
      <p>Lower the minimum match, widen the deadline filter, or press <em>Refresh now</em>.</p>`;
  }

  $$('.card').forEach(el => {
    el.addEventListener('click', () => openDrawer(el.dataset.id));
    el.querySelectorAll('[data-act]').forEach(btn => {
      btn.addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const item = lastItems.find(i => i.id === el.dataset.id);
        const want = btn.dataset.act;
        const next = item && item.status === want ? 'new' : want;
        await setStatus(el.dataset.id, next);
      });
    });
    el.querySelectorAll('[data-pack]').forEach(btn => btn.addEventListener('click', ev => {
      ev.stopPropagation(); createPack(btn.dataset.pack, btn);
    }));
  });
}

async function setStatus(id, status) {
  await fetch('/api/status', {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': appConfig.csrf },
    body: JSON.stringify({ id, status, track: appConfig.track })
  });
  const label = { saved: 'Saved', applied: 'Marked as applied', dismissed: 'Hidden', new: 'Reset' }[status];
  toast(label || 'Updated');
  load();
}

/* ------------------------------------------------------------------ drawer */
async function openDrawer(id) {
  const res = await fetch('/api/opportunity/' + encodeURIComponent(id) + '?track=' + encodeURIComponent(appConfig.track));
  if (!res.ok) return;
  const it = await res.json();
  const b = it.breakdown || {};
  const bar = (label, v) => `<div class="bar-row"><span>${label}</span>
      <div class="bar"><span style="width:${Math.max(0, Math.min(100, v || 0))}%"></span></div>
      <span class="pct">${Math.round(v || 0)}</span></div>`;

  $('#drawerBody').innerHTML = `
    <h2>${esc(it.title)}</h2>
    <div class="org">${esc(it.org || '')}${it.location ? ' &middot; ' + esc(it.location) : ''}</div>
    <div class="meta">
      <span class="tag role">${esc(it.role_label || '')}</span>
      ${deadlineTag(it)}
      <span class="tag">${esc(it.source)}</span>
      ${it.country ? `<span class="tag">${esc(it.country)}</span>` : ''}
    </div>

    <h4>Why it scored ${it.score}</h4>
    <div class="bars">
      ${bar('Subject fit', b.topic)}
      ${bar('Post type fit', b.role)}
      ${bar('Location fit', b.country)}
      ${bar('Timing', b.timing)}
    </div>

    ${(it.matched_terms || []).length ? `<h4>Overlap with your CV</h4>
      <p class="tiny">${(it.matched_terms || []).map(esc).join(' &middot; ')}</p>` : ''}

    ${(it.positives || []).length ? `<h4>In its favour</h4>
      <p class="tiny">${(it.positives || []).map(esc).join('<br>')}</p>` : ''}

    ${(it.flags || []).length ? `<h4>Watch out for</h4>
      <p class="tiny">${(it.flags || []).map(esc).join('<br>')}</p>` : ''}

    <h4>Details</h4>
    <dl class="kv">
      <dt>Deadline</dt><dd>${esc(it.deadline || 'not stated in the advert')}</dd>
      <dt>Posted</dt><dd>${esc(it.posted || 'unknown')}</dd>
      <dt>First seen here</dt><dd>${esc((it.first_seen || '').replace('T', ' '))}</dd>
      <dt>Found via</dt><dd>${esc(it.query || '')}</dd>
      <dt>Status</dt><dd>${esc(it.status)}</dd>
    </dl>

    <h4>Advert text</h4>
    <p class="desc">${esc((it.description || '').slice(0, 3500))}</p>

    <div class="drawer-actions">
      <a class="btn primary" href="${esc(it.url)}" target="_blank" rel="noopener">Open the advert</a>
      <button class="btn" data-d="saved">${it.status === 'saved' ? 'Unsave' : 'Save'}</button>
      <button class="btn" data-d="applied">${it.status === 'applied' ? 'Not applied' : 'Mark applied'}</button>
      <button class="btn ghost" data-d="dismissed">Hide this</button>
      <button class="btn primary" id="drawerPack">Create Word application pack</button>
    </div>`;

  $('#drawer').hidden = false;
  $$('#drawerBody [data-d]').forEach(btn => btn.onclick = async () => {
    const want = btn.dataset.d;
    await setStatus(it.id, it.status === want ? 'new' : want);
    $('#drawer').hidden = true;
  });
  $('#drawerPack').onclick = () => createPack(it.id, $('#drawerPack'));
}

async function createPack(id, button) {
  const old = button.textContent; button.disabled = true; button.textContent = 'Starting…';
  const response = await fetch('/api/packs', {
    method: 'POST', headers: {'Content-Type':'application/json','X-CSRF-Token':appConfig.csrf},
    body: JSON.stringify({opportunity_id:id, track:appConfig.track})
  });
  const data = await response.json();
  if (!response.ok) {
    button.disabled=false; button.textContent=old; toast(data.error || 'Could not create the pack.');
    if (data.settings_url && confirm((data.error || '') + '\n\nOpen API settings now?')) location.href=data.settings_url;
    return;
  }
  button.textContent='Researching and writing…';
  for (let attempt=0; attempt<80; attempt++) {
    await new Promise(resolve=>setTimeout(resolve,3000));
    const statusResponse=await fetch('/api/packs/'+encodeURIComponent(data.id));
    const pack=await statusResponse.json();
    if (pack.status==='ready') {
      button.textContent='Download ZIP'; button.disabled=false;
      button.onclick=()=>{location.href='/api/packs/'+encodeURIComponent(data.id)+'/download';};
      toast('Your editable Word application pack is ready.'); return;
    }
    if (pack.status==='failed') {
      button.disabled=false; button.textContent=old; toast(pack.error || 'Pack generation failed.'); return;
    }
  }
  button.disabled=false; button.textContent=old; toast('Generation is still running. Try again shortly.');
}

$('#drawerClose').onclick = () => { $('#drawer').hidden = true; };
$('#drawer').addEventListener('click', (e) => { if (e.target.id === 'drawer') $('#drawer').hidden = true; });
document.addEventListener('keydown', (e) => { if (e.key === 'Escape') $('#drawer').hidden = true; });

/* ------------------------------------------------------------------ filters */
let searchTimer = null;
$('#q').addEventListener('input', (e) => {
  state.q = e.target.value;
  clearTimeout(searchTimer);
  searchTimer = setTimeout(load, 250);
});

$('#minScore').addEventListener('input', (e) => {
  state.min_score = +e.target.value;
  $('#minScoreVal').textContent = e.target.value;
});
$('#minScore').addEventListener('change', load);

$('#sort').addEventListener('change', (e) => { state.sort = e.target.value; load(); });

function wireSegment(sel, key) {
  $$(sel + ' button').forEach(btn => btn.addEventListener('click', () => {
    $$(sel + ' button').forEach(b => b.classList.remove('on'));
    btn.classList.add('on');
    state[key] = btn.dataset.v;
    load();
  }));
}
wireSegment('#deadlineSeg', 'deadline');
wireSegment('#windowSeg', 'window');
wireSegment('#statusSeg', 'status');

$('#clearBtn').addEventListener('click', () => {
  Object.assign(state, { q: '', min_score: 45, roles: [], countries: [], sources: [],
                         status: 'open', window: 'any', deadline: 'live', sort: 'score' });
  $('#q').value = '';
  $('#minScore').value = 45;
  $('#minScoreVal').textContent = '45';
  $('#sort').value = 'score';
  [['#deadlineSeg', 'live'], ['#windowSeg', 'any'], ['#statusSeg', 'open']].forEach(([sel, v]) => {
    $$(sel + ' button').forEach(b => b.classList.toggle('on', b.dataset.v === v));
  });
  load();
});

/* ------------------------------------------------------------------ refresh */
let pollTimer = null;

async function pollRefresh() {
  const s = await (await fetch('/api/refresh/status')).json();
  const el = $('#refreshState');
  const btn = $('#refreshBtn');

  if (s.running) {
    el.className = 'refresh-state busy';
    el.textContent = s.stage + '…';
    btn.disabled = true;
    btn.querySelector('svg').classList.add('spin');
    if (!pollTimer) pollTimer = setInterval(pollRefresh, 1500);
    return;
  }

  btn.disabled = false;
  btn.querySelector('svg').classList.remove('spin');
  if (pollTimer) { clearInterval(pollTimer); pollTimer = null; load(); }

  if (s.error) {
    el.className = 'refresh-state err';
    el.textContent = 'Last refresh failed: ' + s.error;
  } else if (s.finished) {
    el.className = 'refresh-state';
    el.textContent = `${s.found} scanned · ${s.added} new · ${s.updated} updated`;
  } else {
    el.className = 'refresh-state';
    el.textContent = '';
  }
}

$('#refreshBtn').addEventListener('click', async () => {
  $('#refreshBtn').disabled = true;
  await fetch('/api/refresh', { method: 'POST' });
  toast('Searching the job boards… this takes a few minutes.');
  pollRefresh();
});

/* --------------------------------------------------- filters on a phone */
// The panel is open in the markup so desktop needs no JS; a narrow screen
// collapses it so the results, not the controls, are what you land on.
if (window.innerWidth <= 940) $('#filters').removeAttribute('open');

function updateFilterHint() {
  const active = [];
  if (state.q) active.push('search');
  if (state.min_score !== 45) active.push(state.min_score + '+');
  if (state.roles.length) active.push(state.roles.length + ' type' + (state.roles.length > 1 ? 's' : ''));
  if (state.countries.length) active.push(state.countries.length + ' countr' + (state.countries.length > 1 ? 'ies' : 'y'));
  if (state.sources.length) active.push(state.sources.length + ' source' + (state.sources.length > 1 ? 's' : ''));
  if (state.deadline !== 'live') active.push(state.deadline === 'soon' ? 'closing soon' : 'any deadline');
  if (state.window !== 'any') active.push(state.window);
  if (state.status !== 'open') active.push(state.status);
  $('#filtersHint').textContent = active.length ? active.join(' · ') : 'none applied';
}

/* ------------------------------------------------------------------ start */
load();
pollRefresh();
setInterval(pollRefresh, 20000);
