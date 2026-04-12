from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import House, Location, OperationLog, User
from ..schemas import LocationIn, LocationOut, MessageOut

router = APIRouter(prefix="/api/rooms", tags=["房间"])


def to_out(room: Location, house_name: str | None = None) -> LocationOut:
  return LocationOut(
    id=room.id,
    name=room.name,
    sort_order=room.sort_order,
    house_id=room.house_id,
    house_name=house_name,
    path=room.path,
    parent_id=room.parent_id,
    is_active=room.is_active,
    created_at=room.created_at,
  )


def build_path(house_name: str, room_name: str) -> str:
  return f"{house_name}-{room_name}"


@router.get("", response_model=list[LocationOut])
def list_rooms(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
  stmt = select(Location, House.name).join(House, Location.house_id == House.id, isouter=True)
  if current_user.role != "admin":
    accessible_ids = [house.id for house in current_user.accessible_houses]
    if not accessible_ids:
      return []
    stmt = stmt.where(Location.is_active.is_(True), House.is_active.is_(True), Location.house_id.in_(accessible_ids))
  rows = db.execute(stmt.order_by(Location.house_id.asc(), Location.sort_order.asc(), Location.id.asc())).all()
  return [to_out(room, house_name) for room, house_name in rows]


@router.post("", response_model=LocationOut)
def create_room(payload: LocationIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  if not payload.house_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择所属房屋")
  house = db.get(House, payload.house_id)
  if not house:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房屋不存在")
  room = Location(
    user_id=admin.id,
    house_id=payload.house_id,
    parent_id=None,
    sort_order=max(0, payload.sort_order),
    name=payload.name.strip(),
    path=build_path(house.name, payload.name.strip()),
    is_active=True,
  )
  db.add(room)
  db.add(OperationLog(owner=admin, action="create_room", details=room.path))
  db.commit()
  db.refresh(room)
  return to_out(room, house.name)


@router.put("/{room_id}", response_model=MessageOut)
def update_room(room_id: int, payload: LocationIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  room = db.get(Location, room_id)
  if not room:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房间不存在")
  if not payload.house_id:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择所属房屋")
  house = db.get(House, payload.house_id)
  if not house:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房屋不存在")
  room.house_id = payload.house_id
  room.sort_order = max(0, payload.sort_order)
  room.name = payload.name.strip()
  room.path = build_path(house.name, room.name)
  db.add(OperationLog(owner=admin, action="update_room", details=room.path))
  db.commit()
  return MessageOut(message="房间已更新")


@router.post("/{room_id}/enable", response_model=MessageOut)
def enable_room(room_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  room = db.get(Location, room_id)
  if not room:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房间不存在")
  room.is_active = True
  db.add(OperationLog(owner=admin, action="enable_room", details=room.path))
  db.commit()
  return MessageOut(message="房间已启用")


@router.post("/{room_id}/disable", response_model=MessageOut)
def disable_room(room_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  room = db.get(Location, room_id)
  if not room:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房间不存在")
  room.is_active = False
  db.add(OperationLog(owner=admin, action="disable_room", details=room.path))
  db.commit()
  return MessageOut(message="房间已停用")


@router.delete("/{room_id}", response_model=MessageOut)
def delete_room(room_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  room = db.get(Location, room_id)
  if not room:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="房间不存在")
  db.delete(room)
  db.add(OperationLog(owner=admin, action="delete_room", details=room.path))
  db.commit()
  return MessageOut(message="房间已删除")
