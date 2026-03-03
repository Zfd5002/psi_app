# UI Underscore Label Audit

- Repo root: `/home/zach/psi_repo`
- Total findings: `157`

## Findings by Category

- `direct_key_render_no_humanize`: `71`
- `literal_token_with_underscore`: `86`

## Detailed Findings

| Category | File | Line | Snippet |
|---|---|---:|---|
| direct_key_render_no_humanize | `psi/web/templates/batches/detail.html` | 84 | `<td>{{ row.decision_key }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/data/detail.html` | 68 | `{{ status }}` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 37 | `<div class="muted">Template: {{ snap_prov.template_name if snap_prov.template_name is defined and snap_prov.template_name else (snap_prov.template_key if snap_prov.template_key is defined and snap_prov.template_key else '—') }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 39 | `<div class="muted mini">template_key={{ snap_prov.template_key }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 92 | `<pre style="white-space:pre-wrap;overflow:auto;max-height:120px;">{{ output.state_transition \| tojson(indent=2) }}</pre>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 118 | `<div class="muted mini">readiness_state={{ error_block.readiness_state }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 183 | `<option value="{{ lt.key }}">{{ lt.label }}</option>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 203 | `<option value="{{ v.key }}">{{ v.label }}</option>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 225 | `<div style="font-size:22px;font-weight:800;">{{ output.decision_state }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 226 | `<div class="muted">Decision: {{ snap.decision_key }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 243 | `<div><span class="chip">{{ b.blocker_key if b.blocker_key is defined else b.get('blocker_key') }}</span></div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 254 | `<span class="chip">{{ rf_key }}</span>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 318 | `<div class="muted"><b>{{ ex.key if ex is mapping and ex.key is defined else '—' }}</b>: {{ ex.summary if ex is mapping and ex.summary is defined else '' }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 401 | `<td class="muted">{{ ev.evaluated_status if ev is mapping and ev.evaluated_status is defined else '—' }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 530 | `<div style="font-size:20px;font-weight:800;">{% if soe_cov is mapping and soe_cov is not none %}{{ 'v0.3' if soe.soe_v0_3 is defined and soe.soe_v0_3.metric_status is defined else ('v0.2' if soe.soe_v0_2 is defined else '—') }}{% else %}—{% endif %}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 554 | `<td>{{ ms.status if ms is mapping and ms.status is defined else (ms.get('status') if ms is mapping else '—') }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 556 | `<td class="muted">{% if ms is mapping and ms.qc_status is defined and ms.qc_status %}{{ ms.qc_status }}{% else %}—{% endif %}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 595 | `<td><b>{{ g.gate_key }}</b></td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 596 | `<td>{{ g.status }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 614 | `<b>{{ b.blocker_key if b.blocker_key is defined else 'blocker' }}</b>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 647 | `<b>{{ rkey if rkey else 'risk' }}</b>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 711 | `<td><b>{{ metric_key }}</b></td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 721 | `<td>{{ ev.qc_status if ev.qc_status is defined else '' }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 745 | `<td>{{ ig.metric_key if ig.metric_key is defined else '' }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_snapshot.html` | 762 | `<td>{{ ig.metric_key if ig.metric_key is defined else '' }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_verification.html` | 21 | `<span class="badge {{ anchored_badge }}">Anchored: {{ anchored_status }}</span>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_verification.html` | 76 | `<td><b>{{ row.metric_key }}</b></td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/_di_verification.html` | 77 | `<td class="muted">{{ row.reason_key }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/compare.html` | 30 | `<div class="muted">{{ snap_a.decision_key }} · rules {{ snap_a.rules_version }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/compare.html` | 36 | `<div class="muted">{{ snap_b.decision_key }} · rules {{ snap_b.rules_version }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/compare.html` | 71 | `<td><b>{{ gate_key }}</b></td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/compare.html` | 78 | `{% if g.status is defined %}<div><b>status:</b> {{ g.status.from }} → {{ g.status.to }}</div>{% endif %}` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/compare.html` | 99 | `<ul class="clean">{% for b in ch.readiness.blockers.added %}<li><b>{{ b.key }}</b>{% if b.explanation %}<span class="muted"> — {{ b.explanation }}</span>{% endif %}</li>{% endfor %}</ul>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/compare.html` | 105 | `<ul class="clean">{% for b in ch.readiness.blockers.removed %}<li><b>{{ b.key }}</b>{% if b.explanation %}<span class="muted"> — {{ b.explanation }}</span>{% endif %}</li>{% endfor %}</ul>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/detail.html` | 7 | `<h1 style="margin:0;">Decision #{{ snap.id }} ({{ snap.decision_key }})</h1>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/detail_print.html` | 7 | `<h1 style="margin:0;">Decision #{{ snap.id }} ({{ snap.decision_key }})</h1>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/detail_print.html` | 22 | `<h1 class="print-only" style="display:none;margin:0;">Decision #{{ snap.id }} ({{ snap.decision_key }})</h1>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/history.html` | 8 | `<div class="muted">Scope: {{ snap.decision_key }} · program {{ snap.program_id }} · molecule {{ snap.molecule_id }} · batch {{ snap.batch_id }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/history.html` | 46 | `<td>{{ row.decision_state }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/history.html` | 57 | `{{ row.state_transition.get("from_state", "") }} → {{ row.state_transition.get("to_state", "") }}` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/history.html` | 59 | `<span class="muted">({{ row.state_transition.get("trigger") }})</span>` |
| direct_key_render_no_humanize | `psi/web/templates/decisions/list.html` | 27 | `{{ s.decision_key }}` |
| direct_key_render_no_humanize | `psi/web/templates/di/run.html` | 83 | `{{ p.decision_key }} · {{ p.policy_version }} · {{ p.policy_name }}` |
| direct_key_render_no_humanize | `psi/web/templates/lineage/portfolio_detail.html` | 44 | `<pre style="white-space:pre-wrap;">{{ membership_state \| tojson(indent=2) }}</pre>` |
| direct_key_render_no_humanize | `psi/web/templates/lineage/program_detail.html` | 54 | `<pre style="white-space:pre-wrap;">{{ membership_state \| tojson(indent=2) }}</pre>` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 70 | `<b>Blocked by prerequisites</b>{% if mh.progress_stage_advisory.milestone_key %} ({{ mh.progress_stage_advisory.milestone_key }}){% endif %}: {{ mh.progress_stage_advisory.blocked_by_text }}` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 92 | `{{ mh.heavy_compute_banner if mh.heavy_compute_banner is defined else 'Heavy compute status unavailable.' }}` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 108 | `<b>Blocked by prerequisites</b> for {{ a.milestone_key }}:` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 125 | `<div class="molecule-confidence-summary state-{{ cm.scalar_state if cm.scalar_state is defined else 'unknown' }}" title="{{ cm.rule_text if cm.rule_text is defined else '' }}">` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 132 | `<div class="molecule-confidence-item state-{{ c.state if c.state is defined else 'not_assessed' }}">` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 163 | `<b>{{ m.key }}</b> — {% if m.satisfied %}satisfied{% else %}not yet{% endif %}` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 173 | `template={{ m.detail.template_key if m.detail.template_key is defined else '—' }}` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 178 | `· state={{ m.detail.latest_decision_state }}` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 202 | `{{ ri.key }} · {{ ri.severity if ri.severity is defined else 'unspecified' }}` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 294 | `<details class="batch-panel" data-psi-details-key="{{ details_key }}">` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 395 | `<details class="assay-node" data-psi-details-key="{{ details_key }}:assay:{{ assay }}">` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 398 | `<details class="cond-node" data-psi-details-key="{{ details_key }}:assay:{{ assay }}:cond:{{ fp }}">` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 493 | `<td>{{ row.decision_key }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 504 | `<div><b>{{ row.summary.decision_state }}</b></div>` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 670 | `<div class="muted">{{ latest_run.created_at }} · {{ latest_run.status }} · {{ latest_run.trigger_reason }} · tier={{ latest_run.compute_tier }}</div>` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 923 | `<td>{{ r.status }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/detail.html` | 1129 | `<td>{{ di.status }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/molecules/list.html` | 38 | `<div class="molecule-confidence-summary state-{{ cm.scalar_state if cm.scalar_state is defined else 'unknown' }}" title="{{ cm.rule_text if cm.rule_text is defined else '' }}" style="margin-top:0;">` |
| direct_key_render_no_humanize | `psi/web/templates/programs/detail.html` | 113 | `<li><a href="/decisions/{{ d.id }}">{{ d.decision_key }}</a> <span class="muted">{{ d.created_at }}</span></li>` |
| direct_key_render_no_humanize | `psi/web/templates/reports/_technical_audit.html` | 20 | `<pre style="white-space:pre-wrap;">{{ (measurement_key_citations if measurement_key_citations is defined else []) \| tojson(indent=2) }}</pre>` |
| direct_key_render_no_humanize | `psi/web/templates/reports/_technical_audit.html` | 31 | `"measurement_summary": {{ ((measurement_key_citations if measurement_key_citations is defined and measurement_key_citations else "missing") \| tojson(indent=2)) }},` |
| direct_key_render_no_humanize | `psi/web/templates/reports/board_comparison_v3.html` | 88 | `<td>{{ "✓" if col in row_keys else "—" }}</td>` |
| direct_key_render_no_humanize | `psi/web/templates/reports/board_molecule_v3.html` | 120 | `{{ item.label if item.label is defined else (item.suggestion_key if item.suggestion_key is defined else (item \| tojson(indent=0))) }}` |
| direct_key_render_no_humanize | `psi/web/templates/reports/board_molecule_v3.html` | 146 | `<code>{{ mkeys\|sort\|join(", ") }}</code>` |
| direct_key_render_no_humanize | `psi/web/templates/reports/board_template_ladder_v3.html` | 23 | `<tr><td>{{ row.stage_key }}</td><td>{{ row.current_version }}</td></tr>` |
| direct_key_render_no_humanize | `psi/web/templates/reports/board_upgrade_delta_v3.html` | 13 | `<td>{{ report.header.changed_key_count if report.header is defined and report.header.changed_key_count is defined else "missing" }}</td>` |
| literal_token_with_underscore | `psi/web/static/style.css` | 268 | `.molecule-confidence-item.state-not_assessed { background:rgba(149,165,166,.08); color:var(--muted); }` |
| literal_token_with_underscore | `psi/web/templates/batches/detail.html` | 82 | `<td><a href="/decisions/{{ row.snapshot_id }}">#{{ row.snapshot_id }}</a></td>` |
| literal_token_with_underscore | `psi/web/templates/batches/detail.html` | 85 | `<td class="muted">{{ row.policy_id }}@{{ row.policy_version }}</td>` |
| literal_token_with_underscore | `psi/web/templates/batches/detail.html` | 93 | `<div class="muted"><a href="/decisions/compare?snap_a={{ row.prev_snapshot_id }}&snap_b={{ row.snapshot_id }}">compare</a></div>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 44 | `<div>{{ snap_prov.policy_version if snap_prov.policy_version is defined and snap_prov.policy_version else '—' }}</div>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 243 | `<div><span class="chip">{{ b.blocker_key if b.blocker_key is defined else b.get('blocker_key') }}</span></div>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 351 | `<div class="muted">{{ policy.policy_version if policy.policy_version is defined else (policy.version if policy.version is defined else '') }}</div>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 548 | `<thead><tr><th>metric_key</th><th>required?</th><th>status</th><th>measurement_id</th><th>qc</th><th>timestamp_used</th><th class="muted">notes</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 570 | `<thead><tr><th>gate_key</th><th>requirement</th><th>present</th><th>missing</th><th>satisfied</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 593 | `{% for g in output.gates\|sort(attribute='gate_key') %}` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 595 | `<td><b>{{ g.gate_key }}</b></td>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 614 | `<b>{{ b.blocker_key if b.blocker_key is defined else 'blocker' }}</b>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 617 | `{% if exp_sugg and (b.blocker_key is defined) and (b.blocker_key in exp_sugg) %}` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 620 | `{% for ek in exp_sugg[b.blocker_key] %}<span class="tag">{{ ek }}</span>{% endfor %}` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 698 | `<th>metric_key</th>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 709 | `{% for metric_key, ev in used\|dictsort %}` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 711 | `<td><b>{{ metric_key }}</b></td>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 741 | `<thead><tr><th>metric_key</th><th>measurement_id</th><th>qc_source</th><th>reason_detail</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 745 | `<td>{{ ig.metric_key if ig.metric_key is defined else '' }}</td>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 758 | `<thead><tr><th>metric_key</th><th>measurement_id</th><th>reason</th><th>details</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_snapshot.html` | 762 | `<td>{{ ig.metric_key if ig.metric_key is defined else '' }}</td>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_verification.html` | 66 | `<th>metric_key</th>` |
| literal_token_with_underscore | `psi/web/templates/decisions/_di_verification.html` | 76 | `<td><b>{{ row.metric_key }}</b></td>` |
| literal_token_with_underscore | `psi/web/templates/decisions/compare.html` | 51 | `<tr><td><b>policy_version</b></td><td>{{ policy_a.policy_version }}</td><td>{{ policy_b.policy_version }}</td></tr>` |
| literal_token_with_underscore | `psi/web/templates/decisions/compare.html` | 69 | `{% for gate_key, g in ch.gate_outcomes\|dictsort %}` |
| literal_token_with_underscore | `psi/web/templates/decisions/compare.html` | 71 | `<td><b>{{ gate_key }}</b></td>` |
| literal_token_with_underscore | `psi/web/templates/decisions/compare.html` | 132 | `<thead><tr><th>metric_key</th><th>field</th><th>A</th><th>B</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/decisions/history.html` | 41 | `<input type="checkbox" name="snapshot_ids" value="{{ row.snapshot_id }}"` |
| literal_token_with_underscore | `psi/web/templates/decisions/history.html` | 42 | `{% if selected_ids is defined and row.snapshot_id in selected_ids %}checked{% endif %} />` |
| literal_token_with_underscore | `psi/web/templates/decisions/history.html` | 44 | `<td><a href="/decisions/{{ row.snapshot_id }}">#{{ row.snapshot_id }}</a></td>` |
| literal_token_with_underscore | `psi/web/templates/decisions/verify.html` | 32 | `<tr><td><b>policy_version</b></td><td>{{ report.stored.policy_version }}</td><td>{{ report.stored.policy_version }}</td><td>{{ report.stored.policy_version }}</td></tr>` |
| literal_token_with_underscore | `psi/web/templates/di/run.html` | 83 | `{{ p.decision_key }} · {{ p.policy_version }} · {{ p.policy_name }}` |
| literal_token_with_underscore | `psi/web/templates/molecules/detail.html` | 132 | `<div class="molecule-confidence-item state-{{ c.state if c.state is defined else 'not_assessed' }}">` |
| literal_token_with_underscore | `psi/web/templates/molecules/detail.html` | 135 | `{{ (c.state if c.state is defined else 'not_assessed')\|humanize_state }}` |
| literal_token_with_underscore | `psi/web/templates/molecules/detail.html` | 465 | `<th>snapshot_id</th>` |
| literal_token_with_underscore | `psi/web/templates/molecules/detail.html` | 479 | `<td><a href="/decisions/{{ row.snapshot_id }}"><b>#{{ row.snapshot_id }}</b></a></td>` |
| literal_token_with_underscore | `psi/web/templates/molecules/detail.html` | 501 | `<div class="muted">{{ row.policy_version }}</div>` |
| literal_token_with_underscore | `psi/web/templates/molecules/detail.html` | 510 | `<div class="muted"><a href="/decisions/compare?snap_a={{ row.prev_snapshot_id }}&snap_b={{ row.snapshot_id }}">compare</a></div>` |
| literal_token_with_underscore | `psi/web/templates/molecules/list.html` | 45 | `{{ c.name }}: {{ (c.state if c.state is defined else 'not_assessed')\|humanize_state }}` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 140 | `<div class="muted">Filter: {{ "policy_version"\|humanize_key }} = {{ di_dashboard.policy_version_filter }} · <a href="/programs/{{ program.id }}">clear</a></div>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 146 | `<thead><tr><th>{{ "policy_version"\|humanize_key }}</th><th>Count</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 150 | `<td><a href="/programs/{{ program.id }}?policy_version={{ k \| urlencode }}">{{ k }}</a></td>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 179 | `<thead><tr><th>{{ "blocker_key"\|humanize_key }}</th><th>Count</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 192 | `<thead><tr><th>{{ "metric_key"\|humanize_key }}</th><th>Count</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 208 | `<thead><tr><th>{{ "gate_key"\|humanize_key }}</th><th>Count</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 221 | `<thead><tr><th>{{ "metric_key"\|humanize_key }}</th><th>Present</th><th>Missing</th><th>% Present</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 225 | `<td>{{ row.metric_key\|humanize_key }}</td>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 255 | `<thead><tr><th>{{ "metric_key"\|humanize_key }}</th><th>Count</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 268 | `<thead><tr><th>{{ "metric_key"\|humanize_key }}</th><th>Count</th></tr></thead>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 305 | `<td class="muted">{{ r.policy_version or '' }}</td>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 315 | `<a href="/programs/{{ program.id }}{% if di_dashboard.policy_version_filter %}?policy_version={{ di_dashboard.policy_version_filter \| urlencode }}{% endif %}">Hide verification</a>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 317 | `<a href="/programs/{{ program.id }}?verify=1{% if di_dashboard.policy_version_filter %}&policy_version={{ di_dashboard.policy_version_filter \| urlencode }}{% endif %}">Show verification</a>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 324 | `<th>snapshot_id</th>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 337 | `<td><a href="/decisions/{{ row.snapshot_id }}">#{{ row.snapshot_id }}</a></td>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 349 | `<div class="muted">{{ row.policy_version }}</div>` |
| literal_token_with_underscore | `psi/web/templates/programs/detail.html` | 368 | `<div class="muted"><a href="/decisions/compare?snap_a={{ row.prev_snapshot_id }}&snap_b={{ row.snapshot_id }}">compare</a></div>` |
| literal_token_with_underscore | `psi/web/templates/reports/_board_narrative.html` | 48 | `(det.outcome if det is mapping and det.outcome is defined else "not_assessed"),` |
| literal_token_with_underscore | `psi/web/templates/reports/_board_narrative.html` | 49 | `(det.rule_id if det is mapping and det.rule_id is defined else "not_available"),` |
| literal_token_with_underscore | `psi/web/templates/reports/_determination_card.html` | 1 | `{% macro render_determination_card(title, outcome_label, rule_id, snapshot_ids, measurement_keys, rationale, missing_inputs, extra_note="") -%}` |
| literal_token_with_underscore | `psi/web/templates/reports/_determination_card.html` | 2 | `{% set raw_outcome = (outcome_label or "not_assessed") %}` |
| literal_token_with_underscore | `psi/web/templates/reports/_determination_card.html` | 5 | `"not_assessed": "Not assessed yet",` |
| literal_token_with_underscore | `psi/web/templates/reports/_determination_card.html` | 14 | `<span class="badge {% if raw_outcome in ['on_track','comparable_full','comparable_partial','enabled'] %}good{% elif raw_outcome in ['policy_disabled','policy_incomplete','not_assessed'] %}warn{% else %}bad{% endif %}">` |
| literal_token_with_underscore | `psi/web/templates/reports/_determination_card.html` | 19 | `<div class="k">Policy rule</div><div><code>{{ rule_id if rule_id else "missing" }}</code></div>` |
| literal_token_with_underscore | `psi/web/templates/reports/board_comparison_v3.html` | 45 | `<td>{{ (row.stage if row is mapping and row.stage is defined else "not_assessed")\|humanize_state }}</td>` |
| literal_token_with_underscore | `psi/web/templates/reports/board_comparison_v3.html` | 46 | `<td>{{ row.snapshot_id if row is mapping and row.snapshot_id is defined else "Not available" }}</td>` |
| literal_token_with_underscore | `psi/web/templates/reports/board_comparison_v3.html` | 141 | `{% set posture_state = (match.posture_state if match is mapping and match.posture_state is defined else "not_assessed") %}` |
| literal_token_with_underscore | `psi/web/templates/reports/board_molecule_v3.html` | 89 | `<td>{{ row.label if row is mapping and row.label is defined else ((row.metric_key if row is mapping and row.metric_key is defined else "")\|humanize_key) }}</td>` |
| literal_token_with_underscore | `psi/web/templates/reports/board_molecule_v3.html` | 92 | `<td>{{ (row.status if row is mapping and row.status is defined else "not_assessed")\|humanize_state }}</td>` |
| literal_token_with_underscore | `psi/web/templates/reports/board_program_v3.html` | 7 | `{% set ns = namespace(total=0, ready=0, blocked=0, not_assessed=0, high_risk=0) %}` |
| literal_token_with_underscore | `psi/web/templates/reports/board_program_v3.html` | 11 | `{% set st = (row.stage\|string\|lower if row.stage is defined else "not_assessed") %}` |
| literal_token_with_underscore | `psi/web/templates/reports/board_program_v3.html` | 14 | `{% if st == "not_assessed" %}{% set ns.not_assessed = ns.not_assessed + 1 %}{% endif %}` |
| literal_token_with_underscore | `psi/web/templates/reports/board_program_v3.html` | 26 | `<tr><th>Not assessed</th><td>{{ ns.not_assessed }}</td></tr>` |
| literal_token_with_underscore | `psi/web/ui_labels.py` | 39 | `"not_assessed": "Not assessed by this surface.",` |
| literal_token_with_underscore | `tests/test_board_determination_card_rendering.py` | 29 | `"outcome": "not_assessed",` |
| literal_token_with_underscore | `tests/test_board_determination_card_rendering.py` | 30 | `"rule_id": "rule_not_assessed_default",` |
| literal_token_with_underscore | `tests/test_board_molecule_sections_rendering.py` | 35 | `"rows": [{"metric_key": "kd", "label": "KD", "value_display": "1 cited", "unit": "nM", "n": 1, "status": "present"}],` |
| literal_token_with_underscore | `tests/test_board_program_posture_rendering.py` | 31 | `{"molecule_id": 3, "stage": "not_assessed", "high_severity_risk_present": False},` |
| literal_token_with_underscore | `tests/test_scientific_summary_report.py` | 71 | `assert [str(r.get("metric_key") or "") for r in first_domain_rows] == ["kd"]` |
| literal_token_with_underscore | `tests/test_v3_report_contracts.py` | 133 | `latest_comp_version = str(load_comparability_policy_latest().get("policy_version") or "v0.1")` |
| literal_token_with_underscore | `tests/test_v3_report_contracts.py` | 168 | `rule_id="placeholder_not_assessed",` |
| literal_token_with_underscore | `tests/test_v3_report_contracts.py` | 181 | `assert det.get("rule_id") != "policy_no_match"` |
| literal_token_with_underscore | `tests/test_v3_report_contracts.py` | 283 | `assert str(comp_pin.get("policy_version") or "") == str(latest.get("policy_version") or "")` |
| literal_token_with_underscore | `tests/test_v3_report_engine_contracts.py` | 34 | `for k in ("policy_pins", "catalog_versions", "cited_snapshot_ids", "inputs_summary"):` |
| literal_token_with_underscore | `tests/test_v3_report_engine_contracts.py` | 58 | `assert str(comp_pin.get("policy_version") or "") == str(latest.get("policy_version") or "")` |
| literal_token_with_underscore | `tests/test_v3_reports_ui_identity.py` | 40 | `"snapshot_id": 11,` |
| literal_token_with_underscore | `tests/test_v3_reports_ui_identity.py` | 94 | `assert s1 == "M1 (Mol 1) · program_id=1 · snapshot_id=11"` |
