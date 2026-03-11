from __future__ import annotations

from typing import Any


SurfaceDescriptor = dict[str, Any]


def nav_item(label: str, href: str, *, active: bool = False) -> dict[str, Any]:
    return {
        "label": str(label or "").strip(),
        "href": str(href or "").strip(),
        "active": bool(active),
    }


def surface_descriptor(
    *,
    surface_key: str,
    surface_kind: str,
    surface_title: str,
    surface_subtitle: str = "",
    dominant_purpose: str = "",
    local_nav: list[dict[str, Any]] | None = None,
    archetype_labels: list[str] | None = None,
    attention_mode: str = "",
    workflow_stage_emphasis: str = "",
    secondary_sections_collapsed_by_default: bool = False,
) -> SurfaceDescriptor:
    return {
        "surface_key": str(surface_key or "").strip(),
        "surface_kind": str(surface_kind or "").strip().lower(),
        "surface_title": str(surface_title or "").strip(),
        "surface_subtitle": str(surface_subtitle or "").strip(),
        "dominant_purpose": str(dominant_purpose or "").strip(),
        "local_nav": list(local_nav or []),
        "archetype_labels": [str(x or "").strip() for x in (archetype_labels or []) if str(x or "").strip()],
        "attention_mode": str(attention_mode or "").strip(),
        "workflow_stage_emphasis": str(workflow_stage_emphasis or "").strip(),
        "secondary_sections_collapsed_by_default": bool(secondary_sections_collapsed_by_default),
    }


def overview_surface(**kwargs: Any) -> SurfaceDescriptor:
    return surface_descriptor(surface_kind="overview", **kwargs)


def workspace_surface(**kwargs: Any) -> SurfaceDescriptor:
    return surface_descriptor(surface_kind="workspace", **kwargs)


def operational_surface(**kwargs: Any) -> SurfaceDescriptor:
    return surface_descriptor(surface_kind="operational", **kwargs)


def workflow_surface(**kwargs: Any) -> SurfaceDescriptor:
    return surface_descriptor(surface_kind="workflow", **kwargs)


def registry_surface(**kwargs: Any) -> SurfaceDescriptor:
    return surface_descriptor(surface_kind="registry", **kwargs)


def program_detail_surface(*, program_id: int) -> SurfaceDescriptor:
    return overview_surface(
        surface_key="program_detail",
        surface_title="Program Strategy",
        dominant_purpose="state and priorities",
        local_nav=[
            nav_item("Overview", "#overview"),
            nav_item("Program State", "#program-state-header"),
            nav_item("Attention Now", "#attention-now"),
            nav_item("Priorities", "#scientific-priorities"),
            nav_item("Execution Links", "#execution-links"),
            nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"),
            nav_item("Open Tasks", "#open-tasks"),
        ],
        archetype_labels=["Overview Page", "Workspace Links", "Operational Handoff"],
        attention_mode="high",
        workflow_stage_emphasis="program execution",
    )


def program_board_surface(*, program_id: int) -> SurfaceDescriptor:
    return operational_surface(
        surface_key="program_board",
        surface_title="Development Board",
        dominant_purpose="daily execution triage",
        local_nav=[
            nav_item("Summary", "#board-summary"),
            nav_item("Execution", "#board-execution"),
            nav_item("Ready", "#board-ready"),
            nav_item("Failed", "#board-failed"),
            nav_item("Missing", "#board-missing-data"),
            nav_item("Not Evaluated", "#board-not-evaluated"),
            nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"),
        ],
        archetype_labels=["Overview Inputs", "Operational Page", "Execution Actions"],
        attention_mode="high",
        workflow_stage_emphasis="task launch and triage",
    )


def program_workflow_surface(*, program_id: int) -> SurfaceDescriptor:
    return workflow_surface(
        surface_key="program_workflow",
        surface_title="Program Workflow",
        dominant_purpose="task lifecycle execution",
        local_nav=[
            nav_item("Ready to Start", "#ready-start"),
            nav_item("In Progress", "#in-progress"),
            nav_item("Blocked", "#blocked"),
            nav_item("Awaiting Data Entry", "#awaiting-data"),
            nav_item("Recently Completed", "#completed"),
            nav_item("Recent Learning", "#recent-learning"),
            nav_item("Awaiting Interpretation", "#interpretation-queue"),
            nav_item("Program Strategy", f"/programs/{int(program_id)}"),
            nav_item("Board", f"/programs/{int(program_id)}/board"),
        ],
        archetype_labels=["Program Workspace", "Operational Page", "Execution Loop"],
        attention_mode="high",
        workflow_stage_emphasis="start/resume/unblock/close",
    )


def molecule_detail_surface(*, molecule_id: int) -> SurfaceDescriptor:
    return workspace_surface(
        surface_key="molecule_detail",
        surface_title="Molecule Workspace",
        dominant_purpose="scientific and execution loop",
        local_nav=[
            nav_item("Workspace", f"/molecules/{int(molecule_id)}"),
            nav_item("Results", f"/molecules/{int(molecule_id)}/results"),
            nav_item("Sequence", f"/molecules/{int(molecule_id)}/sequence"),
            nav_item("Governance", f"/molecules/{int(molecule_id)}/governance"),
        ],
        archetype_labels=["Overview Signals", "Scientific Workspace", "Operational Loop"],
        attention_mode="high",
        workflow_stage_emphasis="evidence to task loop",
    )


def molecule_results_surface(*, molecule_id: int) -> SurfaceDescriptor:
    return workspace_surface(
        surface_key="molecule_results",
        surface_title="Molecule Results",
        dominant_purpose="molecule-first experiment result review",
        local_nav=[
            nav_item("Workspace", f"/molecules/{int(molecule_id)}"),
            nav_item("Results", f"/molecules/{int(molecule_id)}/results"),
            nav_item("Sequence", f"/molecules/{int(molecule_id)}/sequence"),
            nav_item("Governance", f"/molecules/{int(molecule_id)}/governance"),
        ],
        archetype_labels=["ELN Review", "Scientific Workspace", "Result History"],
        attention_mode="high",
        workflow_stage_emphasis="result interpretation",
    )


def molecule_sequence_surface(*, molecule_id: int) -> SurfaceDescriptor:
    return workspace_surface(
        surface_key="molecule_sequence",
        surface_title="Molecule Sequence",
        dominant_purpose="sequence and annotation inspection with builder handoff",
        local_nav=[
            nav_item("Workspace", f"/molecules/{int(molecule_id)}"),
            nav_item("Results", f"/molecules/{int(molecule_id)}/results"),
            nav_item("Sequence", f"/molecules/{int(molecule_id)}/sequence"),
            nav_item("Governance", f"/molecules/{int(molecule_id)}/governance"),
        ],
        archetype_labels=["Sequence View", "Design Surface", "Annotation Review"],
        attention_mode="normal",
        workflow_stage_emphasis="sequence design review",
    )


def molecule_governance_surface(*, molecule_id: int) -> SurfaceDescriptor:
    return workspace_surface(
        surface_key="molecule_governance",
        surface_title="Molecule Governance",
        dominant_purpose="assessment lineage, snapshots, and audit detail",
        local_nav=[
            nav_item("Workspace", f"/molecules/{int(molecule_id)}"),
            nav_item("Results", f"/molecules/{int(molecule_id)}/results"),
            nav_item("Sequence", f"/molecules/{int(molecule_id)}/sequence"),
            nav_item("Governance", f"/molecules/{int(molecule_id)}/governance"),
        ],
        archetype_labels=["Governance View", "Assessment History", "Audit Trace"],
        attention_mode="normal",
        workflow_stage_emphasis="policy and snapshot traceability",
    )


def portfolio_overview_surface() -> SurfaceDescriptor:
    return overview_surface(
        surface_key="portfolio_overview",
        surface_title="Portfolio Intelligence",
        dominant_purpose="cross-program prioritization",
        local_nav=[
            nav_item("Attention", "#portfolio-attention"),
            nav_item("Summary", "#portfolio-summary"),
            nav_item("Narrative", "#portfolio-narrative"),
            nav_item("Programs", "#program-table"),
            nav_item("Molecules", "#molecule-leaderboard"),
            nav_item("Evidence Gaps", "#evidence-gaps"),
            nav_item("Timeline", "#portfolio-timeline"),
        ],
        archetype_labels=["Overview Page", "Prioritization Surface", "Secondary Analytics"],
        attention_mode="high",
        workflow_stage_emphasis="portfolio sequencing",
    )


def claim_detail_surface(*, program_id: int | None = None) -> SurfaceDescriptor:
    nav = [
        nav_item("Interpretation", "#claim-interpretation"),
        nav_item("Maturity", "#claim-maturity"),
        nav_item("Evidence", "#claim-evidence"),
        nav_item("Lifecycle", "#claim-lifecycle"),
        nav_item("Tasks", "#claim-tasks"),
        nav_item("Trajectory", "#claim-trajectory"),
        nav_item("Plans", "#claim-plans"),
    ]
    if program_id is not None:
        nav.append(nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"))
    return workspace_surface(
        surface_key="claim_detail",
        surface_title="Scientific Claim",
        dominant_purpose="interpretation and de-risking",
        local_nav=nav,
        archetype_labels=["Interpretation Workspace", "Scientific Workspace", "Execution Links"],
        attention_mode="medium",
        workflow_stage_emphasis="claim support and conflict",
    )


def plan_detail_surface(*, program_id: int | None = None) -> SurfaceDescriptor:
    nav = [
        nav_item("Interpretation", "#plan-interpretation"),
        nav_item("Ordered Steps", "#plan-steps"),
        nav_item("Actions", "#plan-actions"),
    ]
    if program_id is not None:
        nav.append(nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"))
    return workspace_surface(
        surface_key="plan_detail",
        surface_title="Scientific Plan",
        dominant_purpose="rationale to execution instantiation",
        local_nav=nav,
        archetype_labels=["Interpretation Workspace", "Scientific Workspace", "Operational Instantiation"],
        attention_mode="medium",
        workflow_stage_emphasis="plan to task instantiation",
    )


def programs_registry_surface() -> SurfaceDescriptor:
    return registry_surface(
        surface_key="programs_registry",
        surface_title="Programs",
        dominant_purpose="browse and open program strategy surfaces",
        local_nav=[nav_item("Programs", "/programs"), nav_item("New Program", "/programs/new")],
        archetype_labels=["Registry Page", "Open Strategy Surfaces"],
        workflow_stage_emphasis="program selection",
    )


def molecules_registry_surface() -> SurfaceDescriptor:
    return registry_surface(
        surface_key="molecules_registry",
        surface_title="Molecules",
        dominant_purpose="browse molecules and open scientist workspaces",
        local_nav=[nav_item("Molecules", "/molecules"), nav_item("New Molecule", "/molecules/new")],
        archetype_labels=["Registry Page", "Open Workspaces"],
        workflow_stage_emphasis="molecule selection",
    )


def claims_registry_surface(*, program_id: int | None = None) -> SurfaceDescriptor:
    nav = [nav_item("Claims", "/claims"), nav_item("New Claim", "/claims/new")]
    if program_id is not None:
        nav = [
            nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"),
            nav_item("Program Workspace", f"/programs/{int(program_id)}"),
            nav_item("Claims (Program)", f"/claims?program_id={int(program_id)}"),
            nav_item("New Claim", "/claims/new"),
        ]
    return registry_surface(
        surface_key="claims_registry",
        surface_title="Scientific Claims",
        dominant_purpose="review and open claim interpretation workspaces",
        local_nav=nav,
        archetype_labels=["Registry Page", "Scientific Interpretation"],
    )


def plans_registry_surface(*, program_id: int | None = None) -> SurfaceDescriptor:
    nav = [nav_item("Plans", "/plans"), nav_item("New Plan", "/plans/new")]
    if program_id is not None:
        nav = [
            nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"),
            nav_item("Program Workspace", f"/programs/{int(program_id)}"),
            nav_item("Plans (Program)", f"/plans?program_id={int(program_id)}"),
            nav_item("New Plan", "/plans/new"),
        ]
    return registry_surface(
        surface_key="plans_registry",
        surface_title="Scientific Plans",
        dominant_purpose="review and open plan execution workspaces",
        local_nav=nav,
        archetype_labels=["Registry Page", "Execution Planning"],
    )


def data_registry_surface() -> SurfaceDescriptor:
    return registry_surface(
        surface_key="data_registry",
        surface_title="Experiment Results",
        surface_subtitle="Scientist-facing record of captured runs and extracted measurements.",
        dominant_purpose="scan recorded experiments and continue execution using current assessment feedback",
        local_nav=[nav_item("Experiment Results", "/data"), nav_item("Add Experiment Result", "/data/new"), nav_item("Bulk Import", "/data/bulk-import")],
        archetype_labels=["Registry Page", "Experiment Loop Entry"],
    )


def data_entry_surface(*, program_id: int | None = None, molecule_id: int | None = None, from_task: bool = False) -> SurfaceDescriptor:
    nav = [nav_item("Experiment Results", "/data"), nav_item("Add Experiment Result", "/data/new")]
    if program_id is not None:
        nav.append(nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"))
        nav.append(nav_item("Program Board", f"/programs/{int(program_id)}/board"))
    if molecule_id is not None:
        nav.append(nav_item("Molecule Workspace", f"/molecules/{int(molecule_id)}"))
    return workflow_surface(
        surface_key="data_entry",
        surface_title="Capture Experiment Result",
        surface_subtitle="Record experimental output with clear scientific context and workflow linkage.",
        dominant_purpose="capture experiment results and close operational loops",
        local_nav=nav,
        archetype_labels=["Workflow Page", "Result Capture", "Assessment Refresh"],
        workflow_stage_emphasis="task to result to assessment",
        attention_mode="high" if from_task else "normal",
    )


def data_detail_surface(*, record_id: int, program_id: int | None = None, molecule_id: int | None = None) -> SurfaceDescriptor:
    nav = [nav_item("Experiment Results", "/data"), nav_item("This Result Record", f"/data/{int(record_id)}")]
    if program_id is not None:
        nav.append(nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"))
    if molecule_id is not None:
        nav.append(nav_item("Molecule Workspace", f"/molecules/{int(molecule_id)}"))
    return workspace_surface(
        surface_key="data_detail",
        surface_title="Experiment Result Record",
        surface_subtitle="Review captured output, extracted measurements, and evidence linkage.",
        dominant_purpose="review recorded results and continue execution with refreshed assessment",
        local_nav=nav,
        archetype_labels=["Scientific Workspace", "Experiment Loop Entry"],
        workflow_stage_emphasis="result review and workflow re-entry",
    )


def evidence_registry_surface() -> SurfaceDescriptor:
    return registry_surface(
        surface_key="evidence_registry",
        surface_title="Scientific Evidence",
        surface_subtitle="Interpreted support objects linked to cited result records.",
        dominant_purpose="scan evidence records and inspect scientific support context",
        local_nav=[nav_item("Evidence", "/evidence"), nav_item("New Evidence", "/evidence/new")],
        archetype_labels=["Registry Page", "Scientific Support Layer"],
    )


def evidence_entry_surface(*, program_id: int | None = None, molecule_id: int | None = None, batch_id: int | None = None) -> SurfaceDescriptor:
    nav = [nav_item("Evidence", "/evidence"), nav_item("New Evidence", "/evidence/new")]
    if program_id is not None:
        nav.append(nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"))
    if molecule_id is not None:
        nav.append(nav_item("Molecule Workspace", f"/molecules/{int(molecule_id)}"))
    if batch_id is not None:
        nav.append(nav_item("Batch Detail", f"/batches/{int(batch_id)}"))
    return workflow_surface(
        surface_key="evidence_entry",
        surface_title="Capture Scientific Evidence",
        surface_subtitle="Create a claim-supporting evidence object anchored to cited data records.",
        dominant_purpose="capture and contextualize scientific evidence",
        local_nav=nav,
        archetype_labels=["Workflow Page", "Scientific Support Layer", "Interpretation Capture"],
        workflow_stage_emphasis="data to evidence interpretation",
        attention_mode="high",
    )


def evidence_detail_surface(*, evidence_id: int, program_id: int | None = None, molecule_id: int | None = None) -> SurfaceDescriptor:
    nav = [nav_item("Evidence", "/evidence"), nav_item("This Evidence Record", f"/evidence/{int(evidence_id)}")]
    if program_id is not None:
        nav.append(nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"))
    if molecule_id is not None:
        nav.append(nav_item("Molecule Workspace", f"/molecules/{int(molecule_id)}"))
    return workspace_surface(
        surface_key="evidence_detail",
        surface_title="Scientific Evidence Record",
        surface_subtitle="Review support statement, cited data records, and scientific scope.",
        dominant_purpose="interpret support context and navigate back to scientific workspaces",
        local_nav=nav,
        archetype_labels=["Scientific Workspace", "Interpretation Surface", "Traceability View"],
        workflow_stage_emphasis="evidence to claim/plan reasoning",
    )


def files_registry_surface() -> SurfaceDescriptor:
    return registry_surface(
        surface_key="files_registry",
        surface_title="Files",
        dominant_purpose="locate and open assay artifacts",
        local_nav=[nav_item("Files", "/files")],
        archetype_labels=["Registry Page", "Artifact Traceability"],
    )


def batches_registry_surface() -> SurfaceDescriptor:
    return registry_surface(
        surface_key="batches_registry",
        surface_title="Batches",
        dominant_purpose="scan material batches and open batch detail",
        local_nav=[nav_item("Batches", "/batches"), nav_item("New Batch", "/batches/new")],
        archetype_labels=["Registry Page", "Material Context"],
    )


def reports_registry_surface() -> SurfaceDescriptor:
    return registry_surface(
        surface_key="reports_registry",
        surface_title="Reports",
        dominant_purpose="scan generated reports and open report detail",
        local_nav=[nav_item("Reports", "/reports"), nav_item("Generate Report", "/reports/new")],
        archetype_labels=["Registry Page", "Reporting Surface"],
    )


def legacy_portfolios_registry_surface() -> SurfaceDescriptor:
    return registry_surface(
        surface_key="legacy_portfolios_registry",
        surface_title="Legacy Portfolios",
        dominant_purpose="compatibility portfolio registry and membership management",
        local_nav=[nav_item("Portfolio Intelligence", "/portfolio"), nav_item("Legacy Portfolios", "/portfolios"), nav_item("New Legacy Portfolio", "/portfolios/new")],
        archetype_labels=["Registry Page", "Legacy Surface"],
    )


def builder_home_surface() -> SurfaceDescriptor:
    return workspace_surface(
        surface_key="builder_home",
        surface_title="Molecule Builder",
        dominant_purpose="engineering workspace for deterministic derivation",
        local_nav=[
            nav_item("Builder Home", "/builder"),
            nav_item("Clone", "/builder/clone"),
            nav_item("Point Mutation", "/builder/point-mutation"),
            nav_item("CDR Builder", "/builder/cdr-builder"),
            nav_item("Variant Set", "/builder/variant-set"),
        ],
        archetype_labels=["Scientific Workspace", "Builder Operations"],
        workflow_stage_emphasis="engineering exploration",
    )


def builder_clone_surface() -> SurfaceDescriptor:
    return workspace_surface(
        surface_key="builder_clone",
        surface_title="Builder Clone",
        dominant_purpose="clone parent molecules into draft variants",
        local_nav=[nav_item("Builder Home", "/builder"), nav_item("Point Mutation", "/builder/point-mutation"), nav_item("Variant Set", "/builder/variant-set")],
        archetype_labels=["Scientific Workspace", "Draft Builder"],
    )


def builder_point_mutation_surface() -> SurfaceDescriptor:
    return workspace_surface(
        surface_key="builder_point_mutation",
        surface_title="Builder Point Mutation",
        dominant_purpose="preview deterministic residue edits",
        local_nav=[nav_item("Builder Home", "/builder"), nav_item("Clone", "/builder/clone"), nav_item("Variant Set", "/builder/variant-set")],
        archetype_labels=["Scientific Workspace", "Draft Builder"],
    )


def builder_cdr_surface() -> SurfaceDescriptor:
    return workspace_surface(
        surface_key="builder_cdr",
        surface_title="Builder CDR Scaffold",
        dominant_purpose="reconstruct drafts from CDR and scaffold assumptions",
        local_nav=[nav_item("Builder Home", "/builder"), nav_item("Clone", "/builder/clone"), nav_item("Point Mutation", "/builder/point-mutation")],
        archetype_labels=["Scientific Workspace", "Draft Builder"],
    )


def builder_variant_set_surface() -> SurfaceDescriptor:
    return workflow_surface(
        surface_key="builder_variant_set",
        surface_title="Builder Variant Set",
        dominant_purpose="design and preview deterministic variant families",
        local_nav=[nav_item("Builder Home", "/builder"), nav_item("Variant Set", "/builder/variant-set"), nav_item("Recent Variant Family", "/builder/variant-set")],
        archetype_labels=["Scientific Workspace", "Operational Instantiation"],
    )


def builder_variant_set_detail_surface(*, variant_set_id: int) -> SurfaceDescriptor:
    return workflow_surface(
        surface_key="builder_variant_set_detail",
        surface_title="Variant Family Review",
        dominant_purpose="review ordered members and jump to molecules",
        local_nav=[nav_item("Builder Home", "/builder"), nav_item("Variant Set Builder", "/builder/variant-set"), nav_item("This Variant Family", f"/builder/variant-sets/{int(variant_set_id)}")],
        archetype_labels=["Scientific Workspace", "Operational Instantiation"],
    )


def builder_suggested_task_surface(*, molecule_id: int, program_id: int | None = None) -> SurfaceDescriptor:
    nav = [nav_item("Molecule Workspace", f"/molecules/{int(molecule_id)}"), nav_item("Builder Home", "/builder")]
    if program_id is not None:
        nav.insert(1, nav_item("Program Workflow", f"/programs/{int(program_id)}/workflow"))
    return operational_surface(
        surface_key="builder_suggested_task",
        surface_title="Create Task from Suggested Experiment",
        dominant_purpose="convert suggestion into tracked operational work",
        local_nav=nav,
        archetype_labels=["Operational Page", "Execution Handoff"],
    )
