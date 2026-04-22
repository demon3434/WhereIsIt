from __future__ import annotations

from dataclasses import dataclass
import re

from .term_index_service import VoiceSearchTermSnapshot

try:
    import jieba
except Exception:  # pragma: no cover - optional dependency
    jieba = None  # type: ignore[assignment]


@dataclass(slots=True)
class QueryPlan:
    normalized_query: str
    keywords: list[str]
    query_variants: list[str]


def _extract_keywords(compact_query: str, snapshot: VoiceSearchTermSnapshot) -> list[str]:
    if not compact_query:
        return []

    candidates: list[tuple[int, int, int, str]] = []
    for priority, terms in ((0, snapshot.brands), (1, snapshot.fragments)):
        for term in terms:
            start = compact_query.find(term)
            while start >= 0:
                end = start + len(term)
                candidates.append((start, end, priority, term))
                start = compact_query.find(term, start + 1)

    by_start: dict[int, list[tuple[int, int, int, str]]] = {}
    for candidate in candidates:
        by_start.setdefault(candidate[0], []).append(candidate)

    extracted: list[str] = []
    position = 0
    while position < len(compact_query):
        matches = by_start.get(position, [])
        if not matches:
            position += 1
            continue
        best = min(matches, key=lambda item: (item[2], -(item[1] - item[0]), item[3]))
        if extracted and extracted[-1] == best[3]:
            position = best[1]
            continue
        extracted.append(best[3])
        position = best[1]

    return extracted


def _jieba_keywords(raw_query: str, known_terms: set[str]) -> list[str]:
    if jieba is None or not raw_query:
        return []

    tokens: list[str] = []
    for token in jieba.lcut(raw_query, cut_all=False):
        candidate = re.sub(r"\s+", "", str(token or "").strip().lower())
        if len(candidate) < 2:
            continue
        if candidate in known_terms:
            continue
        if candidate not in tokens:
            tokens.append(candidate)
    return tokens


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        candidate = (value or "").strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        deduped.append(candidate)
    return deduped


def build_query_plan(final_text: str, normalized_query: str, snapshot: VoiceSearchTermSnapshot) -> QueryPlan:
    raw_query = (normalized_query or final_text or "").strip()
    compact_query = raw_query.replace(" ", "")

    split_keywords = [part for part in raw_query.split(" ") if part]
    extracted_keywords = _extract_keywords(compact_query, snapshot)

    known_terms = set(snapshot.brands) | set(snapshot.fragments)
    jieba_keywords = _jieba_keywords(raw_query, known_terms)

    if len(split_keywords) >= 2:
        keywords = _dedupe_preserve_order(split_keywords + extracted_keywords + jieba_keywords)
    else:
        keywords = _dedupe_preserve_order(
            extracted_keywords + jieba_keywords or split_keywords or ([compact_query] if compact_query else [])
        )

    normalized_for_search = " ".join(keywords) if len(keywords) >= 2 else (keywords[0] if keywords else raw_query)

    variants: list[str] = []

    def add_variant(value: str) -> None:
        candidate = (value or "").strip()
        if candidate and candidate not in variants:
            variants.append(candidate)

    add_variant(final_text)
    add_variant(raw_query)
    add_variant(compact_query)
    add_variant(normalized_for_search)
    add_variant(normalized_for_search.replace(" ", ""))

    if len(keywords) >= 2:
        for start in range(len(keywords)):
            for end in range(start + 2, len(keywords) + 1):
                add_variant(" ".join(keywords[start:end]))
                add_variant("".join(keywords[start:end]))

    for keyword in keywords:
        add_variant(keyword)

    return QueryPlan(
        normalized_query=normalized_for_search or raw_query,
        keywords=keywords,
        query_variants=variants,
    )
