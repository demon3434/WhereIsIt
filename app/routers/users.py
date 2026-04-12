from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..auth import hash_password
from ..database import get_db
from ..deps import get_current_user
from ..models import OperationLog, User
from ..schemas import MessageOut, UserOut, UserUpdate

router = APIRouter(prefix="/api", tags=["用户"])


@router.get("/me", response_model=UserOut)
def get_me(current_user: User = Depends(get_current_user)):
  return current_user


@router.put("/me", response_model=MessageOut)
def update_me(payload: UserUpdate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
  current_user.nickname = payload.nickname.strip() or current_user.nickname
  current_user.full_name = payload.full_name.strip() if payload.full_name is not None else current_user.full_name
  if payload.default_house_id is not None:
    allowed_ids = {house.id for house in current_user.accessible_houses}
    if payload.default_house_id not in allowed_ids:
      current_user.default_house_id = None
    else:
      current_user.default_house_id = payload.default_house_id
  else:
    current_user.default_house_id = None
  if payload.password:
    current_user.password_hash = hash_password(payload.password)
  db.add(OperationLog(owner=current_user, action="update_profile", details="更新个人信息"))
  db.commit()
  return MessageOut(message="个人信息已保存")
