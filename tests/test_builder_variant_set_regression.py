from __future__ import annotations

from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import (
    Base,
    Batch,
    BuilderVariantSet,
    BuilderVariantSetMember,
    DecisionSnapshot,
    Molecule,
    MoleculeComponent,
    Program,
    ProgramMembership,
    ReportRun,
)
from psi.services import molecules as molecule_svc
from psi.services.builder import (
    VariantSetBuildSpec,
    VariantSetCreateMeta,
    build_variant_set_draft,
    create_variant_set_from_draft,
)
from psi.services.builder_ops import build_mutation_panel_members


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_variant_set_create_isolation_and_deterministic_save_order() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="VS-R", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="M-104",
                title="Parent",
                components={"HC1": "MSGN", "LC1": "BBBB"},
            )
            parent_before = {
                str(c.role): str(c.fasta or "")
                for c in db.query(MoleculeComponent)
                .filter(MoleculeComponent.molecule_id == int(parent.id))
                .order_by(MoleculeComponent.role.asc(), MoleculeComponent.id.asc())
                .all()
            }
            baseline = {
                "memberships": int(db.query(ProgramMembership).count()),
                "snapshots": int(db.query(DecisionSnapshot).count()),
                "reports": int(db.query(ReportRun).count()),
                "batches": int(db.query(Batch).count()),
            }
            members = build_mutation_panel_members(
                mutation_tokens_text="N4Q G3L",
                include_pair_combinations=False,
                explicit_combos_text="",
            )
            draft = build_variant_set_draft(
                db,
                VariantSetBuildSpec(
                    family_type="mutation_panel",
                    parent_molecule_id=int(parent.id),
                    set_name="Cleanup",
                    naming_base="M-104",
                    members=[
                        {**members[1], "sort_index": 2},
                        {**members[0], "sort_index": 1},
                    ],
                ),
            )
            assert draft.is_valid is True
            result = create_variant_set_from_draft(db, draft, VariantSetCreateMeta(actor="tester"))
            assert int(result.variant_set_id) > 0
            created = [db.get(Molecule, int(mid)) for mid in result.molecule_ids]
            assert [str(m.primary_id) for m in created if m is not None] == ["M_104_N4Q", "M_104_G3L"]

            vset = db.get(BuilderVariantSet, int(result.variant_set_id))
            assert vset is not None
            members_rows = (
                db.query(BuilderVariantSetMember)
                .filter(BuilderVariantSetMember.variant_set_id == int(result.variant_set_id))
                .order_by(BuilderVariantSetMember.sort_index.asc(), BuilderVariantSetMember.id.asc())
                .all()
            )
            assert [str(r.member_label) for r in members_rows] == ["N4Q", "G3L"]

            after = {
                "memberships": int(db.query(ProgramMembership).count()),
                "snapshots": int(db.query(DecisionSnapshot).count()),
                "reports": int(db.query(ReportRun).count()),
                "batches": int(db.query(Batch).count()),
            }
            assert after == baseline
            parent_after = {
                str(c.role): str(c.fasta or "")
                for c in db.query(MoleculeComponent)
                .filter(MoleculeComponent.molecule_id == int(parent.id))
                .order_by(MoleculeComponent.role.asc(), MoleculeComponent.id.asc())
                .all()
            }
            assert parent_after == parent_before
        finally:
            db.close()
    finally:
        eng.dispose()


def test_variant_set_invalid_draft_cannot_create() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="VS-R2", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="M-200",
                components={"HC1": "MSGN", "LC1": "BBBB"},
            )
            draft = build_variant_set_draft(
                db,
                VariantSetBuildSpec(
                    family_type="mutation_panel",
                    parent_molecule_id=int(parent.id),
                    set_name="Bad",
                    naming_base="M-200",
                    members=[
                        {
                            "sort_index": 1,
                            "member_label": "bad",
                            "mode": "point_mutation",
                            "operations": [{"type": "point_mutation", "component": "HC1", "mutations": "Z99Q"}],
                        }
                    ],
                ),
            )
            assert draft.is_valid is False
            try:
                create_variant_set_from_draft(db, draft, VariantSetCreateMeta(actor="tester"))
                assert False, "expected ValueError"
            except ValueError:
                pass
            assert int(db.query(BuilderVariantSet).count()) == 0
            assert int(db.query(BuilderVariantSetMember).count()) == 0
        finally:
            db.close()
    finally:
        eng.dispose()
