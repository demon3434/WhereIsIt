from datetime import datetime, timedelta, timezone
import uuid

from fastapi import HTTPException, status
from jose import JWTError, jwt
from passlib.context import CryptContext

from .config import settings

pwd_context = CryptContext(schemes=["pbkdf2_sha256"], deprecated="auto")
BOOT_NONCE = uuid.uuid4().hex


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(raw_password: str, password_hash: str) -> bool:
    return pwd_context.verify(raw_password, password_hash)


def create_access_token(user_id: int) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "exp": expire, "bn": BOOT_NONCE}
    return jwt.encode(payload, settings.secret_key, algorithm="HS256")


def parse_token(token: str) -> int:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        if payload.get("bn") != BOOT_NONCE:
            raise ValueError("token boot nonce mismatch")
        sub = payload.get("sub")
        if not sub:
            raise ValueError("token missing sub")
        return int(sub)
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效，请重新登录")
