"""Shared domain models."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class TextBlock:
    """A positioned block of recognized or extracted text."""

    text: str
    page_number: int
    bbox: tuple[float, float, float, float] | None = None
    role: str = "paragraph"
    bold: bool = False
    italic: bool = False


@dataclass(slots=True)
class ImageAsset:
    """An image extracted from a PDF page for EPUB embedding."""

    source: Path
    media_type: str
    page_number: int
    alt: str = ""


@dataclass(slots=True)
class PageContent:
    """Analyzed page content."""

    page_number: int
    text_blocks: list[TextBlock] = field(default_factory=list)
    images: list[ImageAsset] = field(default_factory=list)
    is_blank: bool = False
    layout: str = "single-column"


@dataclass(slots=True)
class Chapter:
    """A logical EPUB chapter."""

    title: str
    blocks: list[TextBlock]
    images: list[ImageAsset] = field(default_factory=list)


@dataclass(slots=True)
class BookDocument:
    """Intermediate representation used by the EPUB builder."""

    title: str
    author: str
    language: str
    chapters: list[Chapter]
    cover: Path | None = None
