(function(){
  const cfgEl = document.getElementById('evidenceFormConfig');
  if (!cfgEl) return;
  let cfg = {};
  try { cfg = JSON.parse(cfgEl.textContent || '{}'); } catch (e) { cfg = {}; }

  function opt(el, value, label){ const o=document.createElement('option'); o.value=value; o.textContent=label; el.appendChild(o); }
  function clear(el){ while(el.firstChild) el.removeChild(el.firstChild); }

  async function initEvidenceForm(){
    const form = document.getElementById('evForm');
    if (!form) return;

    const domainMap = cfg.domainMap || {};
    const preType = String(cfg.preType || '');
    const citedIds = Array.isArray(cfg.citedIds) ? cfg.citedIds : [];

    const domainSel = document.getElementById('evDomain');
    const typeSel = document.getElementById('evType');
    const programSel = document.getElementById('evProgram');
    const molSel = document.getElementById('evMolecule');
    const batchSel = document.getElementById('evBatch');
    const drList = document.getElementById('drList');
    const drSearch = document.getElementById('drSearch');
    const citationIds = document.getElementById('citationIds');

    const inlineToggle = document.getElementById('inlineToggle');
    const inlineBox = document.getElementById('inlineBox');
    const inlineDataType = document.getElementById('inlineDataType');
    const inlineMethod = document.getElementById('inlineMethod');
    const inlineParams = document.getElementById('inlineParams');
    const inlineResults = document.getElementById('inlineResults');
    const inlineParamsJson = document.getElementById('inlineParamsJson');
    const inlineResultsJson = document.getElementById('inlineResultsJson');
    const drDomain = document.getElementById('drDomain');

    let registry = null;
    let allowed = null;
    let currentRecords = [];

    function populateTypes(){
      clear(typeSel);
      const d = domainSel.value;
      (domainMap[d]||[]).slice().sort().forEach(t=>opt(typeSel, t, t));
      if(preType && (domainMap[d]||[]).includes(preType)) typeSel.value = preType;
    }

    async function loadRegistry(){
      if(!registry) registry = await fetch('/api/registry').then(r=>r.json());
      return registry;
    }

    async function refreshAllowed(){
      const t = typeSel.value;
      if(!t){ allowed = null; return; }
      allowed = await fetch(`/api/evidence_allowed_sources?evidence_type=${encodeURIComponent(t)}`).then(r=>r.json());
    }

    function pairOk(rec){
      if(!allowed) return true;
      const dts = allowed.allowed_data_types || [];
      if(dts.length && !dts.includes(rec.data_type)) return false;
      const by = allowed.allowed_methods_by_data_type || {};
      const ms = by[rec.data_type] || [];
      return ms.length ? ms.includes(rec.method) : true;
    }

    function syncCitationIds(){
      const ids=[];
      drList.querySelectorAll('input[type="checkbox"]').forEach(cb=>{ if(cb.checked) ids.push(cb.value); });
      citationIds.value = ids.join(',');
    }

    function renderRecords(){
      clear(drList);
      const q = (drSearch.value||'').toLowerCase();
      const filtered = currentRecords
        .filter(r=>pairOk(r))
        .filter(r=>!q || (`${r.title} ${r.data_type} ${r.method}`.toLowerCase().includes(q)));

      if(filtered.length===0){
        const div=document.createElement('div'); div.className='muted'; div.textContent='No eligible Data Records in scope.'; drList.appendChild(div);
        return;
      }

      const pre = new Set(citedIds);
      filtered.forEach(r=>{
        const row=document.createElement('div');
        row.style.display='flex'; row.style.gap='8px'; row.style.alignItems='center'; row.style.marginBottom='6px';
        const cb=document.createElement('input'); cb.type='checkbox'; cb.value=r.id;
        if(pre.has(r.id)) cb.checked = true;
        cb.addEventListener('change', syncCitationIds);
        const label=document.createElement('label'); label.style.cursor='pointer';
        label.textContent = `#${r.id} — ${r.title} (${r.data_type}/${r.method})`;
        row.appendChild(cb); row.appendChild(label);
        drList.appendChild(row);
      });

      syncCitationIds();
    }

    async function fetchRecords(){
      const pid = programSel.value;
      const mid = molSel.value;
      const bid = batchSel.value;
      const params = new URLSearchParams({program_id:pid});
      if(mid) params.set('molecule_id', mid);
      if(bid) params.set('batch_id', bid);
      const payload = await fetch(`/api/data_records?${params.toString()}`).then(r=>r.json());
      currentRecords = payload.records || [];
      renderRecords();
    }

    function fieldInput(def, value){
      const wrap = document.createElement('div'); wrap.className='field';
      const lab = document.createElement('label');
      lab.textContent = def.label + (def.units?` (${def.units})`:'') + (def.required?' *':'');
      wrap.appendChild(lab);
      let inp;
      if(def.type==='select'){
        inp=document.createElement('select'); (def.options||[]).forEach(v=>opt(inp,v,v));
        if(value!=null && value!=='') inp.value=value;
      } else if(def.type==='number'){
        inp=document.createElement('input'); inp.type='number'; if(def.step) inp.step=def.step;
        if(value!=null && value!=='') inp.value=value;
      } else if(def.type==='date'){
        inp=document.createElement('input'); inp.type='date'; if(value) inp.value=value;
      } else {
        inp=document.createElement('input'); inp.type='text'; if(value!=null && value!=='') inp.value=value;
      }
      inp.dataset.key = def.key;
      if(def.required) inp.required = true;
      wrap.appendChild(inp);
      if(def.help){ const h=document.createElement('div'); h.className='help'; h.textContent=def.help; wrap.appendChild(h); }
      return wrap;
    }

    function renderInlineSchema(){
      if(!registry) return;
      clear(inlineParams); clear(inlineResults);
      const dt = inlineDataType.value; const m = inlineMethod.value;
      const schema = (registry.data_schemas||{})[dt] ? (registry.data_schemas||{})[dt][m] : null;
      (schema?.params_fields||[]).forEach(def=> inlineParams.appendChild(fieldInput(def,'')));
      (schema?.results_fields||[]).forEach(def=> inlineResults.appendChild(fieldInput(def,'')));
    }

    function collect(container){
      const obj={};
      container.querySelectorAll('[data-key]').forEach(el=>{ if(el.value!=='' && el.value!=null) obj[el.dataset.key]=el.value; });
      return obj;
    }

    async function initInline(){
      await loadRegistry();
      clear(inlineDataType);
      Object.keys(registry.data_schemas||{}).slice().sort().forEach(dt=>opt(inlineDataType, dt, dt));

      inlineDataType.addEventListener('change', ()=>{
        clear(inlineMethod);
        Object.keys((registry.data_schemas||{})[inlineDataType.value]||{}).slice().sort().forEach(m=>opt(inlineMethod, m, m));
        renderInlineSchema();
      });
      inlineMethod.addEventListener('change', renderInlineSchema);

      inlineDataType.dispatchEvent(new Event('change'));
    }

    populateTypes();
    loadRegistry().then(initInline);

    domainSel.addEventListener('change', async ()=>{
      populateTypes();
      await refreshAllowed();
      await fetchRecords();
      drDomain.value = domainSel.value;
    });

    typeSel.addEventListener('change', async ()=>{
      await refreshAllowed();
      await fetchRecords();
    });

    [programSel, molSel, batchSel].forEach(sel=> sel.addEventListener('change', fetchRecords));
    drSearch.addEventListener('input', renderRecords);

    inlineToggle.addEventListener('change', ()=>{ inlineBox.style.display = inlineToggle.checked ? 'block' : 'none'; });

    form.addEventListener('submit', ()=>{
      syncCitationIds();
      inlineParamsJson.value = JSON.stringify(collect(inlineParams));
      inlineResultsJson.value = JSON.stringify(collect(inlineResults));
    });

    drDomain.value = domainSel.value;
    refreshAllowed().then(fetchRecords);
  }

  initEvidenceForm();
})();
