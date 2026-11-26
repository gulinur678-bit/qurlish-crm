"""Read-only inventory and administrator audit projections."""
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .auth import require_roles
from .identity import AuditLog, Unit, User, get_db
from .inventory import unit_json

router = APIRouter(tags=["workspace"])


@router.get('/api/crm/units')
def units(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
          building: str | None = Query(None, max_length=4), floor: int | None = Query(None, ge=1),
          rooms: int | None = Query(None, ge=1), status: Literal['available', 'reserved', 'sold'] | None = None,
          session: Session = Depends(get_db), user: User = Depends(require_roles('admin', 'seller', 'viewer'))):
    query = select(Unit).where(Unit.company_id == user.company_id)
    for column, value in ((Unit.building, building), (Unit.floor, floor), (Unit.rooms, rooms), (Unit.status, status)):
        if value is not None:
            query = query.where(column == value)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(query.order_by(Unit.building, Unit.floor, Unit.number, Unit.id).offset((page - 1) * page_size).limit(page_size)).all()
    facets = session.execute(select(Unit.building, Unit.floor, Unit.rooms).where(Unit.company_id == user.company_id).distinct()).all()
    return {'units': [unit_json(row) for row in rows], 'total': total, 'page': page, 'page_size': page_size,
            'filters': {'buildings': sorted({r.building for r in facets}), 'floors': sorted({r.floor for r in facets}), 'rooms': sorted({r.rooms for r in facets})}}


@router.get('/api/admin/audit')
def audit(page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100),
          session: Session = Depends(get_db), user: User = Depends(require_roles('admin'))):
    query = select(AuditLog).where(AuditLog.company_id == user.company_id)
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = session.scalars(query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc()).offset((page - 1) * page_size).limit(page_size)).all()
    # Deliberately exclude raw details, hashes and session identifiers.
    return {'items': [{'id': row.id, 'user_id': row.user_id, 'action': row.action,
                       'resource_type': row.resource_type,
                       'resource_id': row.resource_id if row.resource_type in ('lead', 'unit', 'user') else None,
                       'created_at': row.created_at.isoformat()} for row in rows],
            'total': total, 'page': page, 'page_size': page_size}
