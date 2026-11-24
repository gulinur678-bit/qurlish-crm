"""Public inventory and lead intake; these routes intentionally need no login."""

import hashlib
import hmac
import re

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .identity import Idempotency, Lead, LeadEvent, Unit, add_audit, get_db, utcnow


router = APIRouter(prefix="/api/public", tags=["public inventory"])


def unit_json(unit: Unit) -> dict:
    return {
        "id": unit.id,
        "building": unit.building,
        "floor": unit.floor,
        "unit": unit.number,
        "rooms": unit.rooms,
        "area": unit.area,
        "price": unit.price,
        "status": unit.status,
    }


class LeadIn(BaseModel):
    unit_id: str = Field(min_length=1, max_length=20)
    name: str = Field(min_length=2, max_length=100)
    phone: str = Field(min_length=9, max_length=24)

    @field_validator("phone")
    @classmethod
    def valid_phone(cls, value: str) -> str:
        if not re.fullmatch(r"\+?[0-9 ()-]{9,24}", value) or len(re.sub(r"\D", "", value)) < 9:
            raise ValueError("Telefon raqamini tekshiring")
        return value.strip()


@router.get("/units")
def public_units(session: Session = Depends(get_db)):
    units = session.scalars(
        select(Unit)
        .where(Unit.company_id == settings.company_id)
        .order_by(Unit.building, Unit.floor, Unit.number)
    ).all()
    return {"units": [unit_json(unit) for unit in units]}


@router.post("/leads", status_code=201)
def create_lead(payload: LeadIn, request: Request, session: Session = Depends(get_db)):
    key = request.headers.get("Idempotency-Key", "")
    if not re.fullmatch(r"[a-zA-Z0-9-]{16,128}", key):
        raise HTTPException(400, "Idempotency-Key talab qilinadi")
    fingerprint = hashlib.sha256(payload.model_dump_json().encode()).hexdigest()

    previous = session.scalar(
        select(Idempotency).where(Idempotency.key == key, Idempotency.company_id == settings.company_id)
    )
    if previous:
        if not hmac.compare_digest(previous.payload_hash, fingerprint):
            raise HTTPException(409, "Kalit boshqa so‘rov uchun ishlatilgan")
        return {"id": previous.lead_id, "duplicate": True}

    unit = session.scalar(
        select(Unit)
        .where(Unit.id == payload.unit_id, Unit.company_id == settings.company_id)
        .with_for_update()
    )
    if unit is None:
        raise HTTPException(404, "Xonadon topilmadi")
    if unit.status != "available":
        raise HTTPException(409, "Xonadon mavjud emas")

    lead = Lead(
        unit_id=unit.id,
        name=payload.name.strip(),
        phone=payload.phone,
        company_id=settings.company_id,
        created_at=utcnow(),
    )
    session.add(lead)
    session.flush()
    session.add(Idempotency(key=key, payload_hash=fingerprint, lead_id=lead.id, company_id=settings.company_id))
    session.add(LeadEvent(lead_id=lead.id, actor="public", kind="created", value="Murojaat kelib tushdi", company_id=settings.company_id))
    add_audit(session, company_id=settings.company_id, action="lead_created", resource_type="lead", resource_id=lead.id)
    session.commit()
    return {"id": lead.id, "duplicate": False}
