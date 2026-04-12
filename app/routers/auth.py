from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..auth import create_access_token, verify_password
from ..config import settings
from ..database import get_db
from ..models import OperationLog, User
from ..schemas import MessageOut, TokenOut, UserLogin

router = APIRouter(prefix="/api/auth", tags=["??"])


@router.post("/login", response_model=TokenOut)
def login(payload: UserLogin, response: Response, db: Session = Depends(get_db)):
    username = payload.username.strip()
    password = payload.password.strip()
    user = db.scalar(select(User).where(func.lower(User.username) == username.lower()))
    if not user or not verify_password(password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="????????")
    if not user.is_active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="????????????")

    token = create_access_token(user.id)
    db.add(OperationLog(owner=user, action="login", details="????"))
    db.commit()

    response.set_cookie(
        key=settings.auth_cookie_name,
        value=token,
        max_age=settings.access_token_expire_minutes * 60,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite="lax",
        path="/",
    )
    return TokenOut(access_token=token)


@router.post("/logout", response_model=MessageOut)
def logout(response: Response):
    response.delete_cookie(
        key=settings.auth_cookie_name,
        path="/",
        samesite="lax",
    )
    return MessageOut(message="?????")
