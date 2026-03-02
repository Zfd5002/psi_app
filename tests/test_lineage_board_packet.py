from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from psi.core.models import Base, Portfolio, PortfolioMembership, Program
from psi.core.utils import stable_json_dumps
from psi.services.lineage import get_portfolio_lineage_board_packet, get_program_lineage_board_packet


def test_lineage_board_packets_are_fixed_schema_and_deterministic() -> None:
    eng = create_engine("sqlite:///:memory:", future=True)
    try:
        Base.metadata.create_all(bind=eng)
        SessionTmp = sessionmaker(bind=eng, future=True)
        db = SessionTmp()
        try:
            p = Program(name="P")
            db.add(p)
            db.flush()
            pf = Portfolio(name="PF")
            db.add(pf)
            db.flush()
            db.add(PortfolioMembership(portfolio_id=int(pf.id), program_id=int(p.id), sort_index=0))
            db.commit()
            a1 = get_program_lineage_board_packet(db, program_id=int(p.id))
            a2 = get_program_lineage_board_packet(db, program_id=int(p.id))
            b1 = get_portfolio_lineage_board_packet(db, portfolio_id=int(pf.id))
            b2 = get_portfolio_lineage_board_packet(db, portfolio_id=int(pf.id))
        finally:
            db.close()
    finally:
        eng.dispose()

    assert stable_json_dumps(a1) == stable_json_dumps(a2)
    assert stable_json_dumps(b1) == stable_json_dumps(b2)
    assert list(a1.keys()) == [
        "schema_id",
        "schema_version",
        "program_id",
        "rollups",
        "report_history",
        "membership_state",
        "change_surfaces",
        "policy_upgrade_warnings",
    ]
    assert list(b1.keys()) == [
        "schema_id",
        "schema_version",
        "portfolio_id",
        "portfolio_name",
        "membership_state",
        "governance_changes",
        "policy_upgrade_warnings",
        "child_program_lineage_summary",
    ]

