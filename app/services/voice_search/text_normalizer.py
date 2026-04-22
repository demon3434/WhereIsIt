from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
import threading
import unicodedata

from ...config import settings


_DIGIT_WORDS = {
    "零": "0",
    "一": "1",
    "二": "2",
    "两": "2",
    "三": "3",
    "四": "4",
    "五": "5",
    "六": "6",
    "七": "7",
    "八": "8",
    "九": "9",
}

_PUNCT_TRANSLATION = str.maketrans(
    {
        "，": " ",
        "。": " ",
        "、": " ",
        "；": " ",
        "：": " ",
        "？": " ",
        "！": " ",
        "（": " ",
        "）": " ",
        "“": " ",
        "”": " ",
        ",": " ",
        ".": " ",
        ";": " ",
        ":": " ",
        "?": " ",
        "!": " ",
        "\"": " ",
        "'": " ",
    }
)

_DEFAULT_LEXICON_FILES = {
    "prefix": Path(__file__).with_name("cleaning_lexicon_defaults") / "prefix.txt",
    "inline": Path(__file__).with_name("cleaning_lexicon_defaults") / "inline.txt",
    "trailing": Path(__file__).with_name("cleaning_lexicon_defaults") / "trailing.txt",
}

_USER_LEXICON_FILENAMES = {
    "prefix": "prefix.txt",
    "inline": "inline.txt",
    "trailing": "trailing.txt",
}

_LEXICON_CACHE_LOCK = threading.Lock()
_LEXICON_CACHE_SIGNATURE: tuple[tuple[str, int, int], ...] | None = None
_LEXICON_CACHE: dict[str, tuple[re.Pattern[str], ...]] = {
    "prefix": (),
    "inline": (),
    "trailing": (),
}


@dataclass(slots=True)
class NormalizedText:
    raw_text: str
    display_text: str
    query_text: str


def _basic_normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text or "").translate(_PUNCT_TRANSLATION).lower()
    normalized = "".join(_DIGIT_WORDS.get(char, char) for char in normalized)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    return normalized


def _cleaning_lexicon_dir() -> Path:
    return Path(settings.voice_cleaning_lexicon_dir)


def _user_lexicon_path(kind: str) -> Path:
    return _cleaning_lexicon_dir() / _USER_LEXICON_FILENAMES[kind]


def ensure_voice_cleaning_lexicon_files() -> None:
    target_dir = _cleaning_lexicon_dir()
    target_dir.mkdir(parents=True, exist_ok=True)
    for kind, source_path in _DEFAULT_LEXICON_FILES.items():
        target_path = _user_lexicon_path(kind)
        if target_path.exists():
            continue
        target_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")


def _read_lexicon_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []
    lines: list[str] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        lines.append(line)
    return lines


def _phrase_to_pattern(phrase: str, kind: str) -> re.Pattern[str] | None:
    normalized_phrase = _basic_normalize(phrase)
    if not normalized_phrase:
        return None
    escaped = re.escape(normalized_phrase).replace(r"\ ", r"\s*")
    if kind == "prefix":
        pattern = rf"^(?:{escaped})"
    elif kind == "trailing":
        pattern = rf"(?:{escaped})$"
    else:
        pattern = rf"(?:{escaped})"
    return re.compile(pattern)


def _lexicon_signature(paths: list[Path]) -> tuple[tuple[str, int, int], ...]:
    signature: list[tuple[str, int, int]] = []
    for path in paths:
        if not path.exists():
            signature.append((str(path), -1, -1))
            continue
        stat = path.stat()
        signature.append((str(path), int(stat.st_mtime_ns), stat.st_size))
    return tuple(signature)


def _load_cleaning_patterns() -> dict[str, tuple[re.Pattern[str], ...]]:
    ensure_voice_cleaning_lexicon_files()
    lexicon_paths = [
        *_DEFAULT_LEXICON_FILES.values(),
        *(_user_lexicon_path(kind) for kind in _USER_LEXICON_FILENAMES),
    ]
    signature = _lexicon_signature(lexicon_paths)

    global _LEXICON_CACHE_SIGNATURE
    with _LEXICON_CACHE_LOCK:
        if _LEXICON_CACHE_SIGNATURE == signature:
            return _LEXICON_CACHE

        loaded: dict[str, tuple[re.Pattern[str], ...]] = {}
        for kind, default_path in _DEFAULT_LEXICON_FILES.items():
            phrases = _read_lexicon_lines(default_path) + _read_lexicon_lines(_user_lexicon_path(kind))
            deduped: list[re.Pattern[str]] = []
            seen: set[str] = set()
            for phrase in phrases:
                normalized_phrase = _basic_normalize(phrase)
                if not normalized_phrase or normalized_phrase in seen:
                    continue
                seen.add(normalized_phrase)
                pattern = _phrase_to_pattern(normalized_phrase, kind)
                if pattern is not None:
                    deduped.append(pattern)
            loaded[kind] = tuple(deduped)

        _LEXICON_CACHE.update(loaded)
        _LEXICON_CACHE_SIGNATURE = signature
        return _LEXICON_CACHE


def _strip_by_patterns(text: str, patterns: tuple[re.Pattern[str], ...], replace: str) -> str:
    cleaned = text
    while True:
        previous = cleaned
        for pattern in patterns:
            cleaned = pattern.sub(replace, cleaned).strip()
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        if cleaned == previous:
            return cleaned


def normalize_voice_text(text: str) -> NormalizedText:
    raw_text = (text or "").strip()
    normalized = _basic_normalize(raw_text)
    display_text = normalized

    patterns = _load_cleaning_patterns()
    query_text = _strip_by_patterns(normalized, patterns["prefix"], "")
    query_text = _strip_by_patterns(query_text, patterns["inline"], " ")
    query_text = _strip_by_patterns(query_text, patterns["prefix"], "")
    query_text = _strip_by_patterns(query_text, patterns["trailing"], "")
    query_text = re.sub(r"([a-z]+)\s+(\d+)", r"\1\2", query_text)
    query_text = re.sub(r"\s+", " ", query_text).strip()

    if not query_text:
        query_text = re.sub(r"([a-z]+)\s+(\d+)", r"\1\2", normalized)
        query_text = re.sub(r"\s+", " ", query_text).strip()

    return NormalizedText(
        raw_text=raw_text,
        display_text=display_text,
        query_text=query_text,
    )
