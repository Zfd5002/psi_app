(function(){
  const cfgEl = document.getElementById('dataFormConfig');
  if (!cfgEl) return;
  let cfg = {};
  try { cfg = JSON.parse(cfgEl.textContent || '{}'); } catch (e) { cfg = {}; }

  async function initDataForm(){
    const form = document.getElementById('dataForm');
    if (!form) return;

    const registry = await fetch('/api/registry').then(r=>r.json());

    const domainSel = document.getElementById('domainSel');
    const dataTypeSel = document.getElementById('dataTypeSel');
    const methodSel = document.getElementById('methodSel');
    const programSel = document.getElementById('programSel');
    const moleculeSel = document.getElementById('moleculeSel');
    const batchSel = document.getElementById('batchSel');
    const paramsFields = document.getElementById('paramsFields');
    const resultsFields = document.getElementById('resultsFields');
    const paramsJson = document.getElementById('paramsJson');
    const resultsJson = document.getElementById('resultsJson');
    const batchRequirementHint = document.getElementById('batchRequirementHint');

    const schemas = registry.data_schemas || {};
    const legacySchemas = registry.legacy_data_schemas || {};
    const domainDefs = registry.domains_ordered || [];
    const dataTypesByDomain = registry.data_types_by_domain || {};
    const dataTypeMeta = registry.data_type_meta || {};

    const requiringBatch = new Set(registry.data_types_requiring_batch || []);
    const legacyRequiringBatch = new Set(registry.legacy_data_types_requiring_batch || []);
    const legacyProgramLevel = new Set(registry.legacy_program_level_data_types || []);

    const preDomain = String(cfg.preDomain || '');
    const preDt = String(cfg.preDt || '');
    const preM = String(cfg.preM || '');
    let suppressScopeSync = false;
    const moleculeAll = moleculeSel ? Array.from(moleculeSel.options).map((optNode) => ({
      value: String(optNode.value || ''),
      label: String(optNode.textContent || ''),
      programId: String(optNode.dataset.programId || ''),
    })) : [];
    const batchAll = batchSel ? Array.from(batchSel.options).map((optNode) => ({
      value: String(optNode.value || ''),
      label: String(optNode.textContent || ''),
      moleculeId: String(optNode.dataset.moleculeId || ''),
      programId: String(optNode.dataset.programId || ''),
    })) : [];

    function clear(el){ while(el.firstChild) el.removeChild(el.firstChild); }
    function opt(sel, value, label){
      const o = document.createElement('option');
      o.value = value;
      o.textContent = label;
      sel.appendChild(o);
      return o;
    }

    function repopulateMoleculeOptions(selectedProgram, selectedMolecule){
      if(!moleculeSel) return '';
      clear(moleculeSel);
      opt(moleculeSel, '', '(none)');
      const allowed = moleculeAll.filter((row) => !selectedProgram || row.programId === selectedProgram);
      let resolved = '';
      allowed.forEach((row) => {
        const node = opt(moleculeSel, row.value, row.label);
        if (row.programId) node.dataset.programId = row.programId;
        if (selectedMolecule && row.value === selectedMolecule) {
          resolved = row.value;
        }
      });
      moleculeSel.value = resolved;
      return resolved;
    }

    function repopulateBatchOptions(selectedProgram, selectedMolecule, selectedBatch){
      if(!batchSel) return '';
      clear(batchSel);
      opt(batchSel, '', '(none)');
      const allowed = batchAll.filter((row) => {
        if (selectedMolecule) return row.moleculeId === selectedMolecule;
        if (selectedProgram) return row.programId === selectedProgram;
        return true;
      });
      let resolved = '';
      allowed.forEach((row) => {
        const node = opt(batchSel, row.value, row.label);
        if (row.moleculeId) node.dataset.moleculeId = row.moleculeId;
        if (row.programId) node.dataset.programId = row.programId;
        if (selectedBatch && row.value === selectedBatch) {
          resolved = row.value;
        }
      });
      batchSel.value = resolved;
      return resolved;
    }

    function syncScope({ trigger = '' } = {}){
      if(!programSel || !moleculeSel || !batchSel || suppressScopeSync) return;
      suppressScopeSync = true;
      let selectedProgram = String(programSel.value || '');
      let selectedMolecule = String(moleculeSel.value || '');
      let selectedBatch = String(batchSel.value || '');

      if (trigger === 'batch' && selectedBatch) {
        const row = batchAll.find((x) => x.value === selectedBatch);
        if (row) {
          selectedMolecule = row.moleculeId || selectedMolecule;
          selectedProgram = row.programId || selectedProgram;
        }
      } else if (trigger === 'molecule' && selectedMolecule) {
        const row = moleculeAll.find((x) => x.value === selectedMolecule);
        if (row && row.programId) selectedProgram = row.programId;
      }

      if (selectedProgram) programSel.value = selectedProgram;
      selectedMolecule = repopulateMoleculeOptions(selectedProgram, selectedMolecule);
      selectedBatch = repopulateBatchOptions(selectedProgram, selectedMolecule, selectedBatch);

      if (selectedMolecule && !selectedProgram) {
        const row = moleculeAll.find((x) => x.value === selectedMolecule);
        if (row && row.programId) {
          selectedProgram = row.programId;
          programSel.value = selectedProgram;
          selectedMolecule = repopulateMoleculeOptions(selectedProgram, selectedMolecule);
          selectedBatch = repopulateBatchOptions(selectedProgram, selectedMolecule, selectedBatch);
        }
      }

      if (selectedBatch && !selectedMolecule) {
        const row = batchAll.find((x) => x.value === selectedBatch);
        if (row) {
          if (row.programId) {
            selectedProgram = row.programId;
            programSel.value = selectedProgram;
          }
          if (row.moleculeId) {
            selectedMolecule = row.moleculeId;
          }
          selectedMolecule = repopulateMoleculeOptions(selectedProgram, selectedMolecule);
          selectedBatch = repopulateBatchOptions(selectedProgram, selectedMolecule, selectedBatch);
        }
      }

      suppressScopeSync = false;
    }

    function getSchema(dt, m){
      if(schemas[dt] && schemas[dt][m]) return schemas[dt][m];
      if(legacySchemas[dt] && legacySchemas[dt][m]) return legacySchemas[dt][m];
      return null;
    }

    function fieldInput(def, value, sectionName){
      const wrap = document.createElement('div');
      wrap.className = 'field';
      const lab = document.createElement('label');
      lab.textContent = def.label + (def.units ? ` (${def.units})` : '') + (def.required ? ' *' : '');
      wrap.appendChild(lab);

      let el;
      if(def.type === 'textarea'){
        el = document.createElement('textarea');
        el.rows = 3;
      } else if(def.type === 'select'){
        el = document.createElement('select');
        (def.options || []).forEach(v => {
          const o = document.createElement('option');
          o.value = v;
          o.textContent = v;
          el.appendChild(o);
        });
      } else {
        el = document.createElement('input');
        el.type = def.type === 'number' ? 'number' : (def.type === 'date' ? 'date' : 'text');
        if(def.type === 'number') el.step = 'any';
      }

      el.dataset.key = def.key;
      el.dataset.section = sectionName;
      el.value = value == null ? '' : String(value);
      if(def.required) el.required = true;

      if(def.help){
        const help = document.createElement('div');
        help.className = 'muted';
        help.style.fontSize = '0.85em';
        help.textContent = def.help;
        wrap.appendChild(help);
      }

      wrap.appendChild(el);
      return wrap;
    }

    function renderFields(container, defs, existingObj, sectionName){
      clear(container);
      if(!defs || defs.length === 0){
        const p = document.createElement('div');
        p.className = 'muted';
        p.textContent = '(No structured fields for this selection)';
        container.appendChild(p);
        return;
      }
      defs.forEach(def => {
        const val = existingObj ? existingObj[def.key] : '';
        container.appendChild(fieldInput(def, val, sectionName));
      });
    }

    function enforceBatchRequirement(){
      const dt = dataTypeSel.value;
      let requires = false;
      if(requiringBatch.has(dt) || legacyRequiringBatch.has(dt)){
        requires = true;
      } else if(legacyProgramLevel.has(dt)){
        requires = false;
      } else {
        const meta = dataTypeMeta[dt];
        requires = !!(meta && meta.requires_batch);
      }
      batchSel.required = requires;
      if(batchRequirementHint){
        batchRequirementHint.textContent = requires
          ? 'This data type is batch-scoped in PSI. Select a Batch before saving.'
          : 'Batch is optional for this data type.';
      }
    }

    function renderSchema(){
      enforceBatchRequirement();
      let pObj = {};
      let rObj = {};
      try{ pObj = JSON.parse(paramsJson.value || '{}'); }catch(e){}
      try{ rObj = JSON.parse(resultsJson.value || '{}'); }catch(e){}
      const dt = dataTypeSel.value;
      const m = methodSel.value;
      const s = getSchema(dt, m);

      if(!s){
        clear(paramsFields);
        clear(resultsFields);

        const pWrap = document.createElement('div');
        pWrap.className = 'field';
        const pLab = document.createElement('label');
        pLab.textContent = 'Parameters JSON (raw)';
        const pTa = document.createElement('textarea');
        pTa.rows = 10;
        pTa.dataset.raw = 'params';
        pTa.value = paramsJson.value || '{}';
        pWrap.appendChild(pLab);
        pWrap.appendChild(pTa);
        paramsFields.appendChild(pWrap);

        const rWrap = document.createElement('div');
        rWrap.className = 'field';
        const rLab = document.createElement('label');
        rLab.textContent = 'Results JSON (raw)';
        const rTa = document.createElement('textarea');
        rTa.rows = 10;
        rTa.dataset.raw = 'results';
        rTa.value = resultsJson.value || '{}';
        rWrap.appendChild(rLab);
        rWrap.appendChild(rTa);
        resultsFields.appendChild(rWrap);
        return;
      }

      renderFields(paramsFields, s.params_fields || [], pObj, 'params');
      renderFields(resultsFields, s.results_fields || [], rObj, 'results');
    }

    function applyDefaultsToResults(){
      const paramsInputs = Array.from(paramsFields.querySelectorAll('[data-key][data-section="params"]'));
      const resultInputs = Array.from(resultsFields.querySelectorAll('[data-key][data-section="results"]'));
      const paramByKey = {};
      paramsInputs.forEach((el) => {
        const k = String(el.dataset.key || '').trim();
        const v = String(el.value || '').trim();
        if (k && v) paramByKey[k] = v;
      });
      const aliases = {
        unit: ['units', 'result_unit', 'measurement_unit'],
        units: ['unit', 'result_unit', 'measurement_unit'],
        assay_group: ['assay', 'assay_type'],
        condition: ['conditions'],
        matrix: ['sample_matrix'],
      };
      resultInputs.forEach((el) => {
        const current = String(el.value || '').trim();
        if (current) return;
        const key = String(el.dataset.key || '').trim();
        if (!key) return;
        if (paramByKey[key]) {
          el.value = paramByKey[key];
          return;
        }
        const opts = aliases[key] || [];
        for (const src of opts) {
          if (paramByKey[src]) {
            el.value = paramByKey[src];
            return;
          }
        }
      });
    }

    function collect(container){
      const rawParams = container.querySelector('textarea[data-raw="params"]');
      const rawResults = container.querySelector('textarea[data-raw="results"]');
      if(rawParams || rawResults) return null;

      const obj = {};
      container.querySelectorAll('[data-key]').forEach(el=>{
        const k = el.dataset.key;
        const v = el.value;
        if(v !== '' && v != null) obj[k] = v;
      });
      return obj;
    }

    function populateDomains(){
      clear(domainSel);
      domainDefs.forEach(d => {
        opt(domainSel, d.key, `${d.key} — ${d.label}`);
      });

      if(preDomain && !domainDefs.some(d => d.key === preDomain) && !domainDefs.some(d => d.key === (registry.domain_aliases ? registry.domain_aliases[preDomain] : ''))){
        opt(domainSel, preDomain, `(legacy) ${preDomain}`);
      }

      const canonicalForPre = (registry.domain_aliases && registry.domain_aliases[preDomain]) ? registry.domain_aliases[preDomain] : preDomain;
      if(canonicalForPre && Array.from(domainSel.options).some(o => o.value === canonicalForPre)){
        domainSel.value = canonicalForPre;
      } else if(preDomain && Array.from(domainSel.options).some(o => o.value === preDomain)){
        domainSel.value = preDomain;
      } else {
        domainSel.selectedIndex = 0;
      }
    }

    function populateDataTypes(){
      clear(dataTypeSel);
      const dom = domainSel.value;
      const dts = dataTypesByDomain[dom] || [];
      dts.forEach(dt => {
        const meta = dataTypeMeta[dt] || {};
        opt(dataTypeSel, dt, `${dt} — ${meta.label || dt}`);
      });

      if(preDt && !Array.from(dataTypeSel.options).some(o => o.value === preDt)){
        opt(dataTypeSel, preDt, `(legacy) ${preDt}`);
      }

      if(preDt && Array.from(dataTypeSel.options).some(o => o.value === preDt)){
        dataTypeSel.value = preDt;
      } else if(dts.length){
        dataTypeSel.value = dts[0];
      } else if(dataTypeSel.options.length){
        dataTypeSel.selectedIndex = 0;
      }

      populateMethods();
    }

    function populateMethods(){
      clear(methodSel);
      const dt = dataTypeSel.value;

      let methods = [];
      if(schemas[dt]) methods = Object.keys(schemas[dt]).sort();
      else if(legacySchemas[dt]) methods = Object.keys(legacySchemas[dt]).sort();

      methods.forEach(m => opt(methodSel, m, m));

      if(preM && methods.includes(preM)){
        methodSel.value = preM;
      } else if(methodSel.options.length){
        methodSel.selectedIndex = 0;
      }

      renderSchema();
    }

    populateDomains();
    populateDataTypes();
    syncScope();

    if (programSel) programSel.addEventListener('change', () => syncScope({ trigger: 'program' }));
    if (moleculeSel) moleculeSel.addEventListener('change', () => syncScope({ trigger: 'molecule' }));
    if (batchSel) batchSel.addEventListener('change', () => syncScope({ trigger: 'batch' }));
    domainSel.addEventListener('change', populateDataTypes);
    dataTypeSel.addEventListener('change', populateMethods);
    methodSel.addEventListener('change', renderSchema);
    const applyBtn = document.getElementById('applyDefaultsBtn');
    if (applyBtn) applyBtn.addEventListener('click', applyDefaultsToResults);

    form.addEventListener('submit', ()=>{
      const rawP = paramsFields.querySelector('textarea[data-raw="params"]');
      const rawR = resultsFields.querySelector('textarea[data-raw="results"]');
      if(rawP || rawR){
        paramsJson.value = (rawP && rawP.value) ? rawP.value : (paramsJson.value || '{}');
        resultsJson.value = (rawR && rawR.value) ? rawR.value : (resultsJson.value || '{}');
        return;
      }

      const p = collect(paramsFields) || {};
      const r = collect(resultsFields) || {};
      paramsJson.value = JSON.stringify(p);
      resultsJson.value = JSON.stringify(r);
    });
  }

  initDataForm();
})();
