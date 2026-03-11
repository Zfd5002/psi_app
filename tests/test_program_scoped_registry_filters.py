from __future__ import annotations

from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from psi.core.models import Batch, DataRecord, DecisionSnapshot, Evidence, Molecule, Program
from psi.core.models import ScientificClaim, ScientificPlan
from psi.web.routers import claims as claims_router
from psi.web.routers import data_records as data_router
from psi.web.routers import decisions as decisions_router
from psi.web.routers import evidence as evidence_router
from psi.web.routers import molecules as molecules_router
from psi.web.routers import plans as plans_router


def _seed_scope(db):
    now = datetime(2026, 3, 9)
    p1 = Program(name="P-Scoped-1", created_at=now, updated_at=now)
    p2 = Program(name="P-Scoped-2", created_at=now, updated_at=now)
    db.add_all([p1, p2])
    db.commit()
    db.refresh(p1)
    db.refresh(p2)

    m1 = Molecule(program_id=int(p1.id), primary_id="M-S1", title="m1", created_at=now, updated_at=now)
    m2 = Molecule(program_id=int(p2.id), primary_id="M-S2", title="m2", created_at=now, updated_at=now)
    db.add_all([m1, m2])
    db.commit()
    db.refresh(m1)
    db.refresh(m2)

    b1 = Batch(molecule_id=int(m1.id), batch_id="B-S1", title="b1", created_at=now, updated_at=now)
    b2 = Batch(molecule_id=int(m2.id), batch_id="B-S2", title="b2", created_at=now, updated_at=now)
    db.add_all([b1, b2])
    db.commit()
    db.refresh(b1)
    db.refresh(b2)

    d1 = DataRecord(
        program_id=int(p1.id),
        molecule_id=int(m1.id),
        batch_id=int(b1.id),
        domain="Biological",
        data_type="Binding",
        method="SPR",
        title="D-S1",
        params_json="{}",
        results_json="{}",
        raw_inputs_json="{}",
        derived_outputs_json="{}",
        created_at=now,
        updated_at=now,
    )
    d2 = DataRecord(
        program_id=int(p2.id),
        molecule_id=int(m2.id),
        batch_id=int(b2.id),
        domain="Biological",
        data_type="Binding",
        method="SPR",
        title="D-S2",
        params_json="{}",
        results_json="{}",
        raw_inputs_json="{}",
        derived_outputs_json="{}",
        created_at=now,
        updated_at=now,
    )
    db.add_all([d1, d2])

    e1 = Evidence(
        program_id=int(p1.id),
        molecule_id=int(m1.id),
        batch_id=int(b1.id),
        domain="Biological",
        evidence_type="binding_support",
        strength=70,
        summary="e1",
        created_at=now,
        updated_at=now,
    )
    e2 = Evidence(
        program_id=int(p2.id),
        molecule_id=int(m2.id),
        batch_id=int(b2.id),
        domain="Biological",
        evidence_type="binding_support",
        strength=70,
        summary="e2",
        created_at=now,
        updated_at=now,
    )
    db.add_all([e1, e2])

    c1 = ScientificClaim(
        scope_type="molecule",
        molecule_id=int(m1.id),
        program_id=int(p1.id),
        title="C-S1",
        claim_type="mechanism",
        statement="c1",
        status="hypothesis",
        confidence_level="low",
        created_at=now,
        updated_at=now,
    )
    c2 = ScientificClaim(
        scope_type="molecule",
        molecule_id=int(m2.id),
        program_id=int(p2.id),
        title="C-S2",
        claim_type="mechanism",
        statement="c2",
        status="hypothesis",
        confidence_level="low",
        created_at=now,
        updated_at=now,
    )
    db.add_all([c1, c2])
    db.commit()
    db.refresh(c1)
    db.refresh(c2)

    pl1 = ScientificPlan(
        scope_type="molecule",
        molecule_id=int(m1.id),
        program_id=int(p1.id),
        claim_id=int(c1.id),
        title="P-S1",
        plan_type="readiness_advancement",
        status="draft",
        created_at=now,
        updated_at=now,
    )
    pl2 = ScientificPlan(
        scope_type="molecule",
        molecule_id=int(m2.id),
        program_id=int(p2.id),
        claim_id=int(c2.id),
        title="P-S2",
        plan_type="readiness_advancement",
        status="draft",
        created_at=now,
        updated_at=now,
    )
    db.add_all([pl1, pl2])

    s1 = DecisionSnapshot(
        program_id=int(p1.id),
        molecule_id=int(m1.id),
        batch_id=int(b1.id),
        decision_key="advance",
        rules_version="test",
        inputs_json="{}",
        outputs_json="{}",
        evidence_ids_json="[]",
        created_at=now,
    )
    s2 = DecisionSnapshot(
        program_id=int(p2.id),
        molecule_id=int(m2.id),
        batch_id=int(b2.id),
        decision_key="advance",
        rules_version="test",
        inputs_json="{}",
        outputs_json="{}",
        evidence_ids_json="[]",
        created_at=now,
    )
    db.add_all([s1, s2])
    db.commit()

    return {"p1": p1, "p2": p2}


def test_molecules_route_respects_program_filter(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            ids = _seed_scope(db)
            monkeypatch.setattr(molecules_router, "get_templates", lambda _request: dummy_templates)
            resp = molecules_router.list_molecules(
                request=SimpleNamespace(query_params={}),
                program_id=int(ids["p1"].id),
                db=db,
            )
            rows = list(resp.context.get("molecules") or [])
            assert len(rows) == 1
            assert int(rows[0].program_id) == int(ids["p1"].id)
            assert int(resp.context["active_program"].id) == int(ids["p1"].id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_data_route_respects_program_filter(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            ids = _seed_scope(db)
            monkeypatch.setattr(data_router, "get_templates", lambda _request: dummy_templates)
            resp = data_router.list_data(
                request=SimpleNamespace(query_params={}),
                program_id=int(ids["p2"].id),
                db=db,
            )
            rows = list(resp.context.get("records") or [])
            assert len(rows) == 1
            assert int(rows[0].program_id) == int(ids["p2"].id)
            assert int(resp.context["active_program"].id) == int(ids["p2"].id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_data_route_respects_molecule_filter(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            ids = _seed_scope(db)
            m1 = db.query(Molecule).filter(Molecule.program_id == int(ids["p1"].id)).order_by(Molecule.id.asc()).first()
            assert m1 is not None
            monkeypatch.setattr(data_router, "get_templates", lambda _request: dummy_templates)
            resp = data_router.list_data(
                request=SimpleNamespace(query_params={}),
                molecule_id=int(m1.id),
                db=db,
            )
            rows = list(resp.context.get("records") or [])
            assert len(rows) == 1
            assert int(rows[0].molecule_id) == int(m1.id)
            assert int(resp.context["active_molecule"].id) == int(m1.id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_evidence_route_respects_program_filter(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            ids = _seed_scope(db)
            monkeypatch.setattr(evidence_router, "get_templates", lambda _request: dummy_templates)
            resp = evidence_router.list_evidence(
                request=SimpleNamespace(query_params={}),
                program_id=int(ids["p1"].id),
                db=db,
                rules_path=Path(__file__).resolve().parents[1] / "psi_rules" / "psirules-0.1.0.yml",
            )
            rows = list(resp.context.get("evidence") or [])
            assert len(rows) == 1
            assert int(rows[0].program_id) == int(ids["p1"].id)
            assert int(resp.context["active_program"].id) == int(ids["p1"].id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_decisions_route_respects_program_filter(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            ids = _seed_scope(db)
            monkeypatch.setattr(decisions_router, "get_templates", lambda _request: dummy_templates)
            resp = decisions_router.list_decisions(
                request=SimpleNamespace(query_params={}),
                program_id=int(ids["p2"].id),
                db=db,
            )
            rows = list(resp.context.get("snaps") or [])
            assert len(rows) == 1
            assert int(rows[0].program_id) == int(ids["p2"].id)
            assert int(resp.context["active_program"].id) == int(ids["p2"].id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_claims_route_respects_program_filter(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            ids = _seed_scope(db)
            monkeypatch.setattr(claims_router, "get_templates", lambda _request: dummy_templates)
            resp = claims_router.claims_list(
                request=SimpleNamespace(query_params={}),
                program_id=int(ids["p1"].id),
                db=db,
            )
            rows = list(resp.context.get("claims") or [])
            assert len(rows) == 1
            assert int(rows[0].program_id) == int(ids["p1"].id)
            assert int(resp.context["active_program"].id) == int(ids["p1"].id)
        finally:
            db.close()
    finally:
        eng.dispose()


def test_plans_route_respects_program_filter(mkdb, dummy_templates, monkeypatch) -> None:
    eng, SessionTmp = mkdb()
    try:
        db = SessionTmp()
        try:
            ids = _seed_scope(db)
            monkeypatch.setattr(plans_router, "get_templates", lambda _request: dummy_templates)
            resp = plans_router.plans_list(
                request=SimpleNamespace(query_params={}),
                program_id=int(ids["p2"].id),
                db=db,
            )
            rows = list(resp.context.get("plans") or [])
            assert len(rows) == 1
            assert int(rows[0].program_id) == int(ids["p2"].id)
            assert int(resp.context["active_program"].id) == int(ids["p2"].id)
        finally:
            db.close()
    finally:
        eng.dispose()
