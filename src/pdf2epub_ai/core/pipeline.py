"""End-to-end PDF to EPUB conversion pipeline."""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from hashlib import sha256
from pathlib import Path
from typing import Any

from pdf2epub_ai.ai.repair_engine import AIRepairEngine
from pdf2epub_ai.core.config import AppConfig
from pdf2epub_ai.core.models import BookDocument, Chapter, PageContent, TextBlock
from pdf2epub_ai.core.state import ConversionState, PageState, StateStore
from pdf2epub_ai.epub.builder import EpubBuilder
from pdf2epub_ai.exceptions import ConversionCancelledError, DependencyMissingError
from pdf2epub_ai.ocr.engines import OcrEngine, OcrEngineRegistry, OcrMyPdfEngine
from pdf2epub_ai.ocr.pdf_analysis import PdfAnalyzer
from pdf2epub_ai.ocr.preprocess import ImagePreprocessor
from pdf2epub_ai.utils.files import ensure_dir, sha256_file

LOGGER = logging.getLogger(__name__)
ProgressCallback = Callable[[int, int, str], None]
PreviewCallback = Callable[[int, str, str], None]
CancelCallback = Callable[[], bool]
REPAIR_CACHE_VERSION = "4"


class ConversionPipeline:
    """Coordinate analysis, OCR, repair, caching, and EPUB generation."""

    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self.analyzer = PdfAnalyzer(dpi=config.ocr.dpi)
        self.repair_engine = AIRepairEngine(config.ai)
        self.epub_builder = EpubBuilder()

    def convert(
        self,
        input_pdf: Path,
        output_epub: Path,
        resume: bool = False,
        progress: ProgressCallback | None = None,
        preview: PreviewCallback | None = None,
        cancelled: CancelCallback | None = None,
    ) -> Path:
        """Convert a PDF file into EPUB 3."""

        if not input_pdf.exists():
            raise FileNotFoundError(input_pdf)
        self._check_cancelled(cancelled)
        source_hash = sha256_file(input_pdf)
        state_store = StateStore(self.config.performance.cache_dir, source_hash)
        state = state_store.load() if resume else ConversionState(source_hash=source_hash)
        work_dir = ensure_dir(self.config.performance.cache_dir / source_hash)

        native_pages = self.analyzer.extract_native_pages(input_pdf)
        pages = self._process_pages(
            input_pdf,
            work_dir,
            native_pages,
            state,
            state_store,
            progress,
            preview,
            cancelled,
        )
        self._check_cancelled(cancelled)
        document = BookDocument(
            title=self.config.epub.title,
            author=self.config.epub.author,
            language=self.config.epub.language,
            chapters=self._chapters_from_pages(pages),
            cover=self.config.epub.cover,
        )
        result = self.epub_builder.build(document, output_epub)
        if not self.config.performance.keep_temp:
            shutil.rmtree(work_dir, ignore_errors=True)
        return result

    def _process_pages(
        self,
        input_pdf: Path,
        work_dir: Path,
        native_pages: list[PageContent],
        state: ConversionState,
        state_store: StateStore,
        progress: ProgressCallback | None,
        preview: PreviewCallback | None,
        cancelled: CancelCallback | None,
    ) -> list[PageContent]:
        total = len(native_pages) if native_pages else self._page_count(input_pdf)
        needs_ocr = not native_pages or any(page.is_blank for page in native_pages)
        repair_signature = self._repair_signature()
        registry = OcrEngineRegistry(self.config.ocr)
        engine: OcrEngine | None = registry.get(self.config.ocr.engine) if needs_ocr else None

        if isinstance(engine, OcrMyPdfEngine) and not native_pages:
            return self._process_ocrmypdf(
                input_pdf,
                work_dir,
                engine,
                state,
                state_store,
                total,
                repair_signature,
                progress,
                preview,
                cancelled,
            )

        rendered: list[Path] = []
        preprocessor: ImagePreprocessor | None = None
        if needs_ocr:
            rendered = self.analyzer.render_pages(input_pdf, ensure_dir(work_dir / "rendered"))
            preprocessor = ImagePreprocessor(ensure_dir(work_dir / "preprocessed"))
            if isinstance(engine, OcrMyPdfEngine):
                engine = registry.best_image()
        if not native_pages:
            native_pages = [PageContent(page_number=index) for index in range(1, len(rendered) + 1)]

        output_pages: list[PageContent] = []
        for index, page in enumerate(native_pages, start=1):
            self._check_cancelled(cancelled)
            cached = state.pages.get(page.page_number)
            if cached and cached.complete:
                cached_blocks = self._cached_blocks(
                    cached,
                    repair_signature,
                    state,
                    state_store,
                    cancelled,
                )
                repaired = "\n\n".join(block.text for block in cached_blocks)
                output_pages.append(
                    PageContent(
                        page_number=cached.page_number,
                        text_blocks=cached_blocks,
                        is_blank=not repaired.strip(),
                        layout=cached.layout,
                    )
                )
                self._preview(preview, cached.page_number, cached.raw_text, repaired)
                self._progress(progress, index, total, f"Loaded page {page.page_number} from cache")
                continue

            raw_text = "\n".join(block.text for block in page.text_blocks).strip()
            raw_blocks = [self._block_to_state(block) for block in page.text_blocks]
            repaired_blocks = self._repair_blocks(page.text_blocks)
            if not raw_text and rendered and preprocessor is not None and engine is not None:
                images = preprocessor.process(
                    rendered[page.page_number - 1],
                    page.page_number,
                    split_double_pages=self.config.ocr.split_double_pages,
                )
                raw_text = "\n\n".join(engine.recognize_image(image.path).text for image in images)
                raw_block = TextBlock(text=raw_text, page_number=page.page_number)
                raw_blocks = [self._block_to_state(raw_block)]
                repaired_blocks = self._repair_blocks([raw_block])

            repaired = "\n\n".join(block.text for block in repaired_blocks)
            output_page = PageContent(
                page_number=page.page_number,
                text_blocks=repaired_blocks,
                images=page.images,
                is_blank=not repaired.strip(),
                layout=page.layout,
            )
            output_pages.append(output_page)
            state.pages[page.page_number] = PageState(
                page_number=page.page_number,
                raw_text=raw_text,
                repaired_text=repaired,
                layout=page.layout,
                blocks=[self._block_to_state(block) for block in repaired_blocks],
                raw_blocks=raw_blocks,
                repair_signature=repair_signature,
            )
            state_store.save(state)
            self._preview(preview, page.page_number, raw_text, repaired)
            self._progress(progress, index, total, f"Processed page {page.page_number}")
        return output_pages

    def _process_ocrmypdf(
        self,
        input_pdf: Path,
        work_dir: Path,
        engine: OcrMyPdfEngine,
        state: ConversionState,
        state_store: StateStore,
        total: int,
        repair_signature: str,
        progress: ProgressCallback | None,
        preview: PreviewCallback | None,
        cancelled: CancelCallback | None,
    ) -> list[PageContent]:
        result = engine.recognize_pdf(input_pdf, ensure_dir(work_dir / "ocrmypdf"))
        pages: list[PageContent] = []
        for page_number, raw_text in enumerate(result.text.split("\f"), start=1):
            self._check_cancelled(cancelled)
            if not raw_text.strip():
                continue
            raw_block = TextBlock(text=raw_text, page_number=page_number)
            repaired_block = self._repair_blocks([raw_block])[0]
            page = PageContent(page_number=page_number, text_blocks=[repaired_block])
            pages.append(page)
            state.pages[page_number] = PageState(
                page_number=page_number,
                raw_text=raw_text,
                repaired_text=repaired_block.text,
                layout="single-column",
                blocks=[self._block_to_state(repaired_block)],
                raw_blocks=[self._block_to_state(raw_block)],
                repair_signature=repair_signature,
            )
            state_store.save(state)
            self._preview(preview, page_number, raw_text, repaired_block.text)
            self._progress(progress, page_number, total, f"Processed page {page_number}")
        return pages

    def _cached_blocks(
        self,
        cached: PageState,
        repair_signature: str,
        state: ConversionState,
        state_store: StateStore,
        cancelled: CancelCallback | None,
    ) -> list[TextBlock]:
        if cached.repair_signature == repair_signature:
            items = cached.blocks or [
                {"text": cached.repaired_text, "role": "paragraph", "bold": False, "italic": False}
            ]
            return [self._state_to_block(item, cached.page_number) for item in items]

        raw_items = cached.raw_blocks or [
            {"text": cached.raw_text, "role": "paragraph", "bold": False, "italic": False}
        ]
        self._check_cancelled(cancelled)
        raw_blocks = [self._state_to_block(item, cached.page_number) for item in raw_items]
        repaired_blocks = self._repair_blocks(raw_blocks)
        cached.blocks = [self._block_to_state(block) for block in repaired_blocks]
        cached.raw_blocks = raw_items
        cached.repaired_text = "\n\n".join(block.text for block in repaired_blocks)
        cached.repair_signature = repair_signature
        state.pages[cached.page_number] = cached
        state_store.save(state)
        return repaired_blocks

    def _repair_blocks(self, blocks: list[TextBlock]) -> list[TextBlock]:
        return [
            TextBlock(
                text=self.repair_engine.repair(
                    block.text,
                    preserve_line_breaks=block.role in {"table", "poetry"},
                ),
                page_number=block.page_number,
                bbox=block.bbox,
                role=block.role,
                bold=block.bold,
                italic=block.italic,
            )
            for block in blocks
        ]

    def _block_to_state(self, block: TextBlock) -> dict[str, Any]:
        return {
            "text": block.text,
            "role": block.role,
            "bold": block.bold,
            "italic": block.italic,
        }

    def _state_to_block(self, item: dict[str, Any], page_number: int) -> TextBlock:
        return TextBlock(
            text=str(item.get("text", "")),
            page_number=page_number,
            role=str(item.get("role", "paragraph")),
            bold=bool(item.get("bold", False)),
            italic=bool(item.get("italic", False)),
        )

    def _repair_signature(self) -> str:
        payload = f"{REPAIR_CACHE_VERSION}|{self.config.ai.model_dump_json()}"
        return sha256(payload.encode("utf-8")).hexdigest()

    def _chapters_from_pages(self, pages: list[PageContent]) -> list[Chapter]:
        chapters: list[Chapter] = []
        current_title = self.config.epub.title
        current_blocks: list[TextBlock] = []
        for page in pages:
            for block in page.text_blocks:
                if not block.text.strip():
                    continue
                heading = self._extract_heading(block)
                if heading:
                    if current_blocks:
                        chapters.append(Chapter(title=current_title, blocks=current_blocks))
                    current_title = heading
                    current_blocks = []
                    continue
                current_blocks.append(block)
        if current_blocks:
            chapters.append(Chapter(title=current_title, blocks=current_blocks))
        return chapters or [Chapter(title=self.config.epub.title, blocks=[])]

    def _extract_heading(self, block: TextBlock) -> str | None:
        text = block.text.strip()
        first_line = text.splitlines()[0] if text else ""
        if block.role == "heading":
            return first_line
        prefixes = ("bölüm", "chapter", "kısım")
        if len(first_line) <= 80 and first_line.casefold().startswith(prefixes):
            return first_line
        return None

    def _page_count(self, input_pdf: Path) -> int:
        try:
            import fitz  # type: ignore[import-untyped]
        except Exception as exc:
            raise DependencyMissingError(
                "PyMuPDF is required when OCRmyPDF cannot be used"
            ) from exc
        with fitz.open(input_pdf) as doc:
            return len(doc)

    def _check_cancelled(self, callback: CancelCallback | None) -> None:
        if callback and callback():
            raise ConversionCancelledError("Conversion cancelled")

    def _progress(
        self,
        callback: ProgressCallback | None,
        current: int,
        total: int,
        message: str,
    ) -> None:
        LOGGER.info(message)
        if callback:
            callback(current, total, message)

    def _preview(
        self,
        callback: PreviewCallback | None,
        page_number: int,
        raw_text: str,
        repaired_text: str,
    ) -> None:
        if callback:
            callback(page_number, raw_text, repaired_text)
