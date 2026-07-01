"""Resumable conversion state."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from pdf2epub_ai.utils.files import ensure_dir


@dataclass(slots=True)
class PageState:
    """Cached state for a processed page."""

    page_number: int
    raw_text: str
    repaired_text: str
    layout: str
    blocks: list[dict[str, Any]] = field(default_factory=list)
    raw_blocks: list[dict[str, Any]] = field(default_factory=list)
    repair_signature: str = ""
    complete: bool = True


@dataclass(slots=True)
class ConversionState:
    """Persistent conversion state."""

    source_hash: str
    pages: dict[int, PageState] = field(default_factory=dict)


class StateStore:
    """JSON-backed state store for interruption recovery."""

    def __init__(self, cache_dir: Path, source_hash: str) -> None:
        self.cache_dir = ensure_dir(cache_dir)
        self.path = self.cache_dir / f"{source_hash}.state.json"
        self.source_hash = source_hash

    def load(self) -> ConversionState:
        """Load state from disk."""

        if not self.path.exists():
            return ConversionState(source_hash=self.source_hash)
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        pages = {
            int(key): PageState(**value)
            for key, value in raw.get("pages", {}).items()
            if isinstance(value, dict)
        }
        return ConversionState(source_hash=raw["source_hash"], pages=pages)

    def save(self, state: ConversionState) -> None:
        """Atomically save state to disk."""

        serializable: dict[str, Any] = asdict(state)
        serializable["pages"] = {str(key): asdict(value) for key, value in state.pages.items()}
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(serializable, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(self.path)
