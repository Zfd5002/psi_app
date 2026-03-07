(function () {
  function byId(id) { return document.getElementById(id); }
  function safe(v) { return String(v || ""); }
  function initSequenceEditorHover() {
    var panel = byId("sequence_editor_panel");
    var tip = byId("sequence_editor_tooltip");
    if (!panel || !tip) return;
    var residues = Array.prototype.slice.call(panel.querySelectorAll(".seq-residue"));
    var componentSelect = byId("seq_component_select");
    var queueRoot = byId("seq_mutation_queue");
    var queueClear = byId("seq_queue_clear");
    var directInput = byId("seq_direct_mutations");
    var directApply = byId("seq_direct_apply");
    var directErrors = byId("seq_direct_errors");
    var previewMeta = byId("seq_preview_meta");
    var previewErrors = byId("seq_preview_errors");
    var previewOriginal = byId("seq_preview_original");
    var previewEdited = byId("seq_preview_edited");
    var previewChanged = byId("seq_preview_changed_positions");
    var toBuilderComponent = byId("seq_to_builder_component");
    var toBuilderMutations = byId("seq_to_builder_mutations");
    var toBuilderQueuedComponent = byId("seq_to_builder_queued_component");
    var toBuilderMutationCount = byId("seq_to_builder_mutation_count");
    var toBuilderMutationTokens = byId("seq_to_builder_mutation_tokens");
    var toBuilderSubmit = byId("seq_to_builder_submit");
    var toBuilderHint = byId("seq_to_builder_hint");
    var toVariantMutationTokens = byId("seq_to_variant_mutation_tokens");
    var toVariantComponent = byId("seq_to_variant_component");
    var toVariantIncludePairs = byId("seq_to_variant_include_pairs");
    var toVariantExplicitCombos = byId("seq_to_variant_explicit_combos");
    var toVariantIncludeFullCombo = byId("seq_to_variant_include_full_combo");
    var toVariantSubmit = byId("seq_to_variant_submit");
    var toVariantHint = byId("seq_to_variant_hint");
    var queue = [];
    function firstComponentRole() {
      var firstTrack = panel.querySelector(".sequence-editor-track");
      return firstTrack ? safe(firstTrack.getAttribute("data-component-role")) : "";
    }
    function getSelectedComponentRole() {
      if (componentSelect && safe(componentSelect.value)) return safe(componentSelect.value);
      return firstComponentRole();
    }
    function queueSortKey(r) {
      return safe(r.component_role) + ":" + Number(r.position || 0);
    }
    function renderQueue() {
      if (!queueRoot) return;
      var ordered = queue.slice().sort(function (a, b) {
        return queueSortKey(a).localeCompare(queueSortKey(b));
      });
      queueRoot.innerHTML = "";
      if (!ordered.length) {
        var liEmpty = document.createElement("li");
        liEmpty.className = "muted";
        liEmpty.textContent = "No queued mutations.";
        queueRoot.appendChild(liEmpty);
      }
      if (ordered.length) {
        for (var i = 0; i < ordered.length; i += 1) {
          var row = ordered[i];
          var li = document.createElement("li");
          li.style.display = "flex";
          li.style.gap = "8px";
          li.style.alignItems = "center";
          li.style.justifyContent = "space-between";
          var txt = document.createElement("span");
          txt.textContent = safe(row.component_role) + " " + safe(row.from) + safe(row.position) + safe(row.to);
          var btn = document.createElement("button");
          btn.type = "button";
          btn.className = "btn mini";
          btn.textContent = "Remove";
          btn.setAttribute("data-k", queueSortKey(row));
          btn.addEventListener("click", function (ev) {
            var k = safe(ev.currentTarget.getAttribute("data-k"));
            queue = queue.filter(function (q) { return queueSortKey(q) !== k; });
            renderQueue();
          });
          li.appendChild(txt);
          li.appendChild(btn);
          queueRoot.appendChild(li);
        }
      }
      syncBuilderHandoff(ordered);
    }
    function syncBuilderHandoff(orderedQueue) {
      if (!toBuilderMutations || !toBuilderComponent || !toBuilderSubmit) return;
      var ordered = (orderedQueue || []).slice().sort(function (a, b) {
        return queueSortKey(a).localeCompare(queueSortKey(b));
      });
      if (!ordered.length) {
        toBuilderMutations.value = "";
        if (toBuilderQueuedComponent) toBuilderQueuedComponent.value = "";
        if (toBuilderMutationCount) toBuilderMutationCount.value = "0";
        if (toBuilderMutationTokens) toBuilderMutationTokens.value = "";
        toBuilderSubmit.disabled = true;
        if (toBuilderHint) toBuilderHint.textContent = "No queued mutations yet.";
        syncVariantSetHandoff([], true);
        return;
      }
      var component = safe(ordered[0].component_role);
      var sameComponent = ordered.every(function (r) { return safe(r.component_role) === component; });
      var toks = ordered.map(function (r) { return safe(r.from) + String(r.position) + safe(r.to); });
      if (!sameComponent) {
        toBuilderMutations.value = "";
        if (toBuilderQueuedComponent) toBuilderQueuedComponent.value = "";
        if (toBuilderMutationCount) toBuilderMutationCount.value = "0";
        if (toBuilderMutationTokens) toBuilderMutationTokens.value = "";
        toBuilderSubmit.disabled = true;
        if (toBuilderHint) toBuilderHint.textContent = "Queued edits span multiple components. Use one component to build a single variant draft.";
        syncVariantSetHandoff(ordered, false);
        return;
      }
      toBuilderComponent.value = component || "HC1";
      toBuilderMutations.value = toks.join(" ");
      if (toBuilderQueuedComponent) toBuilderQueuedComponent.value = component || "HC1";
      if (toBuilderMutationCount) toBuilderMutationCount.value = String(toks.length);
      if (toBuilderMutationTokens) toBuilderMutationTokens.value = toks.join(" ");
      toBuilderSubmit.disabled = false;
      if (toBuilderHint) toBuilderHint.textContent = "Ready to preview a derived Builder draft from queued mutations.";
      syncVariantSetHandoff(ordered, sameComponent);
    }
    function syncVariantSetHandoff(ordered, sameComponent) {
      if (!toVariantMutationTokens || !toVariantIncludePairs || !toVariantExplicitCombos || !toVariantSubmit) return;
      if (!ordered.length || !sameComponent) {
        toVariantMutationTokens.value = "";
        if (toVariantComponent) toVariantComponent.value = "";
        toVariantIncludePairs.value = "0";
        toVariantExplicitCombos.value = "";
        toVariantSubmit.disabled = true;
        if (toVariantHint) {
          toVariantHint.textContent = ordered.length
            ? "Queued edits span multiple components. Variant set seed expects one component."
            : "No queued mutations yet.";
        }
        return;
      }
      var toks = ordered.map(function (r) { return safe(r.from) + String(r.position) + safe(r.to); });
      toVariantMutationTokens.value = toks.join(" ");
      if (toVariantComponent) toVariantComponent.value = safe(ordered[0].component_role);
      toVariantIncludePairs.value = "0";
      if (toVariantIncludeFullCombo && toVariantIncludeFullCombo.checked && toks.length > 1) {
        toVariantExplicitCombos.value = toks.join("+");
      } else {
        toVariantExplicitCombos.value = "";
      }
      toVariantSubmit.disabled = false;
      if (toVariantHint) toVariantHint.textContent = "Ready to seed a mutation-panel variant set from queued mutations.";
    }
    function buildPreview() {
      var componentRole = getSelectedComponentRole();
      if (!componentRole) return;
      var residuesForComponent = residues.filter(function (r) {
        return safe(r.getAttribute("data-component-role")) === componentRole;
      });
      if (!residuesForComponent.length) return;
      var original = residuesForComponent.map(function (r) { return safe(r.getAttribute("data-aa")).toUpperCase(); }).join("");
      var chars = original.split("");
      var errs = [];
      var changed = [];
      var ordered = queue.slice().sort(function (a, b) { return queueSortKey(a).localeCompare(queueSortKey(b)); });
      for (var i = 0; i < ordered.length; i += 1) {
        var qrow = ordered[i];
        if (safe(qrow.component_role) !== componentRole) continue;
        var pos = Number(qrow.position || 0);
        if (!pos || pos < 1 || pos > chars.length) { errs.push("Out of range: " + qrow.from + pos + qrow.to); continue; }
        var actual = chars[pos - 1];
        if (qrow.from && actual !== qrow.from) { errs.push("WT mismatch at " + pos + ": expected " + qrow.from + ", found " + actual); continue; }
        chars[pos - 1] = safe(qrow.to).toUpperCase();
        changed.push(pos);
      }
      var edited = chars.join("");
      if (previewMeta) previewMeta.textContent = "Preview component: " + componentRole + " (" + chars.length + " aa)";
      if (previewOriginal) previewOriginal.textContent = original;
      if (previewEdited) previewEdited.textContent = edited;
      if (previewChanged) previewChanged.textContent = changed.length ? ("Changed positions: " + changed.sort(function(a,b){return a-b;}).join(", ")) : "Changed positions: none";
      if (previewErrors) previewErrors.textContent = errs.join(" | ");
    }
    function addOrReplace(row) {
      var k = queueSortKey(row);
      var next = [];
      var replaced = false;
      for (var j = 0; j < queue.length; j += 1) {
        if (queueSortKey(queue[j]) === k) {
          next.push(row);
          replaced = true;
        } else {
          next.push(queue[j]);
        }
      }
      if (!replaced) next.push(row);
      queue = next;
    }
    function showTip(ev, el) {
      var component = safe(el.getAttribute("data-component-role"));
      var pos = safe(el.getAttribute("data-position"));
      var aa = safe(el.getAttribute("data-aa"));
      var region = safe(el.getAttribute("data-region")) || "unassigned";
      var numbering = safe(el.getAttribute("data-numbering"));
      tip.innerHTML =
        "<div><b>" + component + " " + aa + pos + "</b></div>" +
        "<div>Region: " + region + "</div>" +
        "<div>Numbering: " + (numbering || "—") + "</div>";
      tip.style.display = "block";
      tip.style.left = String((ev.clientX || 0) + 12) + "px";
      tip.style.top = String((ev.clientY || 0) + 12) + "px";
    }
    function hideTip() { tip.style.display = "none"; }
    for (var i = 0; i < residues.length; i += 1) {
      residues[i].addEventListener("mouseenter", function (ev) { showTip(ev, ev.currentTarget); });
      residues[i].addEventListener("mousemove", function (ev) { showTip(ev, ev.currentTarget); });
      residues[i].addEventListener("mouseleave", hideTip);
      residues[i].addEventListener("click", function (ev) {
        var el = ev.currentTarget;
        var from = safe(el.getAttribute("data-aa"));
        var to = safe(window.prompt("Mutate residue " + from + safe(el.getAttribute("data-position")) + " to (single-letter AA):", ""));
        if (!to) return;
        to = to.trim().toUpperCase();
        if (!/^[A-Z]$/.test(to)) return;
        var row = {
          component_role: safe(el.getAttribute("data-component-role")),
          component_id: Number(el.getAttribute("data-component-id") || "0"),
          position: Number(el.getAttribute("data-position") || "0"),
          from: from,
          to: to
        };
        addOrReplace(row);
        el.style.background = "rgba(255, 193, 7, 0.25)";
        renderQueue();
        buildPreview();
      });
    }
    if (queueClear) {
      queueClear.addEventListener("click", function () {
        queue = [];
        for (var i2 = 0; i2 < residues.length; i2 += 1) {
          residues[i2].style.background = "";
        }
        renderQueue();
        buildPreview();
      });
    }
    function parseDirect(text) {
      var toks = String(text || "").split(/[\s,;]+/).filter(Boolean);
      var out = [];
      var errs = [];
      var seen = {};
      for (var i = 0; i < toks.length; i += 1) {
        var tok = toks[i].trim();
        var m = tok.match(/^([A-Za-z])(\d+)([A-Za-z])$/);
        if (!m) { errs.push("Invalid token: " + tok); continue; }
        var from = m[1].toUpperCase();
        var pos = Number(m[2]);
        var to = m[3].toUpperCase();
        if (!pos || pos < 1) { errs.push("Invalid position: " + tok); continue; }
        if (seen[pos]) { errs.push("Duplicate position: " + pos); continue; }
        seen[pos] = true;
        out.push({ from: from, position: pos, to: to });
      }
      return { rows: out, errors: errs };
    }
    function residueByPos(componentRole, pos) {
      return panel.querySelector('.seq-residue[data-component-role="' + componentRole + '"][data-position="' + String(pos) + '"]');
    }
    if (directApply) {
      directApply.addEventListener("click", function () {
        if (!directInput) return;
        var parsed = parseDirect(directInput.value || "");
        var errs = parsed.errors.slice();
        var componentRole = getSelectedComponentRole();
        var firstResidue = panel.querySelector('.seq-residue[data-component-role="' + componentRole + '"]');
        var componentId = firstResidue ? Number(firstResidue.getAttribute("data-component-id") || "0") : 0;
        for (var i3 = 0; i3 < parsed.rows.length; i3 += 1) {
          var row = parsed.rows[i3];
          var el2 = residueByPos(componentRole, row.position);
          if (!el2) {
            errs.push("Out of range: " + row.from + row.position + row.to);
            continue;
          }
          var actual = safe(el2.getAttribute("data-aa")).toUpperCase();
          if (actual !== row.from) {
            errs.push("WT mismatch at " + row.position + ": expected " + row.from + ", found " + actual);
            continue;
          }
          addOrReplace({
            component_role: componentRole,
            component_id: componentId,
            position: row.position,
            from: row.from,
            to: row.to
          });
          el2.style.background = "rgba(255, 193, 7, 0.25)";
        }
        if (directErrors) {
          directErrors.textContent = errs.join(" | ");
        }
        renderQueue();
        buildPreview();
      });
    }
    if (toVariantIncludeFullCombo) {
      toVariantIncludeFullCombo.addEventListener("change", function () {
        var ordered = queue.slice().sort(function (a, b) {
          return queueSortKey(a).localeCompare(queueSortKey(b));
        });
        var component = ordered.length ? safe(ordered[0].component_role) : "";
        var sameComponent = ordered.every(function (r) { return safe(r.component_role) === component; });
        syncVariantSetHandoff(ordered, sameComponent);
      });
    }
    if (componentSelect) {
      if (!safe(componentSelect.value)) componentSelect.value = firstComponentRole();
      componentSelect.addEventListener("change", function () {
        if (directErrors) directErrors.textContent = "";
        buildPreview();
      });
    }
    renderQueue();
    buildPreview();
  }
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initSequenceEditorHover);
  } else {
    initSequenceEditorHover();
  }
})();
