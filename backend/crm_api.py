"""Authenticated CRM lead, history and metrics endpoints."""

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .crm_service import metrics_for, period
from .identity import Lead, LeadEvent, Unit, User, add_audit, get_db
from .inventory import unit_json


router = APIRouter(prefix="/api/crm", tags=["crm"])
STAGES = ("new", "contacted", "qualified", "closed_lost")
READ_ROLES = ("admin", "seller", "viewer")
WRITE_ROLES = ("admin", "seller")


class StageIn(BaseModel):
    stage: Literal["new", "contacted", "qualified", "closed_lost"]


class NoteIn(BaseModel):
    note: str = Field(min_length=1, max_length=1000)


def lead_json(lead: Lead) -> dict:
    return {
        "id": lead.id,
        "unit_id": lead.unit_id,
        "name": lead.name,
        "phone": lead.phone,
        "stage": lead.stage,
        "created_at": lead.created_at.isoformat(),
    }


def _lead_or_404(session: Session, lead_id: int, company_id: str) -> Lead:
    lead = session.scalar(select(Lead).where(Lead.id == lead_id, Lead.company_id == company_id))
    if lead is None:
        raise HTTPException(404, "Murojaat topilmadi")
    return lead


@router.get("/me")
def me(user: User = Depends(get_current_user)):
    return {"id": user.id, "email": user.email, "role": user.role}


@router.get("/leads")
def leads(days: int = 30, page: int | None = Query(None, ge=1),
          page_size: int = Query(25, ge=1, le=100), q: str = Query("", max_length=100),
          stage: Literal["new", "contacted", "qualified", "closed_lost"] | None = None,
          sort: Literal["newest", "oldest", "name"] = "newest", as_of: datetime | None = None,
          session: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    since, end = period(days, as_of)
    query = select(Lead).where(Lead.company_id == user.company_id, Lead.created_at >= since, Lead.created_at <= end)
    if q.strip():
        query = query.where(or_(Lead.name.contains(q.strip(), autoescape=True), Lead.phone.contains(q.strip(), autoescape=True), Lead.unit_id.contains(q.strip(), autoescape=True)))
    if stage:
        query = query.where(Lead.stage == stage)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    ordering = {"newest": Lead.created_at.desc(), "oldest": Lead.created_at.asc(), "name": Lead.name.asc()}
    query = query.order_by(ordering[sort], Lead.id.desc())
    if page is not None:
        query = query.offset((page - 1) * page_size).limit(page_size)
    rows = session.scalars(query).all()
    return {"days": days, "leads": [lead_json(lead) for lead in rows], "total": total,
            "page": page or 1, "page_size": page_size, "as_of": end.isoformat()}


@router.get("/metrics")
def metrics(days: int = 30, as_of: datetime | None = None,
            session: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    return metrics_for(session, user.company_id, days, as_of)


@router.get("/leads/{lead_id}/detail")
def lead_detail(lead_id: int, session: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    lead = _lead_or_404(session, lead_id, user.company_id)
    unit = session.scalar(select(Unit).where(Unit.id == lead.unit_id, Unit.company_id == user.company_id))
    return {"lead": lead_json(lead), "unit": unit_json(unit) if unit else None}


@router.patch("/leads/{lead_id}/stage")
def change_stage(
    lead_id: int,
    payload: StageIn,
    session: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    lead = _lead_or_404(session, lead_id, user.company_id)
    old = lead.stage
    lead.stage = payload.stage
    session.add(LeadEvent(lead_id=lead.id, actor=user.email, kind="stage", value=f"{old} -> {lead.stage}", company_id=user.company_id))
    add_audit(session, company_id=user.company_id, user_id=user.id, action="lead_stage_changed", resource_type="lead", resource_id=lead.id, details={"from": old, "to": lead.stage})
    session.commit()
    return lead_json(lead)


@router.get("/leads/{lead_id}/events")
def get_events(lead_id: int, session: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    _lead_or_404(session, lead_id, user.company_id)
    events = session.scalars(
        select(LeadEvent)
        .where(LeadEvent.lead_id == lead_id, LeadEvent.company_id == user.company_id)
        .order_by(LeadEvent.created_at)
    ).all()
    return [
        {"kind": event.kind, "actor": event.actor, "value": event.value, "created_at": event.created_at.isoformat()}
        for event in events
    ]


@router.post("/leads/{lead_id}/notes", status_code=201)
def add_note(
    lead_id: int,
    payload: NoteIn,
    session: Session = Depends(get_db),
    user: User = Depends(require_roles(*WRITE_ROLES)),
):
    lead = _lead_or_404(session, lead_id, user.company_id)
    session.add(LeadEvent(lead_id=lead.id, actor=user.email, kind="internal_note", value=payload.note, company_id=user.company_id))
    add_audit(session, company_id=user.company_id, user_id=user.id, action="lead_note_added", resource_type="lead", resource_id=lead.id)
    session.commit()
    return {"ok": True}
