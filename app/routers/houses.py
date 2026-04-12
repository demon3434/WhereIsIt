from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import House, OperationLog, User
from ..schemas import HouseIn, HouseOut, MessageOut

router = APIRouter(prefix="/api/houses", tags=["房屋"])


@router.get("", response_model=list[HouseOut])
def list_houses(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
  stmt = select(House)
  if current_user.role != "admin":
    accessible_ids = [house.id for house in current_user.accessible_houses]
    if not accessible_ids:
      return []
    stmt = stmt.where(House.is_active.is_(True), House.id.in_(accessible_ids))
  return list(db.scalars(stmt.order_by(House.sort_order.asc(), House.id.asc())))


@router.post("", response_model=HouseOut)
def create_house(payload: HouseIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  house = House(name=payload.name.strip(), sort_order=max(0, payload.sort_order), is_active=True)
  db.add(house)
  db.add(OperationLog(owner=admin, action="create_house", details=house.name))
  try:
    db.commit()
  except Exception:
    db.rollback()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房屋名称重复")
  db.refresh(house)
  return house


@router.put("/{house_id}", response_model=MessageOut)
def update_house(house_id: int, payload: HouseIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  house = db.get(House, house_id)
  if not house:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房屋不存在")
  house.name = payload.name.strip()
  house.sort_order = max(0, payload.sort_order)
  db.add(OperationLog(owner=admin, action="update_house", details=house.name))
  try:
    db.commit()
  except Exception:
    db.rollback()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房屋名称重复")
  return MessageOut(message="房屋已更新")


@router.post("/{house_id}/enable", response_model=MessageOut)
def enable_house(house_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  house = db.get(House, house_id)
  if not house:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房屋不存在")
  house.is_active = True
  db.add(OperationLog(owner=admin, action="enable_house", details=house.name))
  db.commit()
  return MessageOut(message="房屋已启用")


@router.post("/{house_id}/disable", response_model=MessageOut)
def disable_house(house_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  house = db.get(House, house_id)
  if not house:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房屋不存在")
  house.is_active = False
  db.add(OperationLog(owner=admin, action="disable_house", details=house.name))
  db.commit()
  return MessageOut(message="房屋已停用")


@router.delete("/{house_id}", response_model=MessageOut)
def delete_house(house_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  house = db.get(House, house_id)
  if not house:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房屋不存在")
  db.delete(house)
  db.add(OperationLog(owner=admin, action="delete_house", details=house.name))
  db.commit()
  return MessageOut(message="房屋已删除")
