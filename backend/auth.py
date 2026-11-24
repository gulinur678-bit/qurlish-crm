"""Login, short-lived access tokens, rotating refresh sessions and RBAC."""

from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field
from sqlalchemy import exists, select, update
from sqlalchemy.orm import Session

from .config import settings
from .identity import RefreshSession, User, add_audit, get_security_db, utcnow


router = APIRouter(prefix="/api/auth", tags=["authentication"])
bearer = HTTPBearer(auto_error=False)
password_hasher = PasswordHasher()
_DUMMY_PASSWORD_HASH = password_hasher.hash("constant-time-login-placeholder")
REFRESH_COOKIE = "qurlish_refresh"
REFRESH_COOKIE_PATH = "/api/auth"


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def _require_secret() -> str:
    if len(settings.jwt_secret) < 32:
        raise HTTPException(status_code=503, detail="Server JWT_SECRET sozlanmagan")
    return settings.jwt_secret


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def _user_json(user: User) -> dict:
    return {"id": user.id, "email": user.email, "role": user.role}


def _issue_access(user: User, family_id: str) -> str:
    now = utcnow()
    return jwt.encode(
        {
            "sub": str(user.id),
            "sid": family_id,
            "jti": str(uuid4()),
            "company_id": user.company_id,
            "iat": now,
            "exp": now + timedelta(seconds=settings.access_token_seconds),
        },
        _require_secret(),
        algorithm="HS256",
    )


def _set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    remaining = max(0, int((_as_utc(expires_at) - utcnow()).total_seconds()))
    response.set_cookie(
        REFRESH_COOKIE,
        token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=remaining,
        path=REFRESH_COOKIE_PATH,
    )


def _new_refresh_session(user: User, family_id: str, expires_at: datetime) -> tuple[RefreshSession, str]:
    raw = secrets.token_urlsafe(48)
    row = RefreshSession(
        id=str(uuid4()),
        family_id=family_id,
        token_hash=_token_hash(raw),
        user_id=user.id,
        company_id=user.company_id,
        expires_at=expires_at,
    )
    return row, raw


def _token_response(user: User, family_id: str) -> dict:
    return {
        "access_token": _issue_access(user, family_id),
        "token_type": "bearer",
        "expires_in": settings.access_token_seconds,
        "user": _user_json(user),
    }


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    password: str = Field(min_length=1, max_length=256)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_security_db),
) -> User:
    if credentials is None:
        raise HTTPException(401, "Login talab qilinadi", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(
            credentials.credentials,
            _require_secret(),
            algorithms=["HS256"],
            options={"require": ["exp", "sub", "sid", "company_id"]},
        )
        user_id = int(payload["sub"])
        family_id = str(payload["sid"])
    except HTTPException:
        raise
    except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
        raise HTTPException(401, "Sessiya tugagan", headers={"WWW-Authenticate": "Bearer"})

    user = session.get(User, user_id)
    now = utcnow()
    active_session = session.scalar(
        select(exists().where(
            RefreshSession.family_id == family_id,
            RefreshSession.user_id == user_id,
            RefreshSession.company_id == settings.company_id,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > now,
        ))
    )
    if (
        user is None
        or not user.is_active
        or user.company_id != settings.company_id
        or payload.get("company_id") != user.company_id
        or not active_session
    ):
        raise HTTPException(401, "Sessiya tugagan", headers={"WWW-Authenticate": "Bearer"})
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise HTTPException(403, "Bu amal uchun ruxsat yo‘q")
        return user

    return dependency


@router.post("/login")
def login(payload: LoginIn, response: Response, session: Session = Depends(get_security_db)):
    _require_secret()
    email = payload.email.strip().lower()
    user = session.scalar(select(User).where(User.email == email, User.company_id == settings.company_id))
    password_valid = verify_password(payload.password, user.password_hash if user is not None else _DUMMY_PASSWORD_HASH)
    if user is None or not user.is_active or not password_valid:
        add_audit(session, company_id=settings.company_id, action="login_failed", resource_type="auth")
        session.commit()
        raise HTTPException(401, "Email yoki parol noto‘g‘ri")

    family_id = str(uuid4())
    expires_at = utcnow() + timedelta(seconds=settings.refresh_token_seconds)
    refresh_row, raw_refresh = _new_refresh_session(user, family_id, expires_at)
    session.add(refresh_row)
    add_audit(session, company_id=user.company_id, user_id=user.id, action="login_succeeded", resource_type="auth")
    session.commit()
    _set_refresh_cookie(response, raw_refresh, expires_at)
    return _token_response(user, family_id)


@router.post("/refresh")
def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    session: Session = Depends(get_security_db),
):
    _require_secret()
    if not refresh_token:
        raise HTTPException(401, "Refresh sessiyasi topilmadi")
    row = session.scalar(
        select(RefreshSession)
        .where(RefreshSession.token_hash == _token_hash(refresh_token), RefreshSession.company_id == settings.company_id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(401, "Refresh sessiyasi yaroqsiz")

    now = utcnow()
    user = session.get(User, row.user_id)
    replayed = row.used_at is not None
    expired = _as_utc(row.expires_at) <= now
    if replayed:
        session.execute(
            update(RefreshSession)
            .where(RefreshSession.family_id == row.family_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        add_audit(session, company_id=row.company_id, user_id=row.user_id, action="refresh_reuse_detected", resource_type="auth_session", resource_id=row.family_id)
        session.commit()
        raise HTTPException(401, "Refresh token qayta ishlatilgan; sessiya bekor qilindi")
    if row.revoked_at is not None or expired or user is None or not user.is_active or user.company_id != settings.company_id:
        if row.revoked_at is None:
            session.execute(
                update(RefreshSession)
                .where(RefreshSession.family_id == row.family_id, RefreshSession.revoked_at.is_(None))
                .values(revoked_at=now)
            )
            session.commit()
        raise HTTPException(401, "Refresh sessiyasi bekor qilingan yoki tugagan")

    replacement, raw_refresh = _new_refresh_session(user, row.family_id, _as_utc(row.expires_at))
    claimed = session.execute(
        update(RefreshSession)
        .where(RefreshSession.id == row.id, RefreshSession.used_at.is_(None), RefreshSession.revoked_at.is_(None))
        .values(used_at=now, replaced_by_id=replacement.id)
    )
    if claimed.rowcount != 1:
        # Defense in depth: a token must have exactly one successor.
        session.rollback()
        raise HTTPException(401, "Refresh sessiyasi o‘zgargan")
    session.add(replacement)
    add_audit(session, company_id=user.company_id, user_id=user.id, action="refresh_rotated", resource_type="auth_session", resource_id=row.family_id)
    session.commit()
    _set_refresh_cookie(response, raw_refresh, row.expires_at)
    return _token_response(user, row.family_id)


@router.post("/logout")
def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE),
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_security_db),
):
    families: set[tuple[str, int]] = set()
    if refresh_token:
        row = session.scalar(select(RefreshSession).where(RefreshSession.token_hash == _token_hash(refresh_token), RefreshSession.company_id == settings.company_id))
        if row is not None:
            families.add((row.family_id, row.user_id))
    if credentials:
        try:
            payload = jwt.decode(credentials.credentials, _require_secret(), algorithms=["HS256"],
                                 options={"require": ["exp", "sub", "sid", "company_id"]})
            if payload["company_id"] == settings.company_id:
                families.add((str(payload["sid"]), int(payload["sub"])))
        except (jwt.InvalidTokenError, KeyError, TypeError, ValueError):
            pass  # Logout is idempotent; an invalid bearer never selects a session.
    for family_id, user_id in families:
        changed = session.execute(
            update(RefreshSession)
            .where(RefreshSession.family_id == family_id, RefreshSession.user_id == user_id,
                   RefreshSession.company_id == settings.company_id, RefreshSession.revoked_at.is_(None))
            .values(revoked_at=utcnow())
        )
        if changed.rowcount:
            add_audit(session, company_id=settings.company_id, user_id=user_id, action="logout", resource_type="auth_session", resource_id=family_id)
    session.commit()
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH, httponly=True, secure=settings.cookie_secure, samesite="strict")
    return {"ok": True}
