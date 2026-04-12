from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..auth import hash_password
from ..database import get_db
from ..deps import require_admin
from ..models import House, OperationLog, User
from ..schemas import AdminUserIn, AdminUserUpdate, MessageOut, UserOut

router = APIRouter(prefix="/api/admin/users", tags=["用户管理"])


def to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        nickname=user.nickname,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        available_house_ids=[house.id for house in user.accessible_houses],
        default_house_id=user.default_house_id,
        created_at=user.created_at,
    )


def normalize_house_ids(ids: list[int]) -> list[int]:
    cleaned: list[int] = []
    seen: set[int] = set()
    for raw in ids:
        value = int(raw)
        if value <= 0 or value in seen:
            continue
        seen.add(value)
        cleaned.append(value)
    return cleaned


def validate_houses(db: Session, house_ids: list[int]) -> list[House]:
    if not house_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请至少选择 1 个可用房屋")
    houses = list(db.scalars(select(House).where(House.id.in_(house_ids), House.is_active.is_(True))))
    if len(houses) != len(house_ids):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="可用房屋包含无效或已停用房屋")
    return houses


def ensure_default_house(default_house_id: int | None, house_ids: list[int]) -> int | None:
    if default_house_id is None:
        return None
    if default_house_id not in house_ids:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="默认房屋必须在可用房屋中")
    return default_house_id


@router.get("", response_model=list[UserOut])
def list_users(db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    users = list(db.scalars(select(User).options(selectinload(User.accessible_houses)).order_by(User.id.desc())))
    return [to_user_out(user) for user in users]


@router.post("", response_model=UserOut)
def create_user(payload: AdminUserIn, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    exists = db.scalar(select(User).where(User.username == payload.username.strip()))
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="登录账号已存在")
    role = "admin" if payload.role == "admin" else "user"
    normalized_house_ids = normalize_house_ids(payload.available_house_ids)
    houses = validate_houses(db, normalized_house_ids)
    default_house_id = ensure_default_house(payload.default_house_id, normalized_house_ids)

    user = User(
        username=payload.username.strip(),
        nickname=payload.full_name.strip() or payload.username.strip(),
        full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password),
        role=role,
        is_active=payload.is_active,
        default_house_id=default_house_id,
    )
    user.accessible_houses = houses
    db.add(user)
    db.add(OperationLog(owner=admin, action="admin_create_user", details=user.username))
    db.commit()
    db.refresh(user)
    db.refresh(user, attribute_names=["accessible_houses"])
    return to_user_out(user)


@router.put("/{user_id}", response_model=MessageOut)
def update_user(user_id: int, payload: AdminUserUpdate, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id, options=[selectinload(User.accessible_houses)])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    new_username = payload.username.strip()
    if user.username == "admin" and new_username != "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能修改 admin 账号")
    exists = db.scalar(select(User).where(User.username == new_username, User.id != user_id))
    if exists:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="登录账号已存在")

    normalized_house_ids = normalize_house_ids(payload.available_house_ids)
    houses = validate_houses(db, normalized_house_ids)
    default_house_id = ensure_default_house(payload.default_house_id, normalized_house_ids)

    user.username = new_username
    user.full_name = payload.full_name.strip()
    user.nickname = payload.full_name.strip() or new_username
    user.role = "admin" if payload.role == "admin" else "user"
    user.is_active = payload.is_active
    user.default_house_id = default_house_id
    user.accessible_houses = houses
    db.add(OperationLog(owner=admin, action="admin_update_user", details=user.username))
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="登录账号已存在")
    return MessageOut(message="用户已更新")


@router.post("/{user_id}/enable", response_model=MessageOut)
def enable_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.is_active = True
    db.add(OperationLog(owner=admin, action="admin_enable_user", details=user.username))
    db.commit()
    return MessageOut(message="用户已启用")


@router.post("/{user_id}/disable", response_model=MessageOut)
def disable_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.username == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能停用 admin 账号")
    user.is_active = False
    db.add(OperationLog(owner=admin, action="admin_disable_user", details=user.username))
    db.commit()
    return MessageOut(message="用户已停用")


@router.post("/{user_id}/reset-password", response_model=MessageOut)
def reset_password(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    user.password_hash = hash_password("123456")
    db.add(OperationLog(owner=admin, action="admin_reset_password", details=user.username))
    db.commit()
    return MessageOut(message="密码已重置为 123456")


@router.delete("/{user_id}", response_model=MessageOut)
def delete_user(user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户不存在")
    if user.username == "admin":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="不能删除 admin 账号")
    db.delete(user)
    db.add(OperationLog(owner=admin, action="admin_delete_user", details=user.username))
    db.commit()
    return MessageOut(message="用户已删除")
