"""Typed application configuration."""

from __future__ import annotations

import tomllib
from enum import StrEnum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class OcrEngineName(StrEnum):
    """Supported OCR engine identifiers."""

    AUTO = "auto"
    OCRMYPDF = "ocrmypdf"
    PADDLEOCR = "paddleocr"
    TESSERACT = "tesseract"
    EASYOCR = "easyocr"


class AiProviderName(StrEnum):
    """Supported AI provider identifiers."""

    RULE = "rule"
    OPENAI_COMPATIBLE = "openai-compatible"
    OLLAMA = "ollama"
    LOCAL = "local"


class OcrConfig(BaseModel):
    """OCR-related configuration."""

    engine: OcrEngineName = OcrEngineName.AUTO
    language: str = "tur"
    dpi: int = Field(default=300, ge=150, le=600)
    gpu: bool = False
    split_double_pages: bool = True
    preserve_illustrations: bool = True


class AiConfig(BaseModel):
    """AI provider configuration."""

    provider: AiProviderName = AiProviderName.RULE
    base_url: str = "http://localhost:11434"
    api_key: str | None = None
    model: str = "qwen3:8b"
    command: list[str] = Field(default_factory=list)
    timeout_seconds: int = Field(default=120, ge=5)


class EpubConfig(BaseModel):
    """EPUB output configuration."""

    title: str = "Untitled"
    author: str = "Unknown"
    language: str = "tr"
    publisher: str = "PDF2EPUB AI"
    cover: Path | None = None
    css_path: Path | None = None


class PerformanceConfig(BaseModel):
    """Performance and state configuration."""

    workers: int = Field(default=1, ge=1)
    cache_dir: Path = Path(".pdf2epub-ai-cache")
    keep_temp: bool = False


class AppConfig(BaseModel):
    """Top-level application configuration."""

    ocr: OcrConfig = Field(default_factory=OcrConfig)
    ai: AiConfig = Field(default_factory=AiConfig)
    epub: EpubConfig = Field(default_factory=EpubConfig)
    performance: PerformanceConfig = Field(default_factory=PerformanceConfig)

    @classmethod
    def from_file(cls, path: Path | None) -> AppConfig:
        """Load configuration from TOML, returning defaults when no file is supplied."""

        if path is None:
            default_path = Path.cwd() / "pdf2epub-ai.toml"
            path = default_path if default_path.exists() else None
        if path is None or not path.exists():
            return cls()
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)

    def merged(self, overrides: dict[str, Any]) -> AppConfig:
        """Return a new config with shallow dotted-key overrides applied."""

        data = self.model_dump()
        for dotted_key, value in overrides.items():
            if value is None:
                continue
            section, key = dotted_key.split(".", 1)
            data.setdefault(section, {})[key] = value
        return AppConfig.model_validate(data)
