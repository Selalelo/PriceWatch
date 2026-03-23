"""
auth.py  —  Authentication
===========================
- Password hashing with passlib/bcrypt
- JWT creation + verification with python-jose
- FastAPI dependency  get_current_user  for protected routes
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from passlib.context import CryptContext

from config import settings

pwd_ctx    = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer     = HTTPBearer()


# ── Password ──────────────────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    return pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_ctx.verify(plain, hashed)


# ── JWT ───────────────────────────────────────────────────────────────────────

def create_access_token(user_id: str, email: str) -> str:
    expire  = datetime.now(timezone.utc) + timedelta(hours=settings.jwt_expiry_hours)
    payload = {"sub": user_id, "email": email, "exp": expire}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )


# ── FastAPI dependency ────────────────────────────────────────────────────────

class CurrentUser:
    def __init__(self, user_id: str, email: str):
        self.user_id = user_id
        self.email   = email


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(bearer)]
) -> CurrentUser:
    payload = decode_token(credentials.credentials)
    return CurrentUser(user_id=payload["sub"], email=payload["email"])


# Type alias for cleaner route signatures
AuthUser = Annotated[CurrentUser, Depends(get_current_user)]