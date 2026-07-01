"""EPUB 3 builder."""

from __future__ import annotations

import html
import mimetypes
import re
import uuid
import zipfile
from collections.abc import Iterator
from pathlib import Path
from xml.etree import ElementTree

from pdf2epub_ai.core.models import BookDocument, Chapter, ImageAsset, TextBlock
from pdf2epub_ai.exceptions import EpubValidationError

DEFAULT_CSS = """
body {
  font-family: serif;
  line-height: 1.45;
  margin: 0 5%;
}
h1, h2 {
  font-family: sans-serif;
  line-height: 1.2;
}
p {
  margin: 0 0 0.85em 0;
  text-align: justify;
}
.footnote {
  font-size: 0.88em;
}
.dialogue, .poetry {
  white-space: pre-wrap;
}
img {
  display: block;
  max-width: 100%;
  height: auto;
  margin: 1em auto;
}
""".strip()


class EpubBuilder:
    """Generate EPUB 3 archives from analyzed book documents."""

    def __init__(self, css: str | None = None) -> None:
        self.css = css or DEFAULT_CSS

    def build(self, document: BookDocument, output_path: Path) -> Path:
        """Build and validate an EPUB archive."""

        output_path.parent.mkdir(parents=True, exist_ok=True)
        book_id = f"urn:uuid:{uuid.uuid4()}"
        chapters = document.chapters or [Chapter(title=document.title, blocks=[])]

        with zipfile.ZipFile(output_path, "w") as epub:
            epub.writestr("mimetype", "application/epub+zip", compress_type=zipfile.ZIP_STORED)
            epub.writestr("META-INF/container.xml", self._container_xml())
            epub.writestr("EPUB/styles/book.css", self.css)
            epub.writestr("EPUB/nav.xhtml", self._nav_xhtml(document, chapters))
            image_offset = 0
            for index, chapter in enumerate(chapters, start=1):
                epub.writestr(
                    f"EPUB/text/chapter-{index:04d}.xhtml",
                    self._chapter_xhtml(chapter, index, image_offset),
                )
                image_offset += len(chapter.images)
            for index, image in enumerate(self._iter_images(chapters), start=1):
                epub.write(
                    image.source,
                    f"EPUB/images/image-{index:04d}{image.source.suffix}",
                )
            if document.cover:
                epub.write(document.cover, f"EPUB/images/cover{document.cover.suffix}")
            epub.writestr("EPUB/package.opf", self._package_opf(document, chapters, book_id))

        self.validate(output_path)
        return output_path

    def validate(self, epub_path: Path) -> None:
        """Validate the generated archive structure and XHTML well-formedness."""

        with zipfile.ZipFile(epub_path) as epub:
            names = epub.namelist()
            required = {"mimetype", "META-INF/container.xml", "EPUB/package.opf", "EPUB/nav.xhtml"}
            missing = required.difference(names)
            if missing:
                raise EpubValidationError(f"EPUB is missing required files: {sorted(missing)}")
            if epub.read("mimetype") != b"application/epub+zip":
                raise EpubValidationError("EPUB mimetype entry is invalid")
            for name in names:
                if name.endswith(".xhtml") or name.endswith(".opf") or name.endswith(".xml"):
                    try:
                        ElementTree.fromstring(epub.read(name))
                    except ElementTree.ParseError as exc:
                        raise EpubValidationError(f"Invalid XML in {name}: {exc}") from exc

    def _container_xml(self) -> str:
        return """<?xml version="1.0" encoding="UTF-8"?>
<container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
  <rootfiles>
    <rootfile full-path="EPUB/package.opf" media-type="application/oebps-package+xml"/>
  </rootfiles>
</container>
"""

    def _package_opf(self, document: BookDocument, chapters: list[Chapter], book_id: str) -> str:
        manifest_items = [
            '<item id="nav" href="nav.xhtml" media-type="application/xhtml+xml" properties="nav"/>',
            '<item id="css" href="styles/book.css" media-type="text/css"/>',
        ]
        spine_items: list[str] = []
        for index, _chapter in enumerate(chapters, start=1):
            href = f"text/chapter-{index:04d}.xhtml"
            manifest_items.append(
                f'<item id="chapter-{index:04d}" href="{href}" '
                'media-type="application/xhtml+xml"/>'
            )
            spine_items.append(f'<itemref idref="chapter-{index:04d}"/>')
        for index, image in enumerate(self._iter_images(chapters), start=1):
            media_type = (
                image.media_type or mimetypes.guess_type(image.source.name)[0] or "image/png"
            )
            href = f"images/image-{index:04d}{html.escape(image.source.suffix)}"
            manifest_items.append(
                f'<item id="image-{index:04d}" href="{href}" '
                f'media-type="{html.escape(media_type)}"/>'
            )
        if document.cover:
            media_type = mimetypes.guess_type(document.cover.name)[0] or "image/png"
            href = f"images/cover{html.escape(document.cover.suffix)}"
            manifest_items.append(
                f'<item id="cover" href="{href}" '
                f'media-type="{html.escape(media_type)}" properties="cover-image"/>'
            )

        return f"""<?xml version="1.0" encoding="UTF-8"?>
<package version="3.0" unique-identifier="book-id" xmlns="http://www.idpf.org/2007/opf">
  <metadata xmlns:dc="http://purl.org/dc/elements/1.1/">
    <dc:identifier id="book-id">{html.escape(book_id)}</dc:identifier>
    <dc:title>{html.escape(document.title)}</dc:title>
    <dc:creator>{html.escape(document.author)}</dc:creator>
    <dc:language>{html.escape(document.language)}</dc:language>
    <meta property="dcterms:modified">2026-06-30T00:00:00Z</meta>
  </metadata>
  <manifest>
    {' '.join(manifest_items)}
  </manifest>
  <spine>
    {' '.join(spine_items)}
  </spine>
</package>
"""

    def _nav_xhtml(self, document: BookDocument, chapters: list[Chapter]) -> str:
        items = "\n".join(
            f'<li><a href="text/chapter-{index:04d}.xhtml">{html.escape(chapter.title)}</a></li>'
            for index, chapter in enumerate(chapters, start=1)
        )
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:epub="http://www.idpf.org/2007/ops"
      lang="{html.escape(document.language)}">
<head>
  <title>{html.escape(document.title)}</title>
  <link rel="stylesheet" type="text/css" href="styles/book.css"/>
</head>
<body>
  <nav epub:type="toc" id="toc">
    <h1>{html.escape(document.title)}</h1>
    <ol>{items}</ol>
  </nav>
</body>
</html>
"""

    def _chapter_xhtml(self, chapter: Chapter, index: int, image_offset: int) -> str:
        body = [f"<h1>{html.escape(chapter.title)}</h1>"]
        image_index = image_offset + 1
        for block in chapter.blocks:
            body.append(self._block_html(block))
        for image in chapter.images:
            suffix = html.escape(image.source.suffix)
            alt = html.escape(image.alt)
            body.append(
                f'<figure><img src="../images/image-{image_index:04d}{suffix}" '
                f'alt="{alt}"/></figure>'
            )
            image_index += 1
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" lang="tr">
<head>
  <title>{html.escape(chapter.title)}</title>
  <link rel="stylesheet" type="text/css" href="../styles/book.css"/>
</head>
<body id="chapter-{index:04d}">
  {''.join(body)}
</body>
</html>
"""

    def _block_html(self, block: TextBlock) -> str:
        text = self._inline_markup(block.text)
        if block.bold:
            text = f"<strong>{text}</strong>"
        if block.italic:
            text = f"<em>{text}</em>"
        if block.role == "heading":
            return f"<h2>{text}</h2>"
        if block.role == "footnote":
            return f'<p class="footnote">{text}</p>'
        if self._looks_poetic(block.text):
            return f'<p class="poetry">{text}</p>'
        return f"<p>{text}</p>"

    def _inline_markup(self, text: str) -> str:
        escaped = html.escape(text)
        escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
        escaped = re.sub(r"_(.+?)_", r"<em>\1</em>", escaped)
        return escaped.replace("\n", "<br/>")

    def _looks_poetic(self, text: str) -> bool:
        lines = [line for line in text.splitlines() if line.strip()]
        return len(lines) >= 3 and sum(1 for line in lines if len(line) <= 42) / len(lines) > 0.7

    def _iter_images(self, chapters: list[Chapter]) -> Iterator[ImageAsset]:
        for chapter in chapters:
            yield from chapter.images
