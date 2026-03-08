from __future__ import annotations

import json

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from sqlalchemy.orm import Session

from psi.services.builder import (
    MoleculeBuildSpec,
    MoleculeCreateMeta,
    VariantSetBuildSpec,
    VariantSetCreateMeta,
    build_molecule_draft,
    build_variant_set_draft,
    create_variant_set_from_draft,
    create_molecule_from_draft,
)
from psi.services.sequence_editor import normalize_mutation_queue
from psi.services.builder_ops import (
    build_fc_panel_members,
    build_kih_panel_members,
    build_mutation_panel_members,
    build_scaffold_panel_members,
)
from psi.core.models import BuilderVariantSet, BuilderVariantSetMember, Molecule, MoleculeComponent, MoleculeDerivation, Program
from psi.services import experiment_tasks as experiment_tasks_svc
from psi.web.deps import get_db, get_templates

router = APIRouter()


def _normalize_builder_mutations(
    db: Session,
    *,
    parent_molecule_id: int,
    component_role: str,
    mutation_text: str,
) -> tuple[str, list[str]]:
    comp = (
        db.query(MoleculeComponent)
        .filter(
            MoleculeComponent.molecule_id == int(parent_molecule_id),
            MoleculeComponent.role == str(component_role),
        )
        .order_by(MoleculeComponent.id.asc())
        .first()
    )
    if comp is None:
        return str(mutation_text or "").strip(), [f"Unknown component: {component_role}"]
    queue, errors = normalize_mutation_queue(
        component_role=str(component_role),
        parent_sequence=str(comp.fasta or ""),
        clicked_mutations=[],
        direct_notation_text=str(mutation_text or ""),
    )
    canonical = " ".join(
        [f"{str(q.get('from') or '')}{int(q.get('position') or 0)}{str(q.get('to') or '')}" for q in queue]
    )
    return canonical, list(errors)


def _builder_parent_selection(db: Session) -> tuple[list[Program], dict[int, list[dict[str, object]]]]:
    programs = db.query(Program).order_by(Program.name.asc(), Program.id.asc()).all()
    molecules = (
        db.query(Molecule)
        .order_by(Molecule.program_id.asc(), Molecule.primary_id.asc(), Molecule.id.asc())
        .all()
    )
    by_program: dict[int, list[dict[str, object]]] = {}
    for m in molecules:
        pid = int(m.program_id)
        by_program.setdefault(pid, []).append(
            {
                "id": int(m.id),
                "primary_id": str(m.primary_id or ""),
                "title": str(m.title or ""),
            }
        )
    return programs, by_program


def _search_builder_molecules(db: Session, *, q: str, limit: int = 10) -> list[dict[str, object]]:
    needle = str(q or "").strip()
    if not needle:
        return []
    rows = (
        db.query(Molecule, Program)
        .join(Program, Program.id == Molecule.program_id)
        .filter(
            (Molecule.primary_id.ilike(f"%{needle}%")) | (Molecule.title.ilike(f"%{needle}%"))
        )
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .limit(int(limit))
        .all()
    )
    out: list[dict[str, object]] = []
    for m, p in rows:
        out.append(
            {
                "id": int(m.id),
                "primary_id": str(m.primary_id or ""),
                "title": str(m.title or ""),
                "program_name": str(p.name or ""),
            }
        )
    return out


@router.post("/builder/exploration-task")
def create_builder_exploration_task(
    parent_molecule_id: int = Form(...),
    task_title: str = Form("engineering_exploration"),
    notes: str = Form(""),
    action_target: str = Form("point-mutation"),
    redirect_to: str = Form(""),
    db: Session = Depends(get_db),
):
    parent = db.get(Molecule, int(parent_molecule_id))
    if parent is None:
        raise HTTPException(404)
    target = str(action_target or "point-mutation").strip().lower()
    if target not in {"point-mutation", "variant-set", "sequence-editor"}:
        target = "point-mutation"
    task = experiment_tasks_svc.create_experiment_task(
        db,
        program_id=int(parent.program_id),
        molecule_id=int(parent.id),
        metric_key=(str(task_title or "").strip() or "engineering_exploration"),
        suggested_assay=f"builder:{target}",
        source_kind="builder_exploration",
        notes=notes,
    )
    if str(redirect_to or "").strip():
        return RedirectResponse(url=str(redirect_to), status_code=303)
    if target == "variant-set":
        return RedirectResponse(url=f"/builder/variant-set?parent_molecule_id={int(parent.id)}&task_id={int(task.id)}", status_code=303)
    if target == "sequence-editor":
        return RedirectResponse(url=f"/molecules/{int(parent.id)}?task_id={int(task.id)}#sequence-editor", status_code=303)
    return RedirectResponse(url=f"/builder/point-mutation?parent_molecule_id={int(parent.id)}&task_id={int(task.id)}", status_code=303)


@router.get("/builder", response_class=HTMLResponse)
def builder_home(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    molecules = (
        db.query(Molecule)
        .order_by(Molecule.primary_id.asc(), Molecule.id.asc())
        .limit(200)
        .all()
    )
    return templates.TemplateResponse(
        "builder/index.html",
        {
            "request": request,
            "molecules": molecules,
        },
    )


@router.get("/builder/clone", response_class=HTMLResponse)
def builder_clone_page(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    parent_programs, parent_molecules_by_program = _builder_parent_selection(db)
    molecules = [m for rows in parent_molecules_by_program.values() for m in rows]
    return templates.TemplateResponse(
        "builder/clone.html",
        {
            "request": request,
            "molecules": molecules,
            "parent_programs": parent_programs,
            "parent_molecules_by_program": parent_molecules_by_program,
            "parent_molecules_by_program_json": json.dumps(parent_molecules_by_program, sort_keys=True, separators=(",", ":")),
            "draft": None,
            "form_data": {},
            "error": "",
        },
    )


@router.post("/builder/clone/draft", response_class=HTMLResponse)
async def builder_clone_build_draft(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    new_primary_id = str(form.get("new_primary_id") or "").strip()
    new_title = str(form.get("new_title") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    draft = build_molecule_draft(
        db,
        MoleculeBuildSpec(
            mode="clone",
            parent_molecule_id=parent_molecule_id,
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=rationale,
            operations=[],
        ),
    )
    parent_programs, parent_molecules_by_program = _builder_parent_selection(db)
    molecules = [m for rows in parent_molecules_by_program.values() for m in rows]
    return templates.TemplateResponse(
        "builder/clone.html",
        {
            "request": request,
            "molecules": molecules,
            "parent_programs": parent_programs,
            "parent_molecules_by_program": parent_molecules_by_program,
            "parent_molecules_by_program_json": json.dumps(parent_molecules_by_program, sort_keys=True, separators=(",", ":")),
            "draft": draft,
            "form_data": {
                "parent_molecule_id": parent_molecule_id,
                "parent_program_id": int(db.get(Molecule, parent_molecule_id).program_id) if db.get(Molecule, parent_molecule_id) is not None else None,
                "new_primary_id": new_primary_id,
                "new_title": new_title,
                "rationale": rationale,
            },
            "error": "",
        },
    )


@router.post("/builder/clone/create")
async def builder_clone_create(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    new_primary_id = str(form.get("new_primary_id") or "").strip()
    new_title = str(form.get("new_title") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    draft = build_molecule_draft(
        db,
        MoleculeBuildSpec(
            mode="clone",
            parent_molecule_id=parent_molecule_id,
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=rationale,
            operations=[],
        ),
    )
    if not draft.is_valid:
        return RedirectResponse(url="/builder/clone", status_code=303)
    try:
        m = create_molecule_from_draft(db, draft, MoleculeCreateMeta(actor="builder"))
    except ValueError:
        return RedirectResponse(url="/builder/clone", status_code=303)
    return RedirectResponse(url=f"/molecules/{int(m.id)}", status_code=303)


@router.get("/builder/point-mutation", response_class=HTMLResponse)
def builder_point_mutation_page(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    parent_programs, parent_molecules_by_program = _builder_parent_selection(db)
    molecules = [m for rows in parent_molecules_by_program.values() for m in rows]
    return templates.TemplateResponse(
        "builder/point_mutation.html",
        {
            "request": request,
            "molecules": molecules,
            "parent_programs": parent_programs,
            "parent_molecules_by_program": parent_molecules_by_program,
            "parent_molecules_by_program_json": json.dumps(parent_molecules_by_program, sort_keys=True, separators=(",", ":")),
            "draft": None,
            "form_data": {},
            "error": "",
        },
    )


@router.get("/builder/cdr-builder", response_class=HTMLResponse)
def builder_cdr_builder_page(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    parent_programs, parent_molecules_by_program = _builder_parent_selection(db)
    molecules = [m for rows in parent_molecules_by_program.values() for m in rows]
    return templates.TemplateResponse(
        "builder/cdr_builder.html",
        {
            "request": request,
            "molecules": molecules,
            "parent_programs": parent_programs,
            "parent_molecules_by_program": parent_molecules_by_program,
            "parent_molecules_by_program_json": json.dumps(parent_molecules_by_program, sort_keys=True, separators=(",", ":")),
            "draft": None,
            "form_data": {},
            "error": "",
        },
    )


@router.get("/builder/variant-set", response_class=HTMLResponse)
def builder_variant_set_page(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    parent_programs, parent_molecules_by_program = _builder_parent_selection(db)
    molecules = [m for rows in parent_molecules_by_program.values() for m in rows]
    return templates.TemplateResponse(
        "builder/variant_set.html",
        {
            "request": request,
            "molecules": molecules,
            "parent_programs": parent_programs,
            "parent_molecules_by_program": parent_molecules_by_program,
            "parent_molecules_by_program_json": json.dumps(parent_molecules_by_program, sort_keys=True, separators=(",", ":")),
            "draft": None,
            "form_data": {},
            "error": "",
        },
    )


@router.get("/builder/suggested-task/new", response_class=HTMLResponse)
def builder_suggested_task_new(
    request: Request,
    molecule_id: int,
    metric_key: str = "",
    suggested_assay: str = "",
    suggested_rationale: str = "",
    db: Session = Depends(get_db),
):
    templates = get_templates(request)
    mol = db.get(Molecule, int(molecule_id))
    if mol is None:
        raise HTTPException(404)
    return templates.TemplateResponse(
        "builder/suggested_task_new.html",
        {
            "request": request,
            "molecule": mol,
            "prefill": experiment_tasks_svc.build_task_prefill_from_suggestion(
                program_id=int(mol.program_id),
                molecule_id=int(mol.id),
                metric_key=str(metric_key or ""),
                suggested_assay=str(suggested_assay or ""),
                suggested_rationale=str(suggested_rationale or ""),
                source_kind="insight",
            ),
        },
    )


@router.post("/builder/variant-set/draft", response_class=HTMLResponse)
async def builder_variant_set_build_draft(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    family_type = str(form.get("family_type") or "mutation_panel").strip().lower()
    set_name = str(form.get("set_name") or "").strip()
    naming_base = str(form.get("naming_base") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    mutation_tokens = str(form.get("mutation_tokens") or "").strip()
    queued_component = str(form.get("queued_component") or "").strip()
    include_pairs = str(form.get("include_pair_combinations") or "").strip() in {"1", "on", "true", "True"}
    explicit_combos = str(form.get("explicit_combos") or "").strip()
    fc_presets = str(form.get("fc_presets") or "").strip()
    kih_presets = str(form.get("kih_presets") or "").strip()
    scaffold_presets = str(form.get("scaffold_presets") or "").strip()
    light_chain_type = str(form.get("light_chain_type") or "kappa").strip().lower()
    numbering_scheme = str(form.get("numbering_scheme") or "kabat").strip().lower()
    cdrs = {
        "HCDR1": str(form.get("HCDR1") or "").strip(),
        "HCDR2": str(form.get("HCDR2") or "").strip(),
        "HCDR3": str(form.get("HCDR3") or "").strip(),
        "LCDR1": str(form.get("LCDR1") or "").strip(),
        "LCDR2": str(form.get("LCDR2") or "").strip(),
        "LCDR3": str(form.get("LCDR3") or "").strip(),
    }
    members: list[dict[str, object]] = []
    if family_type == "mutation_panel":
        mutation_validation_errors: list[str] = []
        if queued_component:
            mutation_tokens, mutation_validation_errors = _normalize_builder_mutations(
                db,
                parent_molecule_id=parent_molecule_id,
                component_role=queued_component,
                mutation_text=mutation_tokens,
            )
        else:
            mutation_validation_errors = []
        members = build_mutation_panel_members(
            mutation_tokens_text=mutation_tokens,
            include_pair_combinations=include_pairs,
            explicit_combos_text=explicit_combos,
        )
    elif family_type == "fc_panel":
        members = build_fc_panel_members(presets_text=fc_presets)
    elif family_type == "kih_panel":
        members = build_kih_panel_members(kih_presets_text=kih_presets)
    elif family_type == "scaffold_panel":
        members = build_scaffold_panel_members(
            scaffold_presets_text=scaffold_presets,
            light_chain_type=light_chain_type,
            numbering_scheme=numbering_scheme,
            cdrs=cdrs,
        )
    draft = build_variant_set_draft(
        db,
        VariantSetBuildSpec(
            family_type=family_type,
            parent_molecule_id=parent_molecule_id,
            set_name=set_name,
            naming_base=naming_base,
            rationale=rationale,
            members=members,
        ),
    )
    parent_programs, parent_molecules_by_program = _builder_parent_selection(db)
    molecules = [m for rows in parent_molecules_by_program.values() for m in rows]
    parent = db.get(Molecule, parent_molecule_id)
    return templates.TemplateResponse(
        "builder/variant_set.html",
        {
            "request": request,
            "molecules": molecules,
            "parent_programs": parent_programs,
            "parent_molecules_by_program": parent_molecules_by_program,
            "parent_molecules_by_program_json": json.dumps(parent_molecules_by_program, sort_keys=True, separators=(",", ":")),
            "draft": draft,
            "form_data": {
                "family_type": family_type,
                "parent_program_id": int(parent.program_id) if parent is not None else None,
                "parent_molecule_id": parent_molecule_id,
                "set_name": set_name,
                "naming_base": naming_base,
                "rationale": rationale,
                "mutation_tokens": mutation_tokens,
                "queued_component": queued_component,
                "mutation_validation_errors": mutation_validation_errors if family_type == "mutation_panel" else [],
                "include_pair_combinations": include_pairs,
                "explicit_combos": explicit_combos,
                "fc_presets": fc_presets,
                "kih_presets": kih_presets,
                "scaffold_presets": scaffold_presets,
                "light_chain_type": light_chain_type,
                "numbering_scheme": numbering_scheme,
                **cdrs,
            },
            "error": "",
        },
    )


@router.post("/builder/variant-set/create")
async def builder_variant_set_create(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    family_type = str(form.get("family_type") or "mutation_panel").strip().lower()
    set_name = str(form.get("set_name") or "").strip()
    naming_base = str(form.get("naming_base") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    mutation_tokens = str(form.get("mutation_tokens") or "").strip()
    queued_component = str(form.get("queued_component") or "").strip()
    include_pairs = str(form.get("include_pair_combinations") or "").strip() in {"1", "on", "true", "True"}
    explicit_combos = str(form.get("explicit_combos") or "").strip()
    fc_presets = str(form.get("fc_presets") or "").strip()
    kih_presets = str(form.get("kih_presets") or "").strip()
    scaffold_presets = str(form.get("scaffold_presets") or "").strip()
    light_chain_type = str(form.get("light_chain_type") or "kappa").strip().lower()
    numbering_scheme = str(form.get("numbering_scheme") or "kabat").strip().lower()
    cdrs = {
        "HCDR1": str(form.get("HCDR1") or "").strip(),
        "HCDR2": str(form.get("HCDR2") or "").strip(),
        "HCDR3": str(form.get("HCDR3") or "").strip(),
        "LCDR1": str(form.get("LCDR1") or "").strip(),
        "LCDR2": str(form.get("LCDR2") or "").strip(),
        "LCDR3": str(form.get("LCDR3") or "").strip(),
    }
    members: list[dict[str, object]] = []
    if family_type == "mutation_panel":
        if queued_component:
            mutation_tokens, _ = _normalize_builder_mutations(
                db,
                parent_molecule_id=parent_molecule_id,
                component_role=queued_component,
                mutation_text=mutation_tokens,
            )
        members = build_mutation_panel_members(
            mutation_tokens_text=mutation_tokens,
            include_pair_combinations=include_pairs,
            explicit_combos_text=explicit_combos,
        )
    elif family_type == "fc_panel":
        members = build_fc_panel_members(presets_text=fc_presets)
    elif family_type == "kih_panel":
        members = build_kih_panel_members(kih_presets_text=kih_presets)
    elif family_type == "scaffold_panel":
        members = build_scaffold_panel_members(
            scaffold_presets_text=scaffold_presets,
            light_chain_type=light_chain_type,
            numbering_scheme=numbering_scheme,
            cdrs=cdrs,
        )
    draft = build_variant_set_draft(
        db,
        VariantSetBuildSpec(
            family_type=family_type,
            parent_molecule_id=parent_molecule_id,
            set_name=set_name,
            naming_base=naming_base,
            rationale=rationale,
            members=members,
        ),
    )
    if not draft.is_valid:
        return RedirectResponse(url="/builder/variant-set", status_code=303)
    result = create_variant_set_from_draft(db, draft, VariantSetCreateMeta(actor="builder"))
    return RedirectResponse(url=f"/builder/variant-sets/{int(result.variant_set_id)}", status_code=303)


@router.get("/builder/variant-sets/{variant_set_id}", response_class=HTMLResponse)
def builder_variant_set_detail(variant_set_id: int, request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    vset = db.get(BuilderVariantSet, int(variant_set_id))
    if vset is None:
        return RedirectResponse(url="/builder/variant-set", status_code=303)
    rows = (
        db.query(BuilderVariantSetMember, Molecule)
        .join(Molecule, Molecule.id == BuilderVariantSetMember.molecule_id)
        .filter(BuilderVariantSetMember.variant_set_id == int(variant_set_id))
        .order_by(BuilderVariantSetMember.sort_index.asc(), BuilderVariantSetMember.id.asc())
        .all()
    )
    member_rows: list[dict[str, object]] = []
    for m, mol in rows:
        deriv = (
            db.query(MoleculeDerivation)
            .filter(MoleculeDerivation.child_molecule_id == int(mol.id))
            .order_by(MoleculeDerivation.created_at.desc(), MoleculeDerivation.id.desc())
            .first()
        )
        parent_primary = ""
        if deriv is not None:
            parent = db.get(Molecule, int(deriv.parent_molecule_id))
            parent_primary = str(parent.primary_id or "") if parent is not None else ""
        member_rows.append(
            {
                "sort_index": int(m.sort_index),
                "member_label": str(m.member_label or ""),
                "member_summary": str(m.member_summary or ""),
                "molecule_id": int(mol.id),
                "primary_id": str(mol.primary_id or ""),
                "title": str(mol.title or ""),
                "parent_primary_id": parent_primary,
                "derivation_type": str(deriv.derivation_type or "") if deriv is not None else "",
            }
        )
    return templates.TemplateResponse(
        "builder/variant_set_detail.html",
        {
            "request": request,
            "variant_set": vset,
            "members": member_rows,
        },
    )


@router.post("/builder/cdr-builder/draft", response_class=HTMLResponse)
async def builder_cdr_builder_build_draft(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    new_primary_id = str(form.get("new_primary_id") or "").strip()
    new_title = str(form.get("new_title") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    op = {
        "type": "cdr_graft",
        "framework_preset": str(form.get("framework_preset") or "human_vh3_vk1").strip().lower(),
        "light_chain_type": str(form.get("light_chain_type") or "kappa").strip().lower(),
        "numbering_scheme": str(form.get("numbering_scheme") or "kabat").strip().lower(),
        "HCDR1": str(form.get("HCDR1") or "").strip(),
        "HCDR2": str(form.get("HCDR2") or "").strip(),
        "HCDR3": str(form.get("HCDR3") or "").strip(),
        "LCDR1": str(form.get("LCDR1") or "").strip(),
        "LCDR2": str(form.get("LCDR2") or "").strip(),
        "LCDR3": str(form.get("LCDR3") or "").strip(),
    }
    draft = build_molecule_draft(
        db,
        MoleculeBuildSpec(
            mode="cdr_graft",
            parent_molecule_id=parent_molecule_id,
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=rationale,
            operations=[op],
        ),
    )
    parent_programs, parent_molecules_by_program = _builder_parent_selection(db)
    molecules = [m for rows in parent_molecules_by_program.values() for m in rows]
    parent = db.get(Molecule, parent_molecule_id)
    return templates.TemplateResponse(
        "builder/cdr_builder.html",
        {
            "request": request,
            "molecules": molecules,
            "parent_programs": parent_programs,
            "parent_molecules_by_program": parent_molecules_by_program,
            "parent_molecules_by_program_json": json.dumps(parent_molecules_by_program, sort_keys=True, separators=(",", ":")),
            "draft": draft,
            "form_data": {
                "parent_program_id": int(parent.program_id) if parent is not None else None,
                "parent_molecule_id": parent_molecule_id,
                "new_primary_id": new_primary_id,
                "new_title": new_title,
                "rationale": rationale,
                **op,
            },
            "error": "",
        },
    )


@router.post("/builder/point-mutation/draft", response_class=HTMLResponse)
async def builder_point_mutation_build_draft(request: Request, db: Session = Depends(get_db)):
    templates = get_templates(request)
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    new_primary_id = str(form.get("new_primary_id") or "").strip()
    new_title = str(form.get("new_title") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    component = str(form.get("component") or "").strip()
    mutations_raw = str(form.get("mutations") or "").strip()
    queue_origin = str(form.get("queue_origin") or "").strip()
    source_primary_id = str(form.get("source_primary_id") or "").strip()
    queued_component = str(form.get("queued_component") or "").strip()
    queued_mutation_tokens = str(form.get("queued_mutation_tokens") or "").strip()
    queued_mutation_count = int(form.get("queued_mutation_count") or 0)
    mutations, mutation_validation_errors = _normalize_builder_mutations(
        db,
        parent_molecule_id=parent_molecule_id,
        component_role=component,
        mutation_text=mutations_raw,
    )
    if not mutations:
        mutations = mutations_raw
    draft = build_molecule_draft(
        db,
        MoleculeBuildSpec(
            mode="point_mutation",
            parent_molecule_id=parent_molecule_id,
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=rationale,
            operations=[{"type": "point_mutation", "component": component, "mutations": mutations}],
        ),
    )
    parent_programs, parent_molecules_by_program = _builder_parent_selection(db)
    molecules = [m for rows in parent_molecules_by_program.values() for m in rows]
    return templates.TemplateResponse(
        "builder/point_mutation.html",
        {
            "request": request,
            "molecules": molecules,
            "parent_programs": parent_programs,
            "parent_molecules_by_program": parent_molecules_by_program,
            "parent_molecules_by_program_json": json.dumps(parent_molecules_by_program, sort_keys=True, separators=(",", ":")),
            "draft": draft,
            "form_data": {
                "parent_molecule_id": parent_molecule_id,
                "parent_program_id": int(db.get(Molecule, parent_molecule_id).program_id) if db.get(Molecule, parent_molecule_id) is not None else None,
                "new_primary_id": new_primary_id,
                "new_title": new_title,
                "rationale": rationale,
                "component": component,
                "mutations": mutations,
                "queue_origin": queue_origin,
                "source_primary_id": source_primary_id,
                "queued_component": queued_component,
                "queued_mutation_tokens": queued_mutation_tokens,
                "queued_mutation_count": queued_mutation_count,
                "mutation_validation_errors": mutation_validation_errors,
            },
            "error": "",
        },
    )


@router.post("/builder/point-mutation/create")
async def builder_point_mutation_create(request: Request, db: Session = Depends(get_db)):
    form = dict(await request.form())
    parent_molecule_id = int(form.get("parent_molecule_id") or 0)
    new_primary_id = str(form.get("new_primary_id") or "").strip()
    new_title = str(form.get("new_title") or "").strip()
    rationale = str(form.get("rationale") or "").strip()
    component = str(form.get("component") or "").strip()
    mutations_raw = str(form.get("mutations") or "").strip()
    mutations, _ = _normalize_builder_mutations(
        db,
        parent_molecule_id=parent_molecule_id,
        component_role=component,
        mutation_text=mutations_raw,
    )
    if not mutations:
        mutations = mutations_raw
    draft = build_molecule_draft(
        db,
        MoleculeBuildSpec(
            mode="point_mutation",
            parent_molecule_id=parent_molecule_id,
            new_primary_id=new_primary_id,
            new_title=new_title,
            rationale=rationale,
            operations=[{"type": "point_mutation", "component": component, "mutations": mutations}],
        ),
    )
    if not draft.is_valid:
        return RedirectResponse(url="/builder/point-mutation", status_code=303)
    try:
        m = create_molecule_from_draft(db, draft, MoleculeCreateMeta(actor="builder"))
    except ValueError:
        return RedirectResponse(url="/builder/point-mutation", status_code=303)
    return RedirectResponse(url=f"/molecules/{int(m.id)}", status_code=303)


@router.get("/builder/search_molecules")
def builder_search_molecules(q: str = "", db: Session = Depends(get_db)):
    return JSONResponse(content=_search_builder_molecules(db, q=q, limit=10))
