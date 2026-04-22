from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
import re

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session, selectinload

from ...config import settings
from ...models import Item, VoiceSearchTerm
from .text_normalizer import normalize_voice_text

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+|[\u4e00-\u9fff]+")
_CHINESE_TOKEN_PATTERN = re.compile(r"^[\u4e00-\u9fff]+$")


@dataclass(slots=True)
class VoiceSearchTermSnapshot:
    brands: list[str]
    fragments: list[str]


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _tokenize_phrase(value: str) -> list[str]:
    return [match.group(0) for match in _TOKEN_PATTERN.finditer(value)]


def _expand_token(token: str) -> set[str]:
    expanded = {token}
    if _CHINESE_TOKEN_PATTERN.fullmatch(token) and len(token) >= 2:
        max_size = min(4, len(token))
        for size in range(2, max_size + 1):
            for start in range(0, len(token) - size + 1):
                expanded.add(token[start : start + size])
    return expanded


def _collect_item_terms(item: Item) -> list[tuple[str, str, int]]:
    terms: dict[tuple[str, str], int] = {}

    def add_term(term: str, term_type: str, weight: int) -> None:
        candidate = normalize_voice_text(term).query_text.replace(" ", "")
        if len(candidate) < 2:
            return
        key = (candidate, term_type)
        terms[key] = max(weight, terms.get(key, 0))

    add_term(item.brand or "", "brand", 100)

    candidate_texts: list[tuple[str, int]] = [(item.name or "", 80)]
    if item.category and item.category.name:
        candidate_texts.append((item.category.name, 45))
    candidate_texts.extend((tag.name, 50) for tag in item.tags)

    for raw_text, base_weight in candidate_texts:
        normalized_text = normalize_voice_text(raw_text).query_text
        for token in _tokenize_phrase(normalized_text):
            for fragment in _expand_token(token):
                add_term(fragment, "fragment", base_weight - max(0, len(token) - len(fragment)) * 5)

    return [(term, term_type, weight) for (term, term_type), weight in terms.items()]


def mark_item_voice_terms_dirty(item: Item, dirty_at: datetime | None = None) -> None:
    item.voice_terms_dirty_at = dirty_at or _utcnow()


def mark_all_items_voice_terms_dirty(db: Session, dirty_at: datetime | None = None) -> None:
    db.execute(update(Item).values(voice_terms_dirty_at=dirty_at or _utcnow()))


def _refresh_item_voice_terms(db: Session, item: Item) -> None:
    db.execute(delete(VoiceSearchTerm).where(VoiceSearchTerm.item_id == item.id))
    rows = [
        VoiceSearchTerm(
            user_id=item.user_id,
            item_id=item.id,
            term=term,
            term_type=term_type,
            weight=weight,
        )
        for term, term_type, weight in _collect_item_terms(item)
    ]
    if rows:
        db.add_all(rows)


def delete_item_voice_terms(db: Session, item_id: int) -> None:
    db.execute(delete(VoiceSearchTerm).where(VoiceSearchTerm.item_id == item_id))


def _load_pending_items(db: Session, due_before: datetime) -> list[Item]:
    stmt = (
        select(Item)
        .where(Item.voice_terms_dirty_at.is_not(None), Item.voice_terms_dirty_at <= due_before)
        .options(selectinload(Item.category), selectinload(Item.location), selectinload(Item.tags))
        .order_by(Item.voice_terms_dirty_at.asc(), Item.id.asc())
        .limit(max(1, settings.voice_terms_index_batch_size))
        .with_for_update(skip_locked=True)
    )
    return list(db.scalars(stmt).unique())


def process_pending_voice_terms(db: Session) -> int:
    due_before = _utcnow() - timedelta(seconds=max(0, settings.voice_terms_index_delay_seconds))
    pending_items = _load_pending_items(db, due_before)
    if not pending_items:
        return 0

    indexed_at = _utcnow()
    processed = 0
    for item in pending_items:
        dirty_snapshot = item.voice_terms_dirty_at
        if dirty_snapshot is None:
            continue

        _refresh_item_voice_terms(db, item)
        cleared = db.execute(
            update(Item)
            .where(Item.id == item.id, Item.voice_terms_dirty_at == dirty_snapshot)
            .values(voice_terms_dirty_at=None, voice_terms_last_indexed_at=indexed_at)
        ).rowcount
        processed += 1 if cleared else 0

    if processed:
        logger.info(
            "voice term indexer processed %s items (due_before=%s, batch_size=%s)",
            processed,
            due_before.isoformat(sep=" ", timespec="seconds"),
            max(1, settings.voice_terms_index_batch_size),
        )
    return processed


def load_voice_search_term_snapshot(db: Session, user_id: int) -> VoiceSearchTermSnapshot:
    rows = db.execute(
        select(VoiceSearchTerm.term, VoiceSearchTerm.term_type, VoiceSearchTerm.weight)
        .where(VoiceSearchTerm.user_id == user_id)
        .order_by(VoiceSearchTerm.term_type.asc(), VoiceSearchTerm.weight.desc(), VoiceSearchTerm.term.asc())
    ).all()

    brands: list[str] = []
    fragments: list[str] = []
    seen_brands: set[str] = set()
    seen_fragments: set[str] = set()

    for term, term_type, _ in rows:
        if term_type == "brand":
            if term not in seen_brands:
                brands.append(term)
                seen_brands.add(term)
            continue
        if term not in seen_fragments:
            fragments.append(term)
            seen_fragments.add(term)

    fragments = [fragment for fragment in fragments if fragment not in seen_brands]
    brands.sort(key=lambda value: (-len(value), value))
    fragments.sort(key=lambda value: (-len(value), value))
    return VoiceSearchTermSnapshot(brands=brands, fragments=fragments)


def iter_voice_search_terms(snapshot: VoiceSearchTermSnapshot) -> Iterable[str]:
    yield from snapshot.brands
    yield from snapshot.fragments
