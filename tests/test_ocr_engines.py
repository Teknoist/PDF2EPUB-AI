from __future__ import annotations

import os
from pathlib import Path

import pytesseract
import pytest
from PIL import Image

from pdf2epub_ai.core.config import OcrConfig
from pdf2epub_ai.ocr.engines import TesseractEngine


def test_tesseract_uses_tessdata_prefix_and_restores_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    image_path = tmp_path / "page.png"
    Image.new("L", (10, 10), color=255).save(image_path)
    tessdata_dir = tmp_path / "tessdata with spaces"
    tessdata_dir.mkdir()
    command = tmp_path / "tesseract.exe"
    command.touch()

    engine = TesseractEngine(OcrConfig(language="tur"))
    monkeypatch.setattr(engine, "is_available", lambda: True)
    monkeypatch.setattr(engine, "_command", lambda: command)
    monkeypatch.setattr(engine, "_tessdata_dir", lambda: tessdata_dir)
    monkeypatch.setenv("TESSDATA_PREFIX", "original-value")

    observed: dict[str, str] = {}

    def fake_image_to_data(
        _image: Image.Image, *, lang: str, output_type: str, config: str
    ) -> dict[str, list[str]]:
        observed["prefix"] = os.environ["TESSDATA_PREFIX"]
        observed["config"] = config
        assert lang == "tur"
        assert output_type == pytesseract.Output.DICT
        return {"text": ["metin"], "conf": ["95"]}

    monkeypatch.setattr(pytesseract, "image_to_data", fake_image_to_data)

    result = engine.recognize_image(image_path)

    assert result.text == "metin"
    assert observed == {"prefix": str(tessdata_dir), "config": "--psm 3"}
    assert os.environ["TESSDATA_PREFIX"] == "original-value"
