from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

from .config import CONFIGS_DIR


@lru_cache(maxsize=1)
def load_terminology() -> dict[str, dict[str, str]]:
    path = CONFIGS_DIR / "terminology.json"
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return {section: dict(entries) for section, entries in payload.items()}


def apply_terminology(text: str, mode: str) -> str:
    glossary = load_terminology()
    replacements: dict[str, str] = {}
    replacements.update(glossary.get("global", {}))
    replacements.update(glossary.get(mode, {}))
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        pattern = re.compile(re.escape(source), flags=re.IGNORECASE)
        text = pattern.sub(target, text)
    return _normalize_spacing(text)


def _normalize_spacing(text: str) -> str:
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return re.sub(r"\s+", " ", text).strip()
