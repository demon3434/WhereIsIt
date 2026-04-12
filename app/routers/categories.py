from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user, require_admin
from ..models import Category, OperationLog, User
from ..schemas import CategoryIn, CategoryOut, MessageOut

router = APIRouter(prefix="/api/categories", tags=["分类"])


@router.get("", response_model=list[CategoryOut])
def list_categories(db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
  stmt = select(Category)
  if current_user.role != "admin":
    stmt = stmt.where(Category.is_active.is_(True))
  stmt = stmt.order_by(Category.sort_order.asc(), Category.id.asc())
  return list(db.scalars(stmt))


@router.post("", response_model=CategoryOut)
def create_category(payload: CategoryIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  category = Category(name=payload.name.strip(), sort_order=max(0, payload.sort_order), owner=admin, is_active=True)
  db.add(category)
  db.add(OperationLog(owner=admin, action="create_category", details=category.name))
  try:
    db.commit()
  except Exception:
    db.rollback()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类名称重复")
  db.refresh(category)
  return category


@router.put("/{category_id}", response_model=MessageOut)
def update_category(category_id: int, payload: CategoryIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  category = db.get(Category, category_id)
  if not category:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
  category.name = payload.name.strip()
  category.sort_order = max(0, payload.sort_order)
  db.add(OperationLog(owner=admin, action="update_category", details=category.name))
  try:
    db.commit()
  except Exception:
    db.rollback()
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类名称重复")
  return MessageOut(message="分类已更新")


@router.post("/{category_id}/enable", response_model=MessageOut)
def enable_category(category_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  category = db.get(Category, category_id)
  if not category:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
  category.is_active = True
  db.add(OperationLog(owner=admin, action="enable_category", details=category.name))
  db.commit()
  return MessageOut(message="分类已启用")


@router.post("/{category_id}/disable", response_model=MessageOut)
def disable_category(category_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  category = db.get(Category, category_id)
  if not category:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
  category.is_active = False
  db.add(OperationLog(owner=admin, action="disable_category", details=category.name))
  db.commit()
  return MessageOut(message="分类已停用")


@router.delete("/{category_id}", response_model=MessageOut)
def delete_category(category_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
  category = db.get(Category, category_id)
  if not category:
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
  db.delete(category)
  db.add(OperationLog(owner=admin, action="delete_category", details=category.name))
  db.commit()
  return MessageOut(message="分类已删除")
