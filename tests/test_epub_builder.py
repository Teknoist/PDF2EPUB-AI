import zipfile
from pathlib import Path

from pdf2epub_ai.core.models import BookDocument, Chapter, TextBlock
from pdf2epub_ai.epub.builder import EpubBuilder


def test_epub_builder_creates_valid_archive(tmp_path: Path) -> None:
    output = tmp_path / "book.epub"
    document = BookDocument(
        title="Deneme",
        author="Yazar",
        language="tr",
        chapters=[
            Chapter(
                title="Bölüm 1",
                blocks=[TextBlock(text="Bugün yer verildi.", page_number=1)],
            )
        ],
    )

    EpubBuilder().build(document, output)

    with zipfile.ZipFile(output) as epub:
        assert epub.read("mimetype") == b"application/epub+zip"
        assert "EPUB/package.opf" in epub.namelist()
        assert "EPUB/nav.xhtml" in epub.namelist()
        assert "EPUB/text/chapter-0001.xhtml" in epub.namelist()
