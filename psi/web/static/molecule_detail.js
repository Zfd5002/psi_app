
  const configEl = document.getElementById("molecule-detail-config");
  let config = {};
  if (configEl) {
    try { config = JSON.parse(configEl.textContent || "{}"); } catch (e) { config = {}; }
  }
  const moleculeId = String(config.molecule_id || "");

(function(){
    // Persist open/closed state for key <details> panels (molecule-scoped).
    var moleculeId = String(config.molecule_id || "");
    function storagePrefix(){ return "psi:m:" + moleculeId + ":details:"; }
    function storageKey(detailsKey){ return storagePrefix() + detailsKey; }

    function getDetailsKey(el){
      if (!el) return null;
      var k = el.getAttribute("data-psi-details-key");
      if (k) return k;
      return el.id || null;
    }

    function getStoredState(detailsKey){
      try { return window.localStorage.getItem(storageKey(detailsKey)); } catch(e) { return null; }
    }

    function setStoredState(detailsKey, isOpen){
      try { window.localStorage.setItem(storageKey(detailsKey), isOpen ? "open" : "closed"); } catch(e) {}
    }

    function migrateLegacyKey(detailsKey, legacyKey){
      // Back-compat: migrate old global key (pre v1.2.3d) to molecule-scoped key.
      if (getStoredState(detailsKey) != null) return;
      var v = null;
      try { v = window.localStorage.getItem(legacyKey); } catch(e) {}
      if (v === "open" || v === "closed") {
        setStoredState(detailsKey, v === "open");
      }
    }

    // Migrate known legacy keys.
    migrateLegacyKey("property_run_details", "psi.details.property_run_details");
    migrateLegacyKey("computed_log_details", "psi.details.computed_log_details");

    function restoreDetails(el){
      var k = getDetailsKey(el);
      if (!k) return;
      var v = getStoredState(k);
      if (v === "open") el.open = true;
      else if (v === "closed") el.open = false;
      // else: keep default as authored (conservative defaults should be collapsed)
      el.addEventListener("toggle", function(){
        setStoredState(k, el.open);
      });
    }

    // Restore for all opt-in <details> on this page.
    var all = document.querySelectorAll("details[data-psi-details-key]");
    for (var i=0;i<all.length;i++) restoreDetails(all[i]);

    // Deep link behavior: open log when anchored.
    if (window.location.hash === "#computed_log" || window.location.hash === "#computed_log_details") {
      var d = document.getElementById("computed_log_details");
      if (d) { d.open = true; setStoredState(getDetailsKey(d) || "computed_log_details", true); }
    }

    // Expand/collapse all batch panels.
    function setAllBatches(open){
      var panels = document.querySelectorAll(".batch-panels details.batch-panel[data-psi-details-key]");
      for (var j=0;j<panels.length;j++) {
        panels[j].open = !!open;
        var kk = getDetailsKey(panels[j]);
        if (kk) setStoredState(kk, !!open);
      }
    }
    var ex = document.getElementById("batch_expand_all");
    var co = document.getElementById("batch_collapse_all");
    if (ex) ex.addEventListener("click", function(){ setAllBatches(true); });
    if (co) co.addEventListener("click", function(){ setAllBatches(false); });

    // QC mode selector (affects headline metric selection; persisted per molecule).
    function qcStorageKey(){ return "psi.molecule." + String(moleculeId) + ".qc_mode"; }
    function getQcStored(){ try { return window.localStorage.getItem(qcStorageKey()); } catch(e) { return null; } }
    function setQcStored(v){ try { window.localStorage.setItem(qcStorageKey(), v); } catch(e) {} }

    var qcSel = document.getElementById("qc_mode_select");
    if (qcSel) {
      // If URL lacks qc_mode but storage has one, apply it (one-time redirect).
      try {
        var u0 = new URL(window.location.href);
        var urlMode = (u0.searchParams.get("qc_mode") || "").trim();
        var stored = (getQcStored() || "").trim();
        if (!urlMode && stored && stored !== "all") {
          u0.searchParams.set("qc_mode", stored);
          window.location.replace(u0.toString());
          return;
        }
      } catch(e) {}

      qcSel.addEventListener("change", function(){
        var v = String(qcSel.value || "all").trim();
        if (v !== "all" && v !== "model_safe" && v !== "approved") v = "all";
        setQcStored(v);
        try {
          var u = new URL(window.location.href);
          if (v === "all") u.searchParams.delete("qc_mode");
          else u.searchParams.set("qc_mode", v);
          if (!u.hash) u.hash = "#batches";
          window.location.assign(u.toString());
        } catch(e) {
          // Fallback: simple reload.
          window.location.reload();
        }
      });
    }
  })();

(function () {
    var root = document.querySelector(".molecule-header");
    var page = document.querySelector(".molecule-page");
    if (!root && !page) return;
    var btnSci = document.getElementById("mh_view_scientist");
    var btnGov = document.getElementById("mh_view_governance");
    if (!btnSci || !btnGov) return;
    var storageKey = "psi.molecule.detail.view_mode";
    function setMode(mode) {
      var m = (mode === "governance") ? "governance" : "scientist";
      if (root) root.setAttribute("data-view-mode", m);
      if (page) page.setAttribute("data-view-mode", m);
      btnSci.classList.toggle("primary", m === "scientist");
      btnGov.classList.toggle("primary", m === "governance");
      try { localStorage.setItem(storageKey, m); } catch (e) {}
    }
    btnSci.addEventListener("click", function () { setMode("scientist"); });
    btnGov.addEventListener("click", function () { setMode("governance"); });
    var initial = "scientist";
    try { initial = localStorage.getItem(storageKey) || "scientist"; } catch (e) {}
    setMode(initial);
  })();

(function(){
  const trendData = config.molecule_trends || { metric_keys: [], series: {} };
  function renderTrendSparkline(svg, points){
    if(!svg) return;
    while(svg.firstChild) svg.removeChild(svg.firstChild);
    if(!Array.isArray(points) || points.length === 0){
      return;
    }
    const values = points.map(p => Number(p.value)).filter(v => Number.isFinite(v));
    if(values.length === 0) return;
    const min = Math.min.apply(null, values);
    const max = Math.max.apply(null, values);
    const span = (max - min) || 1;
    const w = 220, h = 48;
    const xStep = values.length > 1 ? (w - 8) / (values.length - 1) : 1;
    const coords = values.map((v, i) => {
      const x = 4 + (i * xStep);
      const y = 44 - ((v - min) / span) * 40;
      return `${x},${y}`;
    }).join(" ");
    const ns = "http://www.w3.org/2000/svg";
    const poly = document.createElementNS(ns, "polyline");
    poly.setAttribute("points", coords);
    poly.setAttribute("fill", "none");
    poly.setAttribute("stroke", "#2c7be5");
    poly.setAttribute("stroke-width", "2");
    svg.appendChild(poly);
  }
  document.querySelectorAll(".trend-sparkline").forEach((svg) => {
    const mk = String(svg.getAttribute("data-trend-key") || "");
    const pts = trendData && trendData.series ? trendData.series[mk] : [];
    renderTrendSparkline(svg, pts);
  });

  const highlightSelections = new Map();
  const MANUAL_HIGHLIGHT_KEY = "__manual__";

  function viewerSelectionKey(viewerEl){
    return String(viewerEl && viewerEl.dataset && viewerEl.dataset.componentId ? viewerEl.dataset.componentId : "");
  }

  function dispatchViewerSelection(viewerEl, s, e){
    try{
      const moleculeId = viewerEl.dataset.moleculeId;
      const componentId = viewerEl.dataset.componentId;
      window.dispatchEvent(new CustomEvent('psi:viewer-selection', {detail:{moleculeId, componentId, start_idx:s, end_idx:e}}));
    }catch(e){}
  }

  function getComponentHighlightBuckets(viewerEl, create){
    const key = viewerSelectionKey(viewerEl);
    if(!key) return null;
    let buckets = highlightSelections.get(key);
    if(!buckets && create){
      buckets = new Map();
      highlightSelections.set(key, buckets);
    }
    return buckets || null;
  }

  function getHighlightedResiduesSet(viewerEl, featureKey, create){
    const buckets = getComponentHighlightBuckets(viewerEl, create);
    if(!buckets) return null;
    const fk = String(featureKey || MANUAL_HIGHLIGHT_KEY);
    let set = buckets.get(fk);
    if(!set && create){
      set = new Set();
      buckets.set(fk, set);
    }
    return set || null;
  }

  function residueHighlightedInAnyBucket(viewerEl, residueIndex){
    const buckets = getComponentHighlightBuckets(viewerEl, false);
    if(!buckets) return false;
    for(const set of buckets.values()){
      if(set && set.has(residueIndex)) return true;
    }
    return false;
  }

  function renderResidueHighlights(viewerEl){
    const residues = viewerEl.querySelectorAll('.residue');
    residues.forEach((el) => {
      const idx = parseInt(el.dataset.pos || '-1');
      const on = !!(Number.isFinite(idx) && residueHighlightedInAnyBucket(viewerEl, idx));
      el.classList.toggle('selected', on);
    });
  }

  function clearResidueHighlights(viewerEl){
    const buckets = getComponentHighlightBuckets(viewerEl, false);
    if(buckets){
      for(const set of buckets.values()){
        if(set) set.clear();
      }
    }
    renderResidueHighlights(viewerEl);
  }

  function highlightRange(viewerEl, startIdx, endIdx){
    const set = getHighlightedResiduesSet(viewerEl, MANUAL_HIGHLIGHT_KEY, true);
    if(!set) return;
    const s = Math.max(0, parseInt(startIdx||0));
    const e = Math.max(s, parseInt(endIdx||0));
    set.clear();
    for(let i=s; i<e; i++) set.add(i);
    renderResidueHighlights(viewerEl);
    dispatchViewerSelection(viewerEl, s, e);
  }

  function getComponentAnnotationGroups(compId){
    const compEl = document.querySelector(`.annot-comp[data-component-id="${compId}"]`);
    if(!compEl) return [];
    if(Array.isArray(compEl._psiAnnotationGroups)) return compEl._psiAnnotationGroups;
    let groups = [];
    try{
      const parsed = JSON.parse(compEl.dataset.annotationsGroups || '[]');
      if(Array.isArray(parsed)) groups = parsed;
    }catch(e){}
    compEl._psiAnnotationGroups = groups;
    return groups;
  }

  function highlightAllByFeatureName(viewerEl, featureName){
    const compId = String(viewerEl.dataset.componentId || '');
    const fname = String(featureName || '').trim();
    if(!compId || !fname) return;
    const set = getHighlightedResiduesSet(viewerEl, fname, true);
    if(!set) return;
    set.clear();
    let minStart = null;
    let maxEnd = null;
    const groups = getComponentAnnotationGroups(compId);
    groups.forEach((g) => {
      const items = Array.isArray(g && g.items) ? g.items : [];
      items.forEach((feat) => {
        if(String((feat && feat.name) || '') !== fname) return;
        const spans = Array.isArray(feat && feat.spans) ? feat.spans : [];
        spans.forEach((sp) => {
          const s = Math.max(0, parseInt((sp && sp.start) || 0));
          const e = Math.max(s, parseInt((sp && sp.end) || 0));
          if(e <= s) return;
          if(minStart === null || s < minStart) minStart = s;
          if(maxEnd === null || e > maxEnd) maxEnd = e;
          for(let i=s; i<e; i++) set.add(i);
        });
      });
    });
    renderResidueHighlights(viewerEl);
    if(minStart !== null && maxEnd !== null) dispatchViewerSelection(viewerEl, minStart, maxEnd);
  }

  function clearHighlights(componentId){
    if(componentId === undefined || componentId === null || componentId === ''){
      document.querySelectorAll('.seq-scroll.viewer-v2').forEach((viewerEl) => clearResidueHighlights(viewerEl));
      return;
    }
    const viewerEl = document.querySelector(`.seq-scroll.viewer-v2[data-component-id="${componentId}"]`);
    if(viewerEl) clearResidueHighlights(viewerEl);
  }

  function clearHighlightsForComponent(componentId){
    clearHighlights(componentId);
  }

  function clearHighlightsForComponentFeature(componentId, featureName){
    const compId = String(componentId || '');
    const fname = String(featureName || '').trim();
    if(!compId || !fname) return;
    const viewerEl = document.querySelector(`.seq-scroll.viewer-v2[data-component-id="${compId}"]`);
    if(!viewerEl) return;
    const set = getHighlightedResiduesSet(viewerEl, fname, false);
    if(set) set.clear();
    renderResidueHighlights(viewerEl);
  }

  function toggleResidue(viewerEl, residueIndex){
    const idx = parseInt(residueIndex || '-1');
    if(!Number.isFinite(idx) || idx < 0) return;
    const buckets = getComponentHighlightBuckets(viewerEl, false);
    if(!buckets) return;
    let removed = false;
    for(const set of buckets.values()){
      if(set && set.has(idx)){
        set.delete(idx);
        removed = true;
      }
    }
    if(!removed) return;
    renderResidueHighlights(viewerEl);
    dispatchViewerSelection(viewerEl, idx, idx + 1);
  }

  function charWidthPx(el){
    const probe = document.createElement('span');
    probe.textContent = 'M';
    probe.style.visibility = 'hidden';
    probe.style.position = 'absolute';
    probe.style.fontFamily = 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace';
    probe.style.fontSize = '12px';
    el.appendChild(probe);
    const w = probe.getBoundingClientRect().width || 10;
    probe.remove();
    return w;
  }

  function computeWrapCols(viewerEl){
    // Compute based on the visible viewer container width (stable), not content width.
    const w = viewerEl.clientWidth || (viewerEl.getBoundingClientRect && viewerEl.getBoundingClientRect().width) || 0;
    if(!w) return 80;

    let cw = charWidthPx(viewerEl);
    // Guard against bad measurements (can happen in hidden/just-rendered contexts)
    if(!cw || !isFinite(cw) || cw < 7) cw = 10;

    const laneLabelGutter = 64;
    const pad = 24;
    let cols = Math.floor((w - laneLabelGutter - pad) / cw);
    if(!cols || !isFinite(cols)) cols = 80;

    // Hard clamps: prevents any overflow spiral
    cols = Math.max(20, Math.min(120, cols));
    return cols;
  }

  function setWrapCols(viewerEl){
    const cols = computeWrapCols(viewerEl);
    viewerEl.style.setProperty('--wrap-cols', String(cols));
  }

  function setWrapColsAll(){
    const viewers = Array.from(document.querySelectorAll(".viewer-v2")).length
      ? Array.from(document.querySelectorAll(".viewer-v2"))
      : Array.from(document.querySelectorAll(".seq-grid")).map(g => g.closest("[data-component-id], .card, .lane, div") ).filter(Boolean);
    for(const v of viewers){
      try{
        // skip hidden blocks (width 0) and try again later
        const rect = v.getBoundingClientRect();
        if(!rect || rect.width < 10) continue;
        setWrapCols(v);
      }catch(e){}
    }
  }

  // initial + reactive recompute (important when panels/components are collapsed then expanded)
  setTimeout(setWrapColsAll, 0);
  window.addEventListener("resize", () => setTimeout(setWrapColsAll, 0));
  document.addEventListener("toggle", (e) => {
    if(e && e.target && e.target.tagName === "DETAILS") setTimeout(setWrapColsAll, 0);
  });


  function selectionInside(el){
    const sel = window.getSelection();
    if(!sel || sel.rangeCount === 0) return null;
    const range = sel.getRangeAt(0);
    const sc = range.startContainer;
    const ec = range.endContainer;
    if(!(sc instanceof Node) || !(ec instanceof Node)) return null;
    if(!el.contains(sc) && !el.contains(ec)) return null;
    return range;
  }

  function residuesFromRange(viewerEl, range){
    const seqGrid = viewerEl.querySelector('.seq-grid');
    if(!seqGrid) return {text:'', start:null, end:null};
    const residues = Array.from(seqGrid.querySelectorAll('.residue'));
    const hits = [];

    // Intersect residues directly.
    for(const r of residues){
      try{ if(range.intersectsNode(r)) hits.push(parseInt(r.dataset.pos||'0')); }catch(e){}
    }

    // If the user selected only numbering cells, map those columns back to residues.
    if(hits.length === 0){
      const nums = Array.from(viewerEl.querySelectorAll('.num-cell[data-pos]'));
      for(const n of nums){
        try{ if(range.intersectsNode(n)) hits.push(parseInt(n.dataset.pos||'0')); }catch(e){}
      }
    }
    if(hits.length === 0){
      // Fallback: filter the selected plain text for AA characters.
      const raw = String(range.toString() || '');
      const filtered = raw.toUpperCase().replace(/[^A-Z\*\-]/g, '');
      return {text:filtered, start:null, end:null};
    }
    hits.sort((a,b)=>a-b);
    const s = hits[0];
    const e = hits[hits.length-1] + 1;
    const text = hits.map(i => residues[i]?.textContent || '').join('');
    return {text, start:s, end:e};
  }

  async function copyText(text){
    const t = String(text || '');
    if(!t) return;
    try{
      if(navigator.clipboard && navigator.clipboard.writeText){
        await navigator.clipboard.writeText(t);
        return;
      }
    }catch(e){}
    // Fallback for older browsers
    const ta = document.createElement('textarea');
    ta.value = t;
    ta.style.position = 'fixed';
    ta.style.left = '-9999px';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    try{ document.execCommand('copy'); }catch(e){}
    ta.remove();
  }

  // Viewer wiring
  const viewers = Array.from(document.querySelectorAll('.seq-scroll.viewer-v2'));
  viewers.forEach((viewerEl) => {
    setWrapCols(viewerEl);
    window.addEventListener('resize', () => setWrapCols(viewerEl));

    // Manual selection => highlight residues (native selection remains untouched)
    viewerEl.addEventListener('mouseup', () => {
      const range = selectionInside(viewerEl);
      if(!range) return;
      const {start, end} = residuesFromRange(viewerEl, range);
      if(start === null || end === null) return;
      highlightRange(viewerEl, start, end);
    });

    viewerEl.addEventListener('click', (ev) => {
      const target = ev.target;
      if(!(target instanceof HTMLElement)) return;
      if(!target.classList.contains('residue')) return;
      // Avoid toggling off immediately after drag-selection text highlight.
      try{
        const sel = window.getSelection();
        if(sel && String(sel.toString() || '').length > 0) return;
      }catch(e){}
      if(!target.classList.contains('selected')) return;
      toggleResidue(viewerEl, target.dataset.pos);
    });

    // CRITICAL: copy sanitization (viewer-local).
    viewerEl.addEventListener('copy', (ev) => {
      const range = selectionInside(viewerEl);
      if(!range) return;
      const {text} = residuesFromRange(viewerEl, range);
      if(!text) return;
      try{
        ev.clipboardData.setData('text/plain', text);
        ev.preventDefault();
      }catch(e){
        // As a last resort, try async clipboard.
        ev.preventDefault();
        copyText(text);
      }
    });
  });

  // Annotations panel interactions
  document.querySelectorAll('.annot-item').forEach((row) => {
    const compId = row.dataset.componentId;
    let feat = {};
    try{ feat = JSON.parse(row.dataset.feature || '{}'); }catch(e){ feat = {}; }
    const sp = (feat.spans && feat.spans.length) ? feat.spans[0] : null;
    const viewerEl = document.querySelector(`.seq-scroll.viewer-v2[data-component-id="${compId}"]`);
    if(!viewerEl || !sp) return;

    const doHighlight = () => {
      highlightRange(viewerEl, sp.start, sp.end);
      // Scroll to the first selected residue (within the viewer block)
      const first = viewerEl.querySelector(`.residue[data-pos="${sp.start}"]`);
      if(first){
        first.scrollIntoView({block:'nearest', inline:'nearest'});
      }
    };

    row.querySelectorAll('[data-action="annot-highlight"]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        doHighlight();
      });
    });

    row.querySelectorAll('[data-action="annot-copy"]').forEach((btn) => {
      btn.addEventListener('click', async (e) => {
        e.preventDefault();
        const s = Math.max(0, parseInt(sp.start||0));
        const e2 = Math.max(s, parseInt(sp.end||0));
        const residues = Array.from(viewerEl.querySelectorAll('.residue'));
        let out = '';
        for(let i=s; i<e2 && i<residues.length; i++) out += (residues[i]?.textContent || '');
        out = out.toUpperCase().replace(/[^A-Z\*\-]/g, '');
        await copyText(out);
        doHighlight();
      });
    });
  });

  document.querySelectorAll('.annot-comp').forEach((compEl) => {
    const compId = String(compEl.dataset.componentId || '');
    if(!compId) return;
    const viewerEl = document.querySelector(`.seq-scroll.viewer-v2[data-component-id="${compId}"]`);
    if(!viewerEl) return;
    compEl.querySelectorAll('[data-action="annot-bulk-highlight"]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        highlightAllByFeatureName(viewerEl, btn.dataset.featureName || '');
      });
    });
    compEl.querySelectorAll('[data-action="annot-clear-highlights"]').forEach((btn) => {
      btn.addEventListener('click', (e) => {
        e.preventDefault();
        clearHighlights(compId);
      });
    });
  });

  document.querySelectorAll('[data-action="viewer-bulk-highlight"]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const compId = String(btn.dataset.componentId || '');
      const viewerEl = document.querySelector(`.seq-scroll.viewer-v2[data-component-id="${compId}"]`);
      if(!viewerEl) return;
      highlightAllByFeatureName(viewerEl, btn.dataset.featureName || '');
    });
  });

  document.querySelectorAll('[data-action="viewer-clear-highlights"]').forEach((btn) => {
    btn.addEventListener('click', (e) => {
      e.preventDefault();
      const compId = String(btn.dataset.componentId || '');
      const fname = String(btn.dataset.featureName || '').trim();
      if(fname) clearHighlightsForComponentFeature(compId, fname);
      else clearHighlightsForComponent(compId);
    });
  });

  // Quality-of-life: auto-submit PD-L1 mismatch select
  const mmSel = document.getElementById('pdl1_mm');
  if(mmSel){
    mmSel.addEventListener('change', () => {
      mmSel.form && mmSel.form.submit();
    });
  }

  // --- Numbering map (wrapped, block/tile layout) ---
  function esc(s){
    return (s === null || s === undefined) ? '' : String(s);
  }

  function buildTile(map, blockSize, offset){
    const tile = document.createElement('div');
    tile.className = 'nm-tile';
    tile.style.setProperty('--nm-block', String(blockSize));

    const end = Math.min(offset + blockSize, map.sequence.length);
    const count = end - offset;

    function mkRow(kind){
      const row = document.createElement('div');
      row.className = 'nm-row';
      row.style.gridTemplateColumns = `repeat(${blockSize}, var(--nm-colw))`;
      for(let j=0; j<blockSize; j++){
        const idx = offset + j;
        const cell = document.createElement('div');
        cell.className = `nm-cell ${kind}`;
        cell.dataset.col = String(j);
        cell.dataset.abs = String(idx);
        if(idx >= map.sequence.length){
          cell.classList.add('blank');
          cell.textContent = '';
        }else{
          if(kind === 'nm-seq'){
            cell.textContent = map.sequence[idx] || '';
          }else if(kind === 'nm-raw'){
            cell.textContent = String(idx + 1);
          }else if(kind === 'nm-ab'){
            const lab = map.labels_by_raw_index[idx];
            cell.textContent = lab ? String(lab) : '';
            if(!lab) cell.classList.add('blank');
          }
        }
        row.appendChild(cell);
      }
      return row;
    }

    tile.appendChild(mkRow('nm-ab'));
    tile.appendChild(mkRow('nm-raw'));
    tile.appendChild(mkRow('nm-seq'));

    // Click interaction: highlight column within tile + select residue in Viewer v2.
    tile.addEventListener('click', (ev) => {
      const target = ev.target;
      if(!(target instanceof HTMLElement)) return;
      if(!target.classList.contains('nm-cell')) return;
      const col = target.dataset.col;
      const abs = parseInt(target.dataset.abs || '-1');
      if(!Number.isFinite(abs) || abs < 0 || abs >= map.sequence.length) return;

      // Column highlight within this tile only
      tile.querySelectorAll('.nm-cell.selected').forEach(el => el.classList.remove('selected'));
      tile.querySelectorAll(`.nm-cell[data-col="${col}"]`).forEach(el => el.classList.add('selected'));

      // Select corresponding residue in Viewer v2 (component coordinates)
      const viewerEl = document.querySelector(`.seq-scroll.viewer-v2[data-molecule-id="${map.molecule_id}"][data-component-id="${map.component_id}"]`);
      if(viewerEl){
        const compIdx = (map.start_idx || 0) + abs;
        highlightRange(viewerEl, compIdx, compIdx + 1);
      }
    });

    return tile;
  }

  function renderNumberingMap(container, map, blockSize){
    container.innerHTML = '';
    container.style.setProperty('--nm-block', String(blockSize));
    for(let i=0; i<map.sequence.length; i += blockSize){
      container.appendChild(buildTile(map, blockSize, i));
    }
  }

  function getBlockSize(){
    const sel = document.getElementById('nm_block_size');
    const n = sel ? parseInt(sel.value || '10') : 10;
    return [5,10,20,25,50].includes(n) ? n : 10;
  }

  function loadNmSize(){
    try{
      const raw = localStorage.getItem('psi:nm:block_size');
      const n = parseInt(raw || '');
      if([5,10,20,25,50].includes(n)) return n;
    }catch(e){}
    return 10;
  }

  function saveNmSize(n){
    try{ localStorage.setItem('psi:nm:block_size', String(n)); }catch(e){}
  }

  // Render all maps on load
  const nmContainers = Array.from(document.querySelectorAll('.numbering-map'));
  if(nmContainers.length){
    const sel = document.getElementById('nm_block_size');
    const initial = loadNmSize();
    if(sel) sel.value = String(initial);
    const blockSize = initial;
    nmContainers.forEach((el) => {
      let map = {};
      try{ map = JSON.parse(el.dataset.map || '{}'); }catch(e){ map = {}; }
      map.molecule_id = esc(moleculeId);
      renderNumberingMap(el, map, blockSize);
    });

    if(sel){
      sel.addEventListener('change', () => {
        const n = getBlockSize();
        saveNmSize(n);
        nmContainers.forEach((el) => {
          let map = {};
          try{ map = JSON.parse(el.dataset.map || '{}'); }catch(e){ map = {}; }
          map.molecule_id = esc(moleculeId);
          renderNumberingMap(el, map, n);
        });
      });
    }
  }

  // Optional: reflect Viewer selection into the map (if map is open)
  window.addEventListener('psi:viewer-selection', (ev) => {
    try{
      const d = ev.detail || {};
      const componentId = String(d.componentId || d.component_id || '');
      const s = parseInt(d.start_idx || '0');
      const e = parseInt(d.end_idx || '0');
      if(!Number.isFinite(s) || !Number.isFinite(e) || e <= s) return;

      const panel = document.querySelector('.numbering-map-panel');
      if(panel && panel.open !== true) return;

      document.querySelectorAll('.numbering-map').forEach((el) => {
        let map = {};
        try{ map = JSON.parse(el.dataset.map || '{}'); }catch(e){ map = {}; }
        if(String(map.component_id) !== componentId) return;
        const abs = s - (parseInt(map.start_idx || '0'));
        if(abs < 0 || abs >= (map.sequence ? map.sequence.length : 0)) return;
        // Find the tile containing this abs index and highlight its column
        const blockSize = getBlockSize();
        const tileIdx = Math.floor(abs / blockSize);
        const col = String(abs % blockSize);
        const tiles = Array.from(el.querySelectorAll('.nm-tile'));
        const tile = tiles[tileIdx];
        if(!tile) return;
        tile.querySelectorAll('.nm-cell.selected').forEach(x => x.classList.remove('selected'));
        tile.querySelectorAll(`.nm-cell[data-col="${col}"]`).forEach(x => x.classList.add('selected'));
      });
    }catch(e){}
  });
  window.psiSetWrapColsAll = setWrapColsAll;

try{ setTimeout(()=>{ 
  if(typeof window.psiSetWrapColsAll === "function") window.psiSetWrapColsAll(); 
}, 0); }catch(e){}
})();
