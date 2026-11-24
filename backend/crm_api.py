"""Authenticated CRM lead, history and metrics endpoints."""

from datetime import timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import get_current_user, require_roles
from .config import settings
from .identity import Lead, LeadEvent, Unit, User, add_audit, get_db, utcnow
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
def leads(days: int = 30, session: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    if days not in (7, 30, 90):
        raise HTTPException(422, "Davr 7, 30 yoki 90 kun")
    since = utcnow() - timedelta(days=days)
    rows = session.scalars(
        select(Lead)
        .where(Lead.company_id == user.company_id, Lead.created_at >= since)
        .order_by(Lead.created_at.desc())
    ).all()
    return {"days": days, "leads": [lead_json(lead) for lead in rows]}


@router.get("/metrics")
def metrics(days: int = 30, session: Session = Depends(get_db), user: User = Depends(require_roles(*READ_ROLES))):
    if days not in (7, 30, 90):
        raise HTTPException(422, "Davr 7, 30 yoki 90 kun")
    now = utcnow()
    since = now - timedelta(days=days)
    rows = session.scalars(
        select(Lead).where(Lead.company_id == user.company_id, Lead.created_at >= since)
    ).all()
    counts = {stage: sum(lead.stage == stage for lead in rows) for stage in STAGES}
    bins = [0] * 7
    interval = max(1, (now - since).total_seconds())
    for lead in rows:
        created = lead.created_at.replace(tzinfo=timezone.utc) if lead.created_at.tzinfo is None else lead.created_at
        elapsed = created - since
        index = min(6, max(0, int(elapsed.total_seconds() / interval * 7)))
        bins[index] += 1
    statuses = {
        status: session.scalar(
            select(func.count()).select_from(Unit).where(Unit.company_id == user.company_id, Unit.status == status)
        ) or 0
        for status in ("available", "reserved", "sold")
    }
    return {
        "days": days,
        "count": len(rows),
        "stages": counts,
        "bins": bins,
        "unit_statuses": statuses,
        "as_of": now.isoformat(),
    }


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
