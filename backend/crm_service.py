"""Bounded CRM reads and SQL aggregations; no per-row lazy loading."""
from datetime import datetime, timedelta, timezone

from fastapi import HTTPException

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from .identity import Lead, Unit, utcnow

STAGES = ("new", "contacted", "qualified", "closed_lost")


def period(days: int, as_of: datetime | None = None) -> tuple[datetime, datetime]:
    if days not in (7, 30, 90):
        raise HTTPException(422, "Davr 7, 30 yoki 90 kun")
    end = as_of or utcnow()
    if end.tzinfo is None:
        end = end.replace(tzinfo=timezone.utc)
    end = end.astimezone(timezone.utc)
    return end - timedelta(days=days), end


def metrics_for(session: Session, company_id: str, days: int, as_of: datetime | None) -> dict:
    since, end = period(days, as_of)
    where = (Lead.company_id == company_id, Lead.created_at >= since, Lead.created_at <= end)
    counts = dict(session.execute(select(Lead.stage, func.count()).where(*where).group_by(Lead.stage)).all())
    step = (end - since) / 7
    expressions = []
    for i in range(7):
        lower = since + step * i
        # Division rounds to microseconds; the final bucket must end at the
        # actual cutoff used by both the total and the paginated lead list.
        upper = end if i == 6 else since + step * (i + 1)
        condition = (Lead.created_at >= lower) & ((Lead.created_at <= upper) if i == 6 else (Lead.created_at < upper))
        expressions.append(func.coalesce(func.sum(case((condition, 1), else_=0)), 0))
    bins = list(session.execute(select(*expressions).where(*where)).one())
    inventory = dict(session.execute(select(Unit.status, func.count()).where(Unit.company_id == company_id).group_by(Unit.status)).all())
    return {"days": days, "count": sum(counts.values()), "stages": {stage: counts.get(stage, 0) for stage in STAGES},
            "bins": bins, "unit_statuses": {status: inventory.get(status, 0) for status in ("available", "reserved", "sold")},
            "as_of": end.isoformat()}
