
const form = document.querySelector('#search-form');
const q = document.querySelector('#query');
const autocompleteEl = document.querySelector('#autocomplete');
const statusEl = document.querySelector('#status');
const storeStatus = document.querySelector('#store-status');
const table = document.querySelector('#results-table');
const body = document.querySelector('#results-body');
const cardsGrid = document.querySelector('#results-cards');
const filters = document.querySelector('#filters');
const pagination = document.querySelector('#pagination');
const resultsWrap = document.querySelector('.results-wrap');
const storeFilter = document.querySelector('#store-filter');
const currencyFilter = document.querySelector('#currency-filter');
const conditionFilter = document.querySelector('#condition-filter');
const priceSort = document.querySelector('#price-sort');
const viewButtons = [...document.querySelectorAll('.view-button')];
const modal = document.querySelector('#image-modal');
const modalImage = document.querySelector('#modal-image');
const modalTitle = document.querySelector('#modal-title');
const modalStore = document.querySelector('#modal-store');
const modalSet = document.querySelector('#modal-set');
const modalMeta = document.querySelector('#modal-meta');
const modalPrice = document.querySelector('#modal-price');
const modalStock = document.querySelector('#modal-stock');
const modalLink = document.querySelector('#modal-link');
const modalClose = document.querySelector('#modal-close');

let rows = [];
let visibleRows = [];
let currentPageRows = [];
let currentPage = 1;
const PAGE_SIZE = 24;
let currentView = localStorage.getItem('fetchuccini:view') || 'cards';
let activeStoreKeys = [];
let storeRows = new Map();
let storeStates = new Map();
let searchGeneration = 0;
let autocompleteTimer = null;
let autocompleteController = null;
let autocompleteItems = [];
let autocompleteIndex = -1;
let autocompleteGeneration = 0;

const STORE_LABELS = {
  pirulo: 'Pirulo',
  mercadia: 'Mercadia',
  magic_lair: 'Magic Lair',
  batikueva: 'La Batikueva',
  magicdealers: 'MagicDealers',
  la_workshop: 'La Workshop',
  starcitygames: 'StarCityGames',
};

function closeAutocomplete(){
  autocompleteItems = [];
  autocompleteIndex = -1;
  autocompleteEl.innerHTML = '';
  autocompleteEl.classList.add('hidden');
  q.setAttribute('aria-expanded','false');
  q.removeAttribute('aria-activedescendant');
}

function setAutocompleteIndex(index){
  const options = [...autocompleteEl.querySelectorAll('.autocomplete-option')];
  if(!options.length){ autocompleteIndex = -1; return; }
  autocompleteIndex = Math.max(-1, Math.min(index, options.length - 1));
  options.forEach((option,i)=>{
    const active = i === autocompleteIndex;
    option.classList.toggle('active', active);
    option.setAttribute('aria-selected', active ? 'true' : 'false');
  });
  if(autocompleteIndex >= 0){
    const active = options[autocompleteIndex];
    q.setAttribute('aria-activedescendant', active.id);
    active.scrollIntoView({block:'nearest'});
  }else{
    q.removeAttribute('aria-activedescendant');
  }
}

function chooseAutocomplete(index){
  const value = autocompleteItems[index];
  if(!value) return;
  q.value = value;
  closeAutocomplete();
  q.focus();
}

function renderAutocomplete(items){
  autocompleteItems = items.slice(0,8);
  autocompleteIndex = -1;
  if(!autocompleteItems.length){ closeAutocomplete(); return; }
  autocompleteEl.innerHTML = autocompleteItems.map((name,index)=>`
    <button
      type="button"
      id="autocomplete-option-${index}"
      class="autocomplete-option"
      role="option"
      data-index="${index}"
      aria-selected="false"
    >
      <span class="autocomplete-name">${esc(name)}</span>
      <span class="autocomplete-source">Scryfall</span>
    </button>`).join('');
  autocompleteEl.classList.remove('hidden');
  q.setAttribute('aria-expanded','true');
}

async function loadAutocomplete(value){
  const query = value.trim();
  autocompleteGeneration += 1;
  const generation = autocompleteGeneration;

  if(autocompleteController) autocompleteController.abort();
  if(query.length < 2){ closeAutocomplete(); return; }

  autocompleteController = new AbortController();
  try{
    const params = new URLSearchParams({q:query});
    const response = await fetch(`/api/autocomplete/?${params}`, {signal:autocompleteController.signal});
    if(!response.ok) throw new Error('autocomplete');
    const data = await response.json();
    if(generation !== autocompleteGeneration || q.value.trim() !== query) return;
    renderAutocomplete(data.suggestions || []);
  }catch(err){
    if(err.name !== 'AbortError' && generation === autocompleteGeneration) closeAutocomplete();
  }
}

q.addEventListener('input',()=>{
  clearTimeout(autocompleteTimer);
  const value = q.value;
  if(value.trim().length < 2){ closeAutocomplete(); return; }
  autocompleteTimer = setTimeout(()=>loadAutocomplete(value), 280);
});

q.addEventListener('keydown',event=>{
  if(autocompleteEl.classList.contains('hidden')) return;
  if(event.key === 'ArrowDown'){
    event.preventDefault();
    setAutocompleteIndex(autocompleteIndex + 1);
  }else if(event.key === 'ArrowUp'){
    event.preventDefault();
    setAutocompleteIndex(autocompleteIndex <= 0 ? autocompleteItems.length - 1 : autocompleteIndex - 1);
  }else if(event.key === 'Enter' && autocompleteIndex >= 0){
    event.preventDefault();
    chooseAutocomplete(autocompleteIndex);
  }else if(event.key === 'Escape'){
    closeAutocomplete();
  }
});

autocompleteEl.addEventListener('mousedown',event=>{
  const option = event.target.closest('.autocomplete-option');
  if(!option) return;
  event.preventDefault();
  chooseAutocomplete(Number(option.dataset.index));
});

document.addEventListener('click',event=>{
  if(!event.target.closest('.search-input-wrap')) closeAutocomplete();
});

function selectedStores(){return [...document.querySelectorAll('#stores input:checked')].map(x=>x.value)}
function esc(v){return String(v ?? '').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#039;'}[c]))}
function unique(key){return [...new Set(rows.map(r=>r[key]).filter(Boolean))].sort((a,b)=>String(a).localeCompare(String(b),'es',{sensitivity:'base'}))}
function fillSelect(el, values){
  const first=el.options[0];
  const previous=el.value;
  el.innerHTML='';
  el.append(first);
  values.forEach(v=>{const o=document.createElement('option');o.value=v;o.textContent=v;el.append(o)});
  if([...el.options].some(o=>o.value===previous))el.value=previous;
}

function comparePrice(a,b,order){
  const currencyA=String(a.currency||'');
  const currencyB=String(b.currency||'');
  const currencyCompare=currencyA.localeCompare(currencyB,'es',{sensitivity:'base'});
  if(currencyCompare!==0)return currencyCompare;

  const missingA=a.price==null||Number.isNaN(Number(a.price));
  const missingB=b.price==null||Number.isNaN(Number(b.price));
  if(missingA&&missingB)return 0;
  if(missingA)return 1;
  if(missingB)return -1;

  const priceA=Number(a.price);
  const priceB=Number(b.price);
  if(priceA===priceB)return 0;
  return order==='desc' ? priceB-priceA : priceA-priceB;
}

function formatPrice(value,currency){
  if(value==null||Number.isNaN(Number(value)))return '—';
  const number=Number(value);
  const code=String(currency||'').toUpperCase();
  const digits=code==='USD'?2:(Number.isInteger(number)?0:2);
  const formatted=new Intl.NumberFormat('es-AR',{minimumFractionDigits:digits, maximumFractionDigits:digits}).format(number);
  return `${esc(code)} ${esc(formatted)}`.trim();
}

function slugify(value){
  return String(value||'')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g,'')
    .replace(/[^a-z0-9]+/g,'-')
    .replace(/^-+|-+$/g,'');
}

function conditionClass(value){
  const t=slugify(value);
  if(!t) return '';

  // Excelente / EX-NM es la nomenclatura que usa Mercadia para su mejor estado.
  if(
    t.includes('near-mint') || t === 'nm' || t === 'mint' ||
    t.includes('excelente') || t.includes('ex-nm') || t === 'ex' ||
    t.includes('como-nueva') || t.includes('como-nuevo')
  ) return 'cond-near-mint';

  if(
    t.includes('lightly-played') || t === 'lp' ||
    t.includes('levemente-jugada') || t.includes('ligeramente-jugada') ||
    t.includes('poco-jugada')
  ) return 'cond-lightly-played';

  if(
    t.includes('moderately-played') || t === 'mp' ||
    t.includes('moderadamente-jugada')
  ) return 'cond-moderately-played';

  // Chequear estos antes de "jugada" para no clasificar "Muy Jugada" como SP.
  if(
    t.includes('heavily-played') || t === 'hp' ||
    t.includes('muy-jugada') || t.includes('muy-jugado') ||
    t.includes('muy-usada') || t.includes('muy-usado')
  ) return 'cond-heavily-played';

  if(
    t.includes('damaged') || t.includes('poor') || t === 'dmg' || t === 'dm' ||
    t.includes('danada') || t.includes('danado')
  ) return 'cond-damaged';

  if(
    t.includes('played') || t === 'sp' || t.includes('slightly-played') ||
    t.includes('jugada') || t.includes('jugado')
  ) return 'cond-played';

  return '';
}

function badge(value, extra=''){
  return value ? `<span class="badge ${extra}">${esc(value)}</span>` : '<span class="muted">—</span>';
}

function storeClass(value){
  const t=slugify(value);
  if(t.includes('pirulo')) return 'store-pirulo';
  if(t.includes('mercadia')) return 'store-mercadia';
  if(t.includes('magic-lair')) return 'store-magic-lair';
  if(t.includes('batikueva')) return 'store-la-batikueva';
  if(t.includes('magicdealers')) return 'store-magicdealers';
  if(t.includes('la-workshop')) return 'store-la-workshop';
  if(t.includes('starcitygames')) return 'store-starcitygames';
  return '';
}

function storeBadge(value){
  if(!value) return '<span class="muted">—</span>';
  const c=storeClass(value);
  return `<span class="store-badge ${c}"><span class="store-dot"></span>${esc(value)}</span>`;
}

function finishText(row){
  return [row.finish,row.style].filter(Boolean).join(' · ');
}

function thumbMarkup(row, index){
  if(row.image_url){
    return `<img class="thumb clickable js-open-modal" data-index="${index}" src="${esc(row.image_url)}" loading="lazy" alt="${esc(row.card_name||'Carta')}" title="Click para ampliar">`;
  }
  return '<div class="thumb image-ghost">Sin imagen</div>';
}

function renderTable(filtered){
  if(!filtered.length){
    body.innerHTML='<tr><td colspan="10" class="empty-state">No se encontraron publicaciones con los filtros actuales.</td></tr>';
    return;
  }

  body.innerHTML=filtered.map((r,index)=>{
    const finish=finishText(r);
    const stockText=r.stock==null?(r.available?'Sí':'—'):esc(r.stock);
    const condClass=conditionClass(r.condition);
    return `<tr>
      <td>
        <div class="cardcell">
          <div class="thumb-wrap">${thumbMarkup(r,index)}</div>
          <div class="card-main">
            <span class="card-name">${esc(r.card_name)}</span>
            <span class="card-meta">${esc(r.store)} · ${esc(r.language||'Idioma no informado')}</span>
          </div>
        </div>
      </td>
      <td>${storeBadge(r.store)}</td>
      <td><span class="set-name">${esc(r.set_name||r.set_code||'—')}</span></td>
      <td class="collector">${esc(r.collector_number||'—')}</td>
      <td class="language">${esc(r.language||'—')}</td>
      <td>${badge(r.condition, conditionClass(r.condition))}</td>
      <td>${badge(finish,'finish')}</td>
      <td class="stock-cell"><span class="stock-badge ${r.available?'good':'bad'}">${stockText}</span></td>
      <td class="price">${formatPrice(r.price,r.currency)}</td>
      <td class="action-cell">${r.url?`<a class="buy" target="_blank" rel="noopener" href="${esc(r.url)}">Comprar</a>`:''}</td>
    </tr>`;
  }).join('');
}

function renderCards(filtered){
  if(!filtered.length){
    cardsGrid.innerHTML='<div class="empty-state">No se encontraron publicaciones con los filtros actuales.</div>';
    return;
  }

  cardsGrid.innerHTML=filtered.map((r,index)=>{
    const finish=finishText(r);
    const stockText=r.stock==null?(r.available?'Disponible':'Sin stock'):String(r.stock);
    return `<article class="result-card">
      <div class="result-card-top">
        <div class="thumb-wrap">${thumbMarkup(r,index)}</div>
        <div class="card-main">
          <div>${storeBadge(r.store)}</div>
          <h3 class="result-card-title">${esc(r.card_name)}</h3>
          <p class="result-card-sub">${esc(r.set_name||r.set_code||'Edición no informada')}</p>
          <p class="result-card-sub"># ${esc(r.collector_number||'—')} · ${esc(r.language||'—')}</p>
        </div>
      </div>
      <div class="result-card-meta">
        <div class="meta-block"><span class="meta-label">Condición</span><span class="meta-value">${badge(r.condition, conditionClass(r.condition))}</span></div>
        <div class="meta-block"><span class="meta-label">Acabado</span><span class="meta-value">${badge(finish,'finish')}</span></div>
        <div class="meta-block"><span class="meta-label">Stock</span><span class="meta-value"><span class="stock-badge ${r.available?'good':'bad'}">${esc(stockText)}</span></span></div>
        <div class="meta-block"><span class="meta-label">Moneda</span><span class="meta-value">${esc(r.currency||'—')}</span></div>
      </div>
      <div class="result-card-footer">
        <div class="result-card-price">
          <span class="meta-label">Precio</span>
          <span class="price">${formatPrice(r.price,r.currency)}</span>
        </div>
        <div class="result-card-actions">
          <button type="button" class="sort-button js-open-modal" data-index="${index}">Ver</button>
          ${r.url?`<a class="buy" target="_blank" rel="noopener" href="${esc(r.url)}">Comprar</a>`:''}
        </div>
      </div>
    </article>`;
  }).join('');
}

function setView(view){
  currentView = view === 'cards' ? 'cards' : 'table';
  localStorage.setItem('fetchuccini:view', currentView);
  viewButtons.forEach(btn => btn.classList.toggle('active', btn.dataset.view === currentView));
  table.classList.toggle('hidden', currentView !== 'table');
  cardsGrid.classList.toggle('hidden', currentView !== 'cards');
}

function openModal(index){
  const row = currentPageRows[index];
  if(!row) return;
  modalImage.src = row.image_url || '';
  modalImage.alt = row.card_name || 'Carta';
  modalTitle.textContent = row.card_name || 'Carta';
  modalStore.innerHTML = storeBadge(row.store);
  modalSet.textContent = row.set_name || row.set_code || 'Edición no informada';
  modalMeta.innerHTML = [
    badge(row.condition, conditionClass(row.condition)),
    badge(finishText(row), 'finish'),
    badge(`Idioma: ${row.language || '—'}`),
    badge(`# ${row.collector_number || '—'}`)
  ].join('');
  modalPrice.textContent = formatPrice(row.price, row.currency);
  modalStock.textContent = row.available ? `Stock: ${row.stock ?? 'Disponible'}` : 'Sin stock';
  modalLink.href = row.url || '#';
  modalLink.style.display = row.url ? 'inline-flex' : 'none';
  modal.classList.remove('hidden');
  modal.setAttribute('aria-hidden', 'false');
  document.body.style.overflow = 'hidden';
}

function closeModal(){
  modal.classList.add('hidden');
  modal.setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
}

function paginationItems(totalPages, page){
  if(totalPages <= 7) return Array.from({length:totalPages}, (_,i)=>i+1);
  const items = new Set([1,totalPages,page-1,page,page+1]);
  const pages = [...items].filter(n=>n>=1&&n<=totalPages).sort((a,b)=>a-b);
  const result=[];
  let previous=0;
  for(const n of pages){
    if(previous && n-previous>1) result.push('…');
    result.push(n);
    previous=n;
  }
  return result;
}

function renderPagination(totalResults){
  const totalPages = Math.max(1, Math.ceil(totalResults / PAGE_SIZE));
  currentPage = Math.max(1, Math.min(currentPage, totalPages));

  if(totalResults <= PAGE_SIZE){
    pagination.innerHTML='';
    pagination.classList.add('hidden');
    return;
  }

  const items = paginationItems(totalPages,currentPage);
  pagination.innerHTML = `
    <span class="pagination-summary">Página ${currentPage} de ${totalPages} · ${totalResults} resultados</span>
    <button type="button" class="page-button" data-page="${currentPage-1}" ${currentPage===1?'disabled':''}>‹</button>
    ${items.map(item=>item==='…'
      ? '<span class="page-ellipsis">…</span>'
      : `<button type="button" class="page-button ${item===currentPage?'active':''}" data-page="${item}">${item}</button>`
    ).join('')}
    <button type="button" class="page-button" data-page="${currentPage+1}" ${currentPage===totalPages?'disabled':''}>›</button>`;
  pagination.classList.remove('hidden');
}

function render(){
  const store=storeFilter.value;
  const cur=currencyFilter.value;
  const cond=conditionFilter.value;
  const order=priceSort.dataset.order||'asc';

  visibleRows=rows
    .filter(r=>(!store||r.store===store)&&(!cur||r.currency===cur)&&(!cond||r.condition===cond))
    .slice()
    .sort((a,b)=>comparePrice(a,b,order));

  const totalPages=Math.max(1,Math.ceil(visibleRows.length/PAGE_SIZE));
  currentPage=Math.max(1,Math.min(currentPage,totalPages));
  const start=(currentPage-1)*PAGE_SIZE;
  currentPageRows=visibleRows.slice(start,start+PAGE_SIZE);

  renderTable(currentPageRows);
  renderCards(currentPageRows);
  renderPagination(visibleRows.length);
  setView(currentView);
  updateOverallStatus();
}

[storeFilter,currencyFilter,conditionFilter].forEach(x=>x.addEventListener('change',()=>{currentPage=1;render();}));
viewButtons.forEach(btn=>btn.addEventListener('click',()=>setView(btn.dataset.view)));
pagination.addEventListener('click',event=>{
  const button=event.target.closest('.page-button[data-page]');
  if(!button||button.disabled)return;
  currentPage=Number(button.dataset.page)||1;
  render();
  resultsWrap.scrollIntoView({behavior:'smooth',block:'start'});
});

priceSort.addEventListener('click',()=>{
  const next=priceSort.dataset.order==='asc'?'desc':'asc';
  priceSort.dataset.order=next;
  priceSort.textContent=next==='asc'?'Menor → Mayor':'Mayor → Menor';
  priceSort.setAttribute('aria-label',next==='asc'?'Ordenar precio de menor a mayor':'Ordenar precio de mayor a menor');
  currentPage=1;
  render();
});

function handleOpenModalFromEvent(event){
  const trigger = event.target.closest('.js-open-modal');
  if(!trigger) return;
  openModal(Number(trigger.dataset.index));
}

body.addEventListener('click', handleOpenModalFromEvent);
cardsGrid.addEventListener('click', handleOpenModalFromEvent);
modal.addEventListener('click', event => { if(event.target.hasAttribute('data-close-modal')) closeModal(); });
modalClose.addEventListener('click', closeModal);
document.addEventListener('keydown', event => { if(event.key === 'Escape' && !modal.classList.contains('hidden')) closeModal(); });

function formatAge(seconds){
  const value = Math.max(0, Number(seconds) || 0);
  if(value < 60) return `${Math.round(value)} s`;
  if(value < 3600) return `${Math.round(value / 60)} min`;
  return `${Math.round(value / 3600)} h`;
}

function isStoreFinished(state){
  return ['done','cached','error','stale-error'].includes(state?.status);
}

function friendlyStoreError(error){
  const text = String(error || '');
  const low = text.toLowerCase();
  if(low.includes('mercadia bridge') || low.includes('sincronización local')) return 'pendiente de sincronización';
  if(low.includes('403') || low.includes('forbidden')) return 'no disponible online';
  if(low.includes('429') || low.includes('too many requests')) return 'límite de consultas';
  if(low.includes('timeout') || low.includes('timed out')) return 'demoró demasiado';
  if(low.includes('ssl') || low.includes('eof')) return 'conexión inestable';
  return 'no respondió';
}

function renderStoreStates(){
  storeStatus.innerHTML = activeStoreKeys.map(key => {
    const state = storeStates.get(key) || {status:'loading'};
    const label = state.label || STORE_LABELS[key] || key;
    const count = Number(state.count || 0);
    const elapsed = Number(state.elapsed_ms || 0);
    const age = formatAge(state.age_seconds || 0);
    const title = state.error ? ` title="${esc(state.error)}"` : '';

    if(state.status === 'bridge-pending'){
      return `<span class="pill loading">${esc(label)}: esperando sincronización…</span>`;
    }
    if(state.bridge){
      if(state.status === 'refreshing'){
        return `<span class="pill cached loading"${title}>${esc(label)}: ${count} · sincronizado hace ${age} · actualizando…</span>`;
      }
      if(state.status === 'stale-error'){
        return `<span class="pill stale"${title}>${esc(label)}: ${count} · sincronizado hace ${age} · actualización pendiente</span>`;
      }
      if(state.status === 'cached' || state.status === 'done'){
        return `<span class="pill cached"${title}>${esc(label)}: ${count} · sincronizado hace ${age}</span>`;
      }
    }
    if(state.status === 'cached'){
      return `<span class="pill cached"${title}>${esc(label)}: ${count} · cache ${age}</span>`;
    }
    if(state.status === 'refreshing'){
      return `<span class="pill stale loading"${title}>${esc(label)}: ${count} · actualizando…</span>`;
    }
    if(state.status === 'stale-error'){
      return `<span class="pill stale"${title}>${esc(label)}: ${count} · último dato ${age}</span>`;
    }
    if(state.status === 'error'){
      return `<span class="pill error"${title}>${esc(label)}: ${esc(friendlyStoreError(state.error))}</span>`;
    }
    if(state.status === 'done'){
      return `<span class="pill">${esc(label)}: ${count} · ${elapsed} ms</span>`;
    }
    return `<span class="pill loading">${esc(label)}: buscando…</span>`;
  }).join('');
}

function updateOverallStatus(){
  if(!activeStoreKeys.length){
    statusEl.textContent = 'Listo para buscar.';
    return;
  }
  const finished = activeStoreKeys.filter(key => isStoreFinished(storeStates.get(key))).length;
  const suffix = finished < activeStoreKeys.length ? ` · ${finished}/${activeStoreKeys.length} tiendas listas` : '';
  statusEl.textContent = `${visibleRows.length} publicaciones visibles · ${rows.length} obtenidas${suffix}`;
}

function rebuildRows(){
  rows = activeStoreKeys.flatMap(key => storeRows.get(key) || []);
  fillSelect(storeFilter, unique('store'));
  fillSelect(currencyFilter, unique('currency'));
  fillSelect(conditionFilter, unique('condition'));
  filters.classList.remove('hidden');
  renderStoreStates();
  render();
}

function applyStorePayload(key, data, {fromSnapshot=false}={}){
  storeRows.set(key, data.results || []);
  const info = data.store || {};
  const label = info.store || STORE_LABELS[key] || key;

  if(data.bridge_pending && !(data.results || []).length){
    storeStates.set(key, {
      status: 'bridge-pending',
      label,
      count: 0,
      elapsed_ms: 0,
      age_seconds: 0,
      bridge: true,
      error: null,
    });
  }else if(data.stale){
    storeStates.set(key, {
      status: fromSnapshot ? 'refreshing' : 'stale-error',
      label,
      count: (data.results || []).length,
      elapsed_ms: info.elapsed_ms || 0,
      age_seconds: data.bridge_age_seconds ?? data.age_seconds ?? 0,
      bridge: !!data.bridge,
      error: info.error || null,
    });
  }else if(data.cached && data.fresh){
    storeStates.set(key, {
      status: 'cached',
      label,
      count: (data.results || []).length,
      elapsed_ms: info.elapsed_ms || 0,
      age_seconds: data.bridge_age_seconds ?? data.age_seconds ?? 0,
      bridge: !!data.bridge,
      error: null,
    });
  }else if(info.error){
    storeStates.set(key, {
      status: 'error',
      label,
      count: 0,
      elapsed_ms: info.elapsed_ms || 0,
      age_seconds: data.bridge_age_seconds ?? data.age_seconds ?? 0,
      bridge: !!data.bridge,
      error: info.error,
    });
  }else{
    storeStates.set(key, {
      status: 'done',
      label,
      count: (data.results || []).length,
      elapsed_ms: info.elapsed_ms || 0,
      age_seconds: data.bridge_age_seconds ?? data.age_seconds ?? 0,
      bridge: !!data.bridge,
      error: null,
    });
  }

  rebuildRows();
}

async function fetchCacheSnapshot(query, stores, generation){
  const params = new URLSearchParams({q:query, stores:stores.join(',')});
  try{
    const response = await fetch(`/api/search/cache/?${params}`);
    if(!response.ok) return new Set();
    const data = await response.json();
    if(generation !== searchGeneration) return new Set();

    const freshKeys = new Set();
    for(const snapshot of (data.stores || [])){
      const key = snapshot.store_key;
      if(!stores.includes(key)) continue;
      applyStorePayload(key, snapshot, {fromSnapshot:true});
      if(snapshot.fresh) freshKeys.add(key);
    }
    return freshKeys;
  }catch(_err){
    return new Set();
  }
}

async function fetchOneStore(query, key, generation){
  const params = new URLSearchParams({q:query, store:key});
  const controller = new AbortController();
  const timeoutId = setTimeout(()=>controller.abort(), 90000);
  try{
    const response = await fetch(`/api/search/store/?${params}`, {signal:controller.signal});
    const data = await response.json();
    if(generation !== searchGeneration) return;
    if(!response.ok) throw new Error(data.error || 'Error');
    applyStorePayload(key, data);
  }catch(err){
    if(generation !== searchGeneration) return;
    const previous = storeStates.get(key);
    if(previous?.status === 'refreshing' && (storeRows.get(key) || []).length){
      storeStates.set(key, {...previous, status:'stale-error', error:err.message});
    }else{
      storeStates.set(key, {
        status:'error',
        label: STORE_LABELS[key] || key,
        count:0,
        elapsed_ms:0,
        age_seconds:0,
        error:err.message,
      });
    }
    renderStoreStates();
    updateOverallStatus();
  }finally{
    clearTimeout(timeoutId);
  }
}

form.addEventListener('submit', async e=>{
  e.preventDefault();
  closeAutocomplete();
  const query=q.value.trim();
  if(!query)return;
  const stores=selectedStores();
  if(!stores.length){statusEl.textContent='Seleccioná al menos una tienda.';return}

  searchGeneration += 1;
  const generation = searchGeneration;
  activeStoreKeys = stores;
  storeRows = new Map();
  storeStates = new Map(stores.map(key => [key, {status:'loading', label:STORE_LABELS[key] || key, count:0}]));
  rows = [];
  visibleRows = [];
  currentPageRows = [];
  currentPage = 1;

  filters.classList.remove('hidden');
  table.classList.toggle('hidden', currentView !== 'table');
  cardsGrid.classList.toggle('hidden', currentView !== 'cards');
  renderStoreStates();
  render();

  // 1) Show whatever we already know immediately (persistent local cache).
  // 2) Refresh only missing/stale stores. Each store finishes independently,
  //    so StarCityGames/Workshop can appear while slower shops keep working.
  const freshKeys = await fetchCacheSnapshot(query, stores, generation);
  if(generation !== searchGeneration) return;

  const toRefresh = stores.filter(key => !freshKeys.has(key));
  await Promise.allSettled(toRefresh.map(key => fetchOneStore(query, key, generation)));
});

setView(currentView);
