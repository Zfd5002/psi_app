from __future__ import annotations

from datetime import datetime
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.db import ensure_schema
from psi.core.models import Base, DecisionSnapshot, Molecule, MoleculeComponent, MoleculeDerivation, Program, ProgramMembership
from psi.services import molecules as molecule_svc
from psi.services.builder import (
    MoleculeBuildSpec,
    MoleculeCreateMeta,
    build_molecule_draft,
    create_molecule_from_draft,
)


def _mkdb():
    eng = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=eng)
    ensure_schema(engine_override=eng)
    SessionTmp = sessionmaker(bind=eng, future=True)
    return eng, SessionTmp


def test_build_molecule_draft_clone_is_read_only_and_valid() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="Builder-P", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="PARENT-1",
                title="Parent",
                components={"HC1": "QVQLVQSG", "LC1": "DIVLTQSP"},
            )
            before_count = int(db.query(Molecule).count())
            draft = build_molecule_draft(
                db,
                MoleculeBuildSpec(
                    mode="clone",
                    parent_molecule_id=int(parent.id),
                    new_primary_id="CHILD-1",
                    new_title="Child",
                    rationale="clone baseline",
                ),
            )
            after_count = int(db.query(Molecule).count())
            assert before_count == after_count
            assert draft.is_valid is True
            assert draft.errors == []
            assert draft.parent_primary_id == "PARENT-1"
            assert draft.components["HC1"] == "QVQLVQSG"
            assert draft.components["LC1"] == "DIVLTQSP"
            assert draft.inherited_program_id == int(p.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_create_molecule_from_draft_inserts_child_and_keeps_parent_unchanged() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="Builder-P2", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="PARENT-2",
                title="Parent2",
                components={"HC1": "AAAA", "LC1": "BBBB"},
            )
            parent_components_before = {
                str(c.role): str(c.fasta or "")
                for c in db.query(MoleculeComponent)
                .filter(MoleculeComponent.molecule_id == int(parent.id))
                .order_by(MoleculeComponent.role.asc(), MoleculeComponent.id.asc())
                .all()
            }
            draft = build_molecule_draft(
                db,
                MoleculeBuildSpec(
                    mode="clone",
                    parent_molecule_id=int(parent.id),
                    new_primary_id="CHILD-2",
                    new_title="Child2",
                ),
            )
            child = create_molecule_from_draft(db, draft, MoleculeCreateMeta(actor="tester", note="create child"))
            assert int(child.id) != int(parent.id)
            assert int(child.program_id) == int(parent.program_id)
            assert str(child.primary_id) == "CHILD-2"
            assert int(db.query(DecisionSnapshot).count()) == 0
            assert (
                int(
                    db.query(ProgramMembership)
                    .filter(ProgramMembership.molecule_id == int(child.id))
                    .count()
                )
                == 0
            )
            deriv = (
                db.query(MoleculeDerivation)
                .filter(MoleculeDerivation.child_molecule_id == int(child.id))
                .order_by(MoleculeDerivation.id.asc())
                .first()
            )
            assert deriv is not None
            assert int(deriv.parent_molecule_id) == int(parent.id)
            assert str(deriv.derivation_type) == "clone"
            child_components = {
                str(c.role): str(c.fasta or "")
                for c in db.query(MoleculeComponent)
                .filter(MoleculeComponent.molecule_id == int(child.id))
                .order_by(MoleculeComponent.role.asc(), MoleculeComponent.id.asc())
                .all()
            }
            assert child_components == parent_components_before
            parent_components_after = {
                str(c.role): str(c.fasta or "")
                for c in db.query(MoleculeComponent)
                .filter(MoleculeComponent.molecule_id == int(parent.id))
                .order_by(MoleculeComponent.role.asc(), MoleculeComponent.id.asc())
                .all()
            }
            assert parent_components_after == parent_components_before
        finally:
            db.close()
    finally:
        eng.dispose()


def test_create_molecule_from_invalid_draft_fails_without_write() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            before_count = int(db.query(Molecule).count())
            draft = build_molecule_draft(
                db,
                MoleculeBuildSpec(
                    mode="clone",
                    parent_molecule_id=999999,
                    new_primary_id="",
                ),
            )
            assert draft.is_valid is False
            try:
                create_molecule_from_draft(db, draft, MoleculeCreateMeta())
                assert False, "expected ValueError"
            except ValueError:
                pass
            after_count = int(db.query(Molecule).count())
            assert after_count == before_count
        finally:
            db.close()
    finally:
        eng.dispose()


def test_build_point_mutation_draft_applies_mutation_and_create_child() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="Builder-P3", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="PARENT-3",
                title="Parent3",
                components={"HC1": "MSGN", "LC1": "BBBB"},
            )
            draft = build_molecule_draft(
                db,
                MoleculeBuildSpec(
                    mode="point_mutation",
                    parent_molecule_id=int(parent.id),
                    new_primary_id="CHILD-3",
                    new_title="Child3",
                    operations=[{"type": "point_mutation", "component": "HC1", "mutations": "S2A N4Q"}],
                ),
            )
            assert draft.is_valid is True
            assert draft.components["HC1"] == "MAGQ"
            assert len(draft.preview_rows) == 1
            assert draft.preview_rows[0]["before"] == "MSGN"
            assert draft.preview_rows[0]["after"] == "MAGQ"
            child = create_molecule_from_draft(db, draft, MoleculeCreateMeta(actor="tester"))
            child_components = {
                str(c.role): str(c.fasta or "")
                for c in db.query(MoleculeComponent)
                .filter(MoleculeComponent.molecule_id == int(child.id))
                .order_by(MoleculeComponent.role.asc(), MoleculeComponent.id.asc())
                .all()
            }
            assert child_components["HC1"] == "MAGQ"
            deriv = (
                db.query(MoleculeDerivation)
                .filter(MoleculeDerivation.child_molecule_id == int(child.id))
                .order_by(MoleculeDerivation.id.asc())
                .first()
            )
            assert deriv is not None
            payload = json.loads(str(deriv.edit_payload_json or "{}"))
            assert str(deriv.derivation_type) == "point_mutation"
            assert payload.get("operations")[0].get("component") == "HC1"
        finally:
            db.close()
    finally:
        eng.dispose()


def test_build_point_mutation_draft_wt_mismatch_is_invalid_and_no_write() -> None:
    eng, SessionTmp = _mkdb()
    try:
        db = SessionTmp()
        try:
            now = datetime(2026, 3, 7)
            p = Program(name="Builder-P4", description="", created_at=now, updated_at=now)
            db.add(p)
            db.commit()
            db.refresh(p)
            parent = molecule_svc.create_molecule(
                db,
                program_id=int(p.id),
                primary_id="PARENT-4",
                title="Parent4",
                components={"HC1": "MSGN", "LC1": "BBBB"},
            )
            before_count = int(db.query(Molecule).count())
            draft = build_molecule_draft(
                db,
                MoleculeBuildSpec(
                    mode="point_mutation",
                    parent_molecule_id=int(parent.id),
                    new_primary_id="CHILD-4",
                    new_title="Child4",
                    operations=[{"type": "point_mutation", "component": "HC1", "mutations": "T2A"}],
                ),
            )
            assert draft.is_valid is False
            assert any("WT mismatch" in err for err in draft.errors)
            try:
                create_molecule_from_draft(db, draft, MoleculeCreateMeta(actor="tester"))
                assert False, "expected ValueError"
            except ValueError:
                pass
            assert int(db.query(Molecule).count()) == before_count
        finally:
            db.close()
    finally:
        eng.dispose()
