"""OCR engine adapters."""

from __future__ import annotations

import logging
import shutil
import subprocess
from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from pdf2epub_ai.core.config import OcrConfig, OcrEngineName
from pdf2epub_ai.exceptions import DependencyMissingError, OcrEngineError

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class OcrResult:
    """OCR result for a single page or full document."""

    text: str
    confidence: float = 0.0


class OcrEngine(ABC):
    """Abstract OCR engine adapter."""

    name: OcrEngineName

    def __init__(self, config: OcrConfig) -> None:
        self.config = config

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether the engine can run in this environment."""

    @abstractmethod
    def recognize_image(self, image_path: Path) -> OcrResult:
        """Recognize text from a preprocessed page image."""

    def recognize_pdf(self, pdf_path: Path, output_dir: Path) -> OcrResult:
        """Recognize text from a full PDF when the engine supports document mode."""

        raise OcrEngineError(f"{self.name} does not support full-PDF OCR mode for {pdf_path}")


class OcrMyPdfEngine(OcrEngine):
    """OCRmyPDF adapter using sidecar text output."""

    name = OcrEngineName.OCRMYPDF

    def is_available(self) -> bool:
        return shutil.which("ocrmypdf") is not None

    def recognize_image(self, image_path: Path) -> OcrResult:
        raise OcrEngineError("OCRmyPDF works on PDFs; use recognize_pdf")

    def recognize_pdf(self, pdf_path: Path, output_dir: Path) -> OcrResult:
        if not self.is_available():
            raise DependencyMissingError("ocrmypdf executable is not installed")
        output_dir.mkdir(parents=True, exist_ok=True)
        searchable_pdf = output_dir / "ocrmypdf-output.pdf"
        sidecar = output_dir / "ocrmypdf-sidecar.txt"
        command = [
            "ocrmypdf",
            "--skip-text",
            "--deskew",
            "--clean",
            "--rotate-pages",
            "--remove-background",
            "--sidecar",
            str(sidecar),
            "-l",
            self.config.language,
            str(pdf_path),
            str(searchable_pdf),
        ]
        LOGGER.info("Running OCRmyPDF")
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode not in {0, 6}:
            raise OcrEngineError(completed.stderr.strip() or "OCRmyPDF failed")
        return OcrResult(text=sidecar.read_text(encoding="utf-8", errors="replace"), confidence=0.9)


class TesseractEngine(OcrEngine):
    """Tesseract adapter through pytesseract."""

    name = OcrEngineName.TESSERACT

    def is_available(self) -> bool:
        if self._command() is None:
            return False
        try:
            import pytesseract  # noqa: F401
        except Exception:
            return False
        return True

    def recognize_image(self, image_path: Path) -> OcrResult:
        if not self.is_available():
            raise DependencyMissingError("tesseract executable and pytesseract are required")
        import pytesseract  # type: ignore[import-not-found]
        from PIL import Image

        command = self._command()
        if command is None:
            raise DependencyMissingError("tesseract executable is required")
        pytesseract.pytesseract.tesseract_cmd = str(command)
        image = Image.open(image_path)
        options = "--psm 3"
        tessdata = self._tessdata_dir()
        if tessdata is not None:
            options += f' --tessdata-dir "{tessdata}"'
        data = pytesseract.image_to_data(
            image,
            lang=self.config.language,
            output_type=pytesseract.Output.DICT,
            config=options,
        )
        words: list[str] = []
        confidences: list[float] = []
        for word, confidence in zip(data.get("text", []), data.get("conf", []), strict=False):
            stripped = str(word).strip()
            if not stripped:
                continue
            words.append(stripped)
            try:
                numeric = float(confidence)
            except ValueError:
                continue
            if numeric >= 0:
                confidences.append(numeric / 100)
        text = " ".join(words)
        average = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(text=text, confidence=average)

    def _command(self) -> Path | None:
        discovered = shutil.which("tesseract")
        candidates = [
            Path(discovered) if discovered else None,
            Path(r"C:\Program Files\Tesseract-OCR\tesseract.exe"),
            Path.home() / "AppData/Local/Programs/Tesseract-OCR/tesseract.exe",
        ]
        return next((path for path in candidates if path is not None and path.exists()), None)

    def _tessdata_dir(self) -> Path | None:
        candidates = [
            Path.cwd() / ".tools/tessdata",
            Path(r"C:\Program Files\Tesseract-OCR\tessdata"),
            Path.home() / "AppData/Local/Programs/Tesseract-OCR/tessdata",
        ]
        language = self.config.language.split("+")[0]
        return next(
            (path for path in candidates if (path / f"{language}.traineddata").exists()),
            None,
        )


class PaddleOcrEngine(OcrEngine):
    """PaddleOCR adapter."""

    name = OcrEngineName.PADDLEOCR

    def is_available(self) -> bool:
        try:
            import paddleocr  # noqa: F401
        except Exception:
            return False
        return True

    def recognize_image(self, image_path: Path) -> OcrResult:
        if not self.is_available():
            raise DependencyMissingError("paddleocr is not installed")
        from paddleocr import PaddleOCR  # type: ignore[import-not-found]

        language = "tr" if self.config.language.startswith("tur") else self.config.language
        engine = PaddleOCR(use_angle_cls=True, lang=language, use_gpu=self.config.gpu)
        result = engine.ocr(str(image_path), cls=True)
        lines: list[str] = []
        confidences: list[float] = []
        for page in result or []:
            for item in page or []:
                text, confidence = item[1]
                lines.append(str(text))
                confidences.append(float(confidence))
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(text="\n".join(lines), confidence=confidence)


class EasyOcrEngine(OcrEngine):
    """EasyOCR adapter."""

    name = OcrEngineName.EASYOCR

    def is_available(self) -> bool:
        try:
            import easyocr  # noqa: F401
        except Exception:
            return False
        return True

    def recognize_image(self, image_path: Path) -> OcrResult:
        if not self.is_available():
            raise DependencyMissingError("easyocr is not installed")
        import easyocr  # type: ignore[import-not-found]

        reader = easyocr.Reader(["tr", "en"], gpu=self.config.gpu)
        results = reader.readtext(str(image_path), paragraph=True)
        lines = [str(item[1]) for item in results]
        confidences = [float(item[2]) for item in results if len(item) > 2]
        confidence = sum(confidences) / len(confidences) if confidences else 0.0
        return OcrResult(text="\n".join(lines), confidence=confidence)


class OcrEngineRegistry:
    """Select the best available OCR engine for a document."""

    def __init__(self, config: OcrConfig) -> None:
        self.config = config
        self._engines: dict[OcrEngineName, OcrEngine] = {
            OcrEngineName.OCRMYPDF: OcrMyPdfEngine(config),
            OcrEngineName.PADDLEOCR: PaddleOcrEngine(config),
            OcrEngineName.TESSERACT: TesseractEngine(config),
            OcrEngineName.EASYOCR: EasyOcrEngine(config),
        }

    def get(self, name: OcrEngineName) -> OcrEngine:
        """Return a configured engine by name."""

        if name == OcrEngineName.AUTO:
            return self.best()
        engine = self._engines[name]
        if not engine.is_available():
            raise DependencyMissingError(f"OCR engine {name} is not available")
        return engine

    def best(self) -> OcrEngine:
        """Return the highest-priority available engine."""

        priority = [
            OcrEngineName.OCRMYPDF,
            OcrEngineName.PADDLEOCR,
            OcrEngineName.TESSERACT,
            OcrEngineName.EASYOCR,
        ]
        for name in priority:
            engine = self._engines[name]
            if engine.is_available():
                LOGGER.info("Selected OCR engine: %s", name)
                return engine
        raise DependencyMissingError("No supported OCR engine is available")

    def best_image(self) -> OcrEngine:
        """Return the highest-priority engine that accepts page images."""

        priority = [
            OcrEngineName.PADDLEOCR,
            OcrEngineName.TESSERACT,
            OcrEngineName.EASYOCR,
        ]
        for name in priority:
            engine = self._engines[name]
            if engine.is_available():
                LOGGER.info("Selected image OCR engine: %s", name)
                return engine
        raise DependencyMissingError("No image-capable OCR engine is available")
