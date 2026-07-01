"""PDF layout and content analysis."""

from __future__ import annotations

import logging
import re
from collections import Counter
from pathlib import Path

from pdf2epub_ai.core.models import PageContent, TextBlock

LOGGER = logging.getLogger(__name__)


class PdfAnalyzer:
    """Analyze PDF text and layout using PyMuPDF when available."""

    def __init__(self, dpi: int = 300) -> None:
        self.dpi = dpi

    def render_pages(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        """Render PDF pages to images."""

        try:
            import fitz  # type: ignore[import-untyped]
        except Exception as exc:
            raise RuntimeError("PyMuPDF is required to render PDF pages") from exc

        output_dir.mkdir(parents=True, exist_ok=True)
        doc = fitz.open(pdf_path)
        paths: list[Path] = []
        zoom = self.dpi / 72
        matrix = fitz.Matrix(zoom, zoom)
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(matrix=matrix, alpha=False)
            output = output_dir / f"rendered_{index:05d}.png"
            pix.save(output)
            paths.append(output)
        return paths

    def extract_native_pages(self, pdf_path: Path) -> list[PageContent]:
        """Extract native PDF text blocks for mixed PDFs."""

        try:
            import fitz
        except Exception:
            LOGGER.debug("PyMuPDF not available for native extraction")
            return []

        doc = fitz.open(pdf_path)
        pages: list[PageContent] = []
        repeated_candidates: Counter[str] = Counter()
        raw_pages: list[PageContent] = []
        for index, page in enumerate(doc, start=1):
            blocks: list[TextBlock] = []
            text_dict = page.get_text("dict")
            height = float(page.rect.height)
            width = float(page.rect.width)
            x_centers: list[float] = []
            for block in text_dict.get("blocks", []):
                if block.get("type") != 0:
                    continue
                raw_bbox = block["bbox"]
                bbox = (
                    float(raw_bbox[0]),
                    float(raw_bbox[1]),
                    float(raw_bbox[2]),
                    float(raw_bbox[3]),
                )
                lines: list[str] = []
                bold = False
                italic = False
                for line in block.get("lines", []):
                    fragments: list[str] = []
                    for span in line.get("spans", []):
                        fragments.append(span.get("text", ""))
                        font = span.get("font", "").lower()
                        bold = bold or "bold" in font
                        italic = italic or "italic" in font or "oblique" in font
                    if "".join(fragments).strip():
                        lines.append("".join(fragments))
                text = "\n".join(lines).strip()
                if not text:
                    continue
                if bbox[1] < height * 0.12 or bbox[3] > height * 0.88:
                    repeated_candidates[self._normalize_repeated(text)] += 1
                role = self._classify_role(text, bbox, height)
                x_centers.append((bbox[0] + bbox[2]) / 2)
                blocks.append(
                    TextBlock(
                        text=text,
                        page_number=index,
                        bbox=bbox,
                        role=role,
                        bold=bold,
                        italic=italic,
                    )
                )
            layout = self._detect_columns(x_centers, width)
            raw_pages.append(
                PageContent(
                    page_number=index,
                    text_blocks=blocks,
                    is_blank=not blocks,
                    layout=layout,
                )
            )

        repeated = {
            text
            for text, count in repeated_candidates.items()
            if count >= max(3, len(raw_pages) // 4)
        }
        for page in raw_pages:
            filtered = [
                block
                for block in page.text_blocks
                if self._normalize_repeated(block.text) not in repeated
                and not self._is_page_number(block.text)
            ]
            pages.append(
                PageContent(
                    page_number=page.page_number,
                    text_blocks=filtered,
                    is_blank=not filtered,
                    layout=page.layout,
                )
            )
        return pages

    def _classify_role(
        self,
        text: str,
        bbox: tuple[float, float, float, float],
        page_height: float,
    ) -> str:
        stripped = text.strip()
        if self._is_page_number(stripped):
            return "page-number"
        if bbox[1] > page_height * 0.78 and len(stripped) < 240:
            return "footnote"
        chapter_match = re.match(
            r"^(Bölüm|Chapter|Kısım)\b",
            stripped,
            re.IGNORECASE,
        )
        if len(stripped) <= 90 and (stripped.isupper() or chapter_match):
            return "heading"
        if "\t" in stripped or re.search(r"\s{3,}", stripped):
            return "table"
        return "paragraph"

    def _detect_columns(self, x_centers: list[float], width: float) -> str:
        if len(x_centers) < 8:
            return "single-column"
        left = sum(1 for x in x_centers if x < width * 0.45)
        right = sum(1 for x in x_centers if x > width * 0.55)
        middle = len(x_centers) - left - right
        if left >= 3 and right >= 3 and middle <= len(x_centers) * 0.25:
            return "multi-column"
        return "single-column"

    def _normalize_repeated(self, text: str) -> str:
        return re.sub(r"\d+", "#", re.sub(r"\s+", " ", text.casefold())).strip()

    def _is_page_number(self, text: str) -> bool:
        return bool(
            re.fullmatch(
                r"[-–—]?\s*(\d{1,4}|[ivxlcdm]{1,12})\s*[-–—]?",
                text.strip(),
                re.IGNORECASE,
            )
        )
