from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ...models import Item, User
from .query_builder import QueryPlan


def _score_item(item: Item, plan: QueryPlan) -> int:
    name = (item.name or "").lower()
    brand = (item.brand or "").lower()
    location_detail = (item.location_detail or "").lower()
    category_name = (item.category.name if item.category else "").lower()
    room_path = (item.location.path if item.location else "").lower()
    tags = " ".join(tag.name.lower() for tag in item.tags)
    corpus = " ".join(part for part in [name, brand, location_detail, category_name, room_path, tags] if part)

    score = 0
    for variant in plan.query_variants:
        normalized_variant = variant.lower()
        if normalized_variant in name:
            score = max(score, 180)
        if normalized_variant and normalized_variant in brand:
            score = max(score, 150)
        if normalized_variant and normalized_variant in corpus:
            score = max(score, 130)

    if plan.keywords and all(keyword.lower() in corpus for keyword in plan.keywords):
        score += 80

    for keyword in plan.keywords:
        lowered = keyword.lower()
        if lowered in name:
            score += 30
        if lowered in brand:
            score += 25
        if lowered in category_name or lowered in tags:
            score += 18
        if lowered in location_detail or lowered in room_path:
            score += 12

    return score


def load_voice_search_items(db: Session, current_user: User) -> list[Item]:
    from ...routers.items import query_base

    return list(db.scalars(query_base(current_user)).unique())


def search_items_for_voice(
    db: Session,
    current_user: User,
    plan: QueryPlan,
    limit: int = 20,
    items: list[Item] | None = None,
) -> list[dict]:
    from ...routers.items import item_to_out

    items = items if items is not None else load_voice_search_items(db, current_user)
    scored: list[tuple[int, datetime, int, Item]] = []
    for item in items:
        score = _score_item(item, plan)
        if score > 0:
            scored.append((score, item.updated_at, item.id, item))

    scored.sort(key=lambda entry: (entry[0], entry[1], entry[2]), reverse=True)
    return [item_to_out(item).model_dump() for _, _, _, item in scored[:limit]]
