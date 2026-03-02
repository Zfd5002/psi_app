from __future__ import annotations

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from psi.core.models import Portfolio, PortfolioMembership, Program
from psi.core.utils import now_utc
from psi.services.attribution import record_attribution_event


def list_portfolios(db: Session) -> list[Portfolio]:
    return db.query(Portfolio).order_by(Portfolio.name.asc(), Portfolio.id.asc()).all()


def get_portfolio(db: Session, portfolio_id: int) -> Portfolio | None:
    return db.get(Portfolio, portfolio_id)


def create_portfolio(db: Session, *, name: str, description: str = "") -> Portfolio:
    p = Portfolio(
        name=name.strip(),
        description=description.strip(),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    record_attribution_event(
        db,
        event_type="portfolio.create",
        entity_type="Portfolio",
        entity_id=int(p.id),
        metadata={"name": p.name},
    )
    db.commit()
    return p


def update_portfolio(db: Session, *, portfolio_id: int, name: str, description: str = "") -> Portfolio:
    p = get_portfolio(db, portfolio_id)
    if not p:
        raise KeyError("Portfolio not found")
    p.name = name.strip()
    p.description = description.strip()
    p.updated_at = now_utc()
    db.add(p)
    db.commit()
    db.refresh(p)
    record_attribution_event(
        db,
        event_type="portfolio.update",
        entity_type="Portfolio",
        entity_id=int(p.id),
        metadata={"name": p.name},
    )
    db.commit()
    return p


def get_portfolio_detail(db: Session, portfolio_id: int) -> dict:
    p = get_portfolio(db, portfolio_id)
    if not p:
        raise KeyError("Portfolio not found")
    members = (
        db.query(PortfolioMembership, Program)
        .join(Program, Program.id == PortfolioMembership.program_id)
        .filter(PortfolioMembership.portfolio_id == portfolio_id)
        .order_by(PortfolioMembership.sort_index.asc(), PortfolioMembership.id.asc())
        .all()
    )
    all_programs = db.query(Program).order_by(Program.name.asc(), Program.id.asc()).all()
    return {
        "portfolio": p,
        "portfolio_memberships": [
            {
                "membership_id": int(pm.id),
                "portfolio_id": int(pm.portfolio_id),
                "program_id": int(pm.program_id),
                "sort_index": int(pm.sort_index or 0),
                "program_name": str(pr.name or ""),
                "program_description": str(pr.description or ""),
            }
            for pm, pr in members
        ],
        "all_programs_for_membership": [
            {
                "id": int(pr.id),
                "name": str(pr.name or ""),
                "description": str(pr.description or ""),
            }
            for pr in all_programs
        ],
    }


def add_portfolio_membership(
    db: Session,
    *,
    portfolio_id: int,
    program_id: int,
    sort_index: int = 0,
) -> PortfolioMembership:
    pm = PortfolioMembership(
        portfolio_id=int(portfolio_id),
        program_id=int(program_id),
        sort_index=int(sort_index),
        created_at=now_utc(),
        updated_at=now_utc(),
    )
    db.add(pm)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError("Portfolio membership already exists or references invalid entities") from exc
    db.refresh(pm)
    record_attribution_event(
        db,
        event_type="portfolio_membership.add",
        entity_type="PortfolioMembership",
        entity_id=int(pm.id),
        metadata={"portfolio_id": int(pm.portfolio_id), "program_id": int(pm.program_id), "sort_index": int(pm.sort_index or 0)},
    )
    db.commit()
    return pm


def update_portfolio_membership(db: Session, *, membership_id: int, sort_index: int) -> PortfolioMembership:
    pm = db.get(PortfolioMembership, membership_id)
    if not pm:
        raise KeyError("Portfolio membership not found")
    pm.sort_index = int(sort_index)
    pm.updated_at = now_utc()
    db.add(pm)
    db.commit()
    db.refresh(pm)
    record_attribution_event(
        db,
        event_type="portfolio_membership.update",
        entity_type="PortfolioMembership",
        entity_id=int(pm.id),
        metadata={"sort_index": int(pm.sort_index or 0)},
    )
    db.commit()
    return pm


def remove_portfolio_membership(db: Session, *, membership_id: int) -> None:
    pm = db.get(PortfolioMembership, membership_id)
    if not pm:
        raise KeyError("Portfolio membership not found")
    pm_id = int(pm.id)
    meta = {"portfolio_id": int(pm.portfolio_id), "program_id": int(pm.program_id), "sort_index": int(pm.sort_index or 0)}
    db.delete(pm)
    db.commit()
    record_attribution_event(
        db,
        event_type="portfolio_membership.remove",
        entity_type="PortfolioMembership",
        entity_id=pm_id,
        metadata=meta,
    )
    db.commit()
