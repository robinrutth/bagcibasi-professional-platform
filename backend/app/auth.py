from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import uuid4

from fastapi import Depends, Header, HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import RefreshToken, RevokedToken, User

REFRESH_TOKEN_DAYS = 14
settings = get_settings()

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, stored_hash: str) -> bool:
    return pwd_context.verify(password, stored_hash)


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(user: User) -> str:
    jti = str(uuid4())
    exp = now_utc() + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {
        "sub": user.username,
        "uid": str(user.id),
        "role": user.role,
        "typ": "access",
        "jti": jti,
        "exp": int(exp.timestamp()),
        "iat": int(now_utc().timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.algorithm)


def create_refresh_token(db: Session, user: User) -> str:
    jti = str(uuid4())
    exp = now_utc() + timedelta(days=REFRESH_TOKEN_DAYS)
    payload = {
        "sub": user.username,
        "uid": str(user.id),
        "typ": "refresh",
        "jti": jti,
        "exp": int(exp.timestamp()),
        "iat": int(now_utc().timestamp()),
    }
    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.algorithm)
    db.add(
        RefreshToken(
            user_id=user.id,
            token_jti=jti,
            token_hash=_token_hash(token),
            expires_at=exp.replace(tzinfo=None),
        )
    )
    db.commit()
    return token


def decode_token(token: str, expected_type: str) -> dict:
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.algorithm])
        if payload.get("typ") != expected_type:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token türü hatalı")
        return payload
    except JWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz token") from exc


def _is_revoked(db: Session, jti: str) -> bool:
    return db.scalar(select(RevokedToken).where(RevokedToken.token_jti == jti)) is not None


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    db: Session = Depends(get_db),
) -> User:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Oturum gerekli")
    token = authorization.removeprefix("Bearer ").strip()
    payload = decode_token(token, "access")
    jti = payload.get("jti")
    if not jti or _is_revoked(db, jti):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token iptal edilmiş")
    user = db.scalar(select(User).where(User.username == payload["sub"], User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı")
    return user


def rotate_refresh_token(db: Session, refresh_token: str) -> tuple[User, str, str]:
    payload = decode_token(refresh_token, "refresh")
    jti = payload["jti"]
    token_row = db.scalar(select(RefreshToken).where(RefreshToken.token_jti == jti))
    if not token_row or token_row.is_revoked:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token geçersiz")
    if token_row.expires_at < datetime.utcnow():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token süresi dolmuş")
    if token_row.token_hash != _token_hash(refresh_token):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token eşleşmiyor")

    token_row.is_revoked = True
    token_row.revoked_at = datetime.utcnow()
    db.add(RevokedToken(token_jti=jti, token_type="refresh"))

    user = db.scalar(select(User).where(User.username == payload["sub"], User.is_active.is_(True)))
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Kullanıcı bulunamadı")

    access_token = create_access_token(user)
    new_refresh_token = create_refresh_token(db, user)
    db.commit()
    return user, access_token, new_refresh_token


def revoke_access_token(db: Session, access_token: str) -> None:
    payload = decode_token(access_token, "access")
    jti = payload.get("jti")
    if jti and not _is_revoked(db, jti):
        db.add(RevokedToken(token_jti=jti, token_type="access"))
        db.commit()


def revoke_refresh_token(db: Session, refresh_token: str) -> None:
    payload = decode_token(refresh_token, "refresh")
    jti = payload.get("jti")
    token_row = db.scalar(select(RefreshToken).where(RefreshToken.token_jti == jti))
    if token_row and not token_row.is_revoked:
        token_row.is_revoked = True
        token_row.revoked_at = datetime.utcnow()
    if jti and not _is_revoked(db, jti):
        db.add(RevokedToken(token_jti=jti, token_type="refresh"))
    db.commit()


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role != "admin" and user.role not in roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu işlem için yetki yok")
        return user

    return dependency
