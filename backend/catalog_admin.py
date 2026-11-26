"""Administrator-only inventory and staff account management."""

import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from .auth import hash_password, require_roles
from .identity import RefreshSession, Unit, User, add_audit, get_security_db, utcnow
from .inventory import unit_json


router = APIRouter(tags=["catalog administration"])


class UnitStatusIn(BaseModel):
    status: Literal["available", "reserved", "sold"]


class UserCreate(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=12, max_length=256)
    role: Literal["admin", "seller", "viewer"]

    @field_validator("email")
    @classmethod
    def valid_email(cls, value: str) -> str:
        normalized = value.strip().lower()
        if not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", normalized):
            raise ValueError("Email manzilini tekshiring")
        return normalized


class UserUpdate(BaseModel):
    role: Literal["admin", "seller", "viewer"] | None = None
    is_active: bool | None = None


def _public_user(user: User) -> dict:
    return {"id": user.id, "email": user.email, "role": user.role, "is_active": user.is_active, "created_at": user.created_at.isoformat()}


def _ensure_another_active_admin(session: Session, target: User, update_role: str | None, update_active: bool | None) -> None:
    will_remain_admin = (update_role or target.role) == "admin" and (update_active if update_active is not None else target.is_active)
    if target.role == "admin" and target.is_active and not will_remain_admin:
        active_admins = session.scalar(
            select(func.count()).select_from(User).where(
                User.company_id == target.company_id,
                User.role == "admin",
                User.is_active.is_(True),
            )
        ) or 0
        if active_admins <= 1:
            raise HTTPException(409, "Oxirgi faol administratorni o‘chirish yoki rolini almashtirish mumkin emas")


@router.get("/api/admin/users")
def list_users(page: int | None = Query(None, ge=1), page_size: int = Query(25, ge=1, le=100),
               q: str = Query("", max_length=100), session: Session = Depends(get_security_db),
               user: User = Depends(require_roles("admin"))):
    query = select(User).where(User.company_id == user.company_id)
    if q.strip():
        query = query.where(User.email.contains(q.strip(), autoescape=True))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    query = query.order_by(User.email, User.id)
    if page is not None:
        query = query.offset((page - 1) * page_size).limit(page_size)
    rows = session.scalars(query).all()
    return {"users": [_public_user(row) for row in rows], "total": total, "page": page or 1}


@router.post("/api/admin/users", status_code=201)
def create_user(payload: UserCreate, session: Session = Depends(get_security_db), actor: User = Depends(require_roles("admin"))):
    if session.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(409, "Bu email bilan hisob mavjud")
    created = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        role=payload.role,
        is_active=True,
        company_id=actor.company_id,
    )
    session.add(created)
    session.flush()
    add_audit(session, company_id=actor.company_id, user_id=actor.id, action="user_created", resource_type="user", resource_id=created.id, details={"role": created.role})
    session.commit()
    return _public_user(created)


@router.patch("/api/admin/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    session: Session = Depends(get_security_db),
    actor: User = Depends(require_roles("admin")),
):
    target = session.scalar(select(User).where(User.id == user_id, User.company_id == actor.company_id))
    if target is None:
        raise HTTPException(404, "Xodim topilmadi")
    changes = payload.model_dump(exclude_unset=True)
    new_role = changes.get("role")
    new_active = changes.get("is_active")
    _ensure_another_active_admin(session, target, new_role, new_active)
    if target.id == actor.id and new_active is False:
        raise HTTPException(409, "Joriy hisobni o‘zingiz deaktivatsiya qila olmaysiz")

    role_changed = new_role is not None and new_role != target.role
    active_changed = new_active is not None and new_active != target.is_active
    if new_role is not None:
        target.role = new_role
    if new_active is not None:
        target.is_active = new_active
    if role_changed or active_changed:
        now = utcnow()
        session.execute(
            update(RefreshSession)
            .where(RefreshSession.user_id == target.id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
    add_audit(
        session,
        company_id=actor.company_id,
        user_id=actor.id,
        action="user_updated" if target.is_active else "user_deactivated",
        resource_type="user",
        resource_id=target.id,
        details={"role": target.role, "is_active": target.is_active},
    )
    session.commit()
    return _public_user(target)


@router.patch("/api/crm/units/{unit_id}")
def change_unit(
    unit_id: str,
    payload: UnitStatusIn,
    session: Session = Depends(get_security_db),
    user: User = Depends(require_roles("admin")),
):
    unit = session.scalar(select(Unit).where(Unit.id == unit_id, Unit.company_id == user.company_id))
    if unit is None:
        raise HTTPException(404, "Xonadon topilmadi")
    if payload.status == "sold" or unit.status == "sold":
        raise HTTPException(409, "Sotuvni tasdiqlash jarayoni hali ishlab chiqilmagan")
    old = unit.status
    unit.status = payload.status
    add_audit(session, company_id=user.company_id, user_id=user.id, action="unit_status_changed", resource_type="unit", resource_id=unit.id, details={"from": old, "to": unit.status})
    session.commit()
    return unit_json(unit)
