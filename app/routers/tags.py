from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import OperationLog, Tag, User, item_tags
from ..schemas import MessageOut, TagIn, TagOut

router = APIRouter(prefix="/api/tags", tags=["标签"])


@router.get("", response_model=list[TagOut])
def list_tags(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
  stmt = select(Tag)
  if current_user.role != "admin":
    stmt = stmt.where(Tag.is_active.is_(True))
  stmt = stmt.order_by(Tag.id.desc())
  return list(db.scalars(stmt))


@router.post("", response_model=TagOut)
def create_tag(payload: TagIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  tag = Tag(name=payload.name.strip(), owner=admin, is_active=True)
  db.add(tag)
  db.add(OperationLog(owner=admin, action="create_tag", details=tag.name))
  try:
    db.commit()
  except Exception:
    db.rollback()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签名称重复")
  db.refresh(tag)
  return tag


@router.put("/{tag_id}", response_model=MessageOut)
def update_tag(tag_id: int, payload: TagIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  tag = db.get(Tag, tag_id)
  if not tag:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
  tag.name = payload.name.strip()
  db.add(OperationLog(owner=admin, action="update_tag", details=tag.name))
  try:
    db.commit()
  except Exception:
    db.rollback()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签名称重复")
  return MessageOut(message="标签已更新")


@router.post("/{tag_id}/enable", response_model=MessageOut)
def enable_tag(tag_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  tag = db.get(Tag, tag_id)
  if not tag:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
  tag.is_active = True
  db.add(OperationLog(owner=admin, action="enable_tag", details=tag.name))
  db.commit()
  return MessageOut(message="标签已启用")


@router.post("/{tag_id}/disable", response_model=MessageOut)
def disable_tag(tag_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  tag = db.get(Tag, tag_id)
  if not tag:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
  tag.is_active = False
  db.add(OperationLog(owner=admin, action="disable_tag", details=tag.name))
  db.commit()
  return MessageOut(message="标签已停用")


@router.delete("/{tag_id}", response_model=MessageOut)
def delete_tag(tag_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  tag = db.get(Tag, tag_id)
  if not tag:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
  db.execute(delete(item_tags).where(item_tags.c.tag_id == tag_id))
  db.delete(tag)
  db.add(OperationLog(owner=admin, action="delete_tag", details=tag.name))
  db.commit()
  return MessageOut(message="标签已删除")
