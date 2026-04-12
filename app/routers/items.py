import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy import Select, select
from sqlalchemy.orm import Session, selectinload

from ..config import settings
from ..database import get_db
from ..deps import get_current_user
from ..models import Category, House, Item, ItemImage, Location, OperationLog, Tag, User
from ..schemas import ItemIn, ItemOut, MessageOut
from ..services.storage import save_upload_file

router = APIRouter(prefix="/api/items", tags=["物品"])


def check_refs(db: Session, current_user: User, category_id: int, house_id: int, room_id: int) -> tuple[Category, Location]:
    category = db.get(Category, category_id)
    if not category:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类不存在")
    if current_user.role != "admin" and not category.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类已停用")

    house = db.get(House, house_id)
    if not house:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房屋不存在")
    if current_user.role != "admin":
        available_house_ids = {h.id for h in current_user.accessible_houses}
        if house_id not in available_house_ids:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="无权使用该房屋")
        if not house.is_active:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房屋已停用")

    location = db.get(Location, room_id)
    if not location:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房间不存在")
    if location.house_id != house_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房间与房屋不匹配")
    if current_user.role != "admin" and not location.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="房间已停用")
    return category, location


def collect_tags(db: Session, current_user: User, tag_ids: list[int], tag_names: list[str]) -> list[Tag]:
    tags: list[Tag] = []
    if tag_ids:
        unique_ids = set(tag_ids)
        tags = list(db.scalars(select(Tag).where(Tag.id.in_(unique_ids))))
        if len(tags) != len(unique_ids):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签不存在")
        if current_user.role != "admin" and any(not tag.is_active for tag in tags):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签已停用")

    tag_map = {tag.name.lower(): tag for tag in tags}
    for raw_name in tag_names:
        name = raw_name.strip()
        if not name:
            continue
        key = name.lower()
        if key in tag_map:
            continue

        same_name_tags = list(db.scalars(select(Tag).where(Tag.name == name)))
        selected = next((x for x in same_name_tags if x.user_id == current_user.id), None) or (
            same_name_tags[0] if same_name_tags else None
        )
        if selected:
            if current_user.role != "admin" and not selected.is_active:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"标签已停用：{name}")
            tags.append(selected)
            tag_map[key] = selected
            continue

        new_tag = Tag(name=name, owner=current_user, is_active=True)
        db.add(new_tag)
        db.flush()
        tags.append(new_tag)
        tag_map[key] = new_tag

    if len(tags) > 50:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="最多 50 个标签")
    return tags


def item_to_out(item: Item) -> ItemOut:
    house_name = None
    if item.location and item.location.path:
        house_name = item.location.path.split("-", 1)[0]
    owner_display_name = "-"
    if item.owner:
        owner_display_name = item.owner.full_name or item.owner.nickname or item.owner.username
    return ItemOut(
        id=item.id,
        name=item.name,
        location_detail=item.location_detail,
        quantity=item.quantity,
        brand=item.brand,
        category_id=item.category_id,
        category_name=item.category.name if item.category else None,
        room_id=item.location_id,
        room_path=item.location.path if item.location else None,
        house_id=item.location.house_id if item.location else None,
        house_name=house_name,
        tags=item.tags,
        images=item.images,
        owner_user_id=item.user_id,
        owner_username=item.owner.username if item.owner else "",
        owner_display_name=owner_display_name,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def query_base(current_user: User) -> Select[tuple[Item]]:
    stmt = select(Item)
    if current_user.role != "admin":
        stmt = stmt.where(Item.user_id == current_user.id)
    return stmt.options(
        selectinload(Item.tags),
        selectinload(Item.images),
        selectinload(Item.category),
        selectinload(Item.location),
        selectinload(Item.owner),
    ).order_by(Item.updated_at.desc())


@router.get("", response_model=list[ItemOut])
def list_items(
    q: str | None = None,
    category_id: int | None = None,
    house_id: int | None = None,
    room_id: int | None = None,
    tag_id: int | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = query_base(current_user)
    if q:
        stmt = stmt.where(Item.name.ilike(f"%{q}%") | Item.brand.ilike(f"%{q}%"))
    if category_id:
        stmt = stmt.where(Item.category_id == category_id)
    if room_id:
        stmt = stmt.where(Item.location_id == room_id)
    if house_id:
        stmt = stmt.join(Item.location).where(Location.house_id == house_id)
    if tag_id:
        stmt = stmt.join(Item.tags).where(Tag.id == tag_id)
    items = list(db.scalars(stmt).unique())
    return [item_to_out(item) for item in items]


@router.post("", response_model=ItemOut)
def create_item(
    data: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    payload = ItemIn(**json.loads(data))
    if len(files) > settings.max_images_per_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"最多上传 {settings.max_images_per_item} 张图片")
    _, location = check_refs(db, current_user, payload.category_id, payload.house_id, payload.room_id)
    tags = collect_tags(db, current_user, payload.tag_ids, payload.tag_names)

    now = datetime.utcnow()
    item = Item(
        owner=current_user,
        name=payload.name.strip(),
        description="",
        location_detail=payload.location_detail.strip(),
        quantity=payload.quantity,
        brand=payload.brand.strip(),
        category_id=payload.category_id,
        location_id=location.id,
        created_at=now,
        updated_at=now,
    )
    item.tags = tags
    db.add(item)
    db.flush()

    for f in files:
        filename, url = save_upload_file(f, current_user.id, item.id)
        db.add(ItemImage(item=item, filename=filename, url=url))

    db.add(OperationLog(owner=current_user, action="create_item", details=item.name))
    db.commit()
    db.refresh(item)
    return item_to_out(item)


@router.put("/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    data: str = Form(...),
    files: list[UploadFile] = File(default=[]),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    item = db.scalar(query_base(current_user).where(Item.id == item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物品不存在")

    payload = ItemIn(**json.loads(data))
    if len(item.images) + len(files) > settings.max_images_per_item:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"最多上传 {settings.max_images_per_item} 张图片")
    _, location = check_refs(db, current_user, payload.category_id, payload.house_id, payload.room_id)
    tags = collect_tags(db, current_user, payload.tag_ids, payload.tag_names)

    item.name = payload.name.strip()
    item.description = ""
    item.location_detail = payload.location_detail.strip()
    item.quantity = payload.quantity
    item.brand = payload.brand.strip()
    item.category_id = payload.category_id
    item.location_id = location.id
    item.tags = tags

    for f in files:
        filename, url = save_upload_file(f, current_user.id, item.id)
        db.add(ItemImage(item=item, filename=filename, url=url))

    db.add(OperationLog(owner=current_user, action="update_item", details=item.name))
    db.commit()
    db.refresh(item)
    return item_to_out(item)


@router.delete("/{item_id}", response_model=MessageOut)
def delete_item(item_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.scalar(query_base(current_user).where(Item.id == item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物品不存在")
    for image in item.images:
        file_path = Path(settings.upload_dir) / image.filename
        if file_path.exists():
            file_path.unlink(missing_ok=True)
    db.delete(item)
    db.add(OperationLog(owner=current_user, action="delete_item", details=item.name))
    db.commit()
    return MessageOut(message="物品已删除")


@router.delete("/{item_id}/images/{image_id}", response_model=MessageOut)
def delete_item_image(item_id: int, image_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    item = db.scalar(query_base(current_user).where(Item.id == item_id))
    if not item:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="物品不存在")
    target = next((image for image in item.images if image.id == image_id), None)
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
    file_path = Path(settings.upload_dir) / target.filename
    if file_path.exists():
        file_path.unlink(missing_ok=True)
    db.delete(target)
    db.commit()
    return MessageOut(message="图片已删除")
