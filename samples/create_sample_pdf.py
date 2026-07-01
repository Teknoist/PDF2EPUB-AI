"""Create a simple sample PDF for integration testing."""

from __future__ import annotations

from pathlib import Path


def main() -> None:
    try:
        from reportlab.lib.pagesizes import A5
        from reportlab.pdfgen import canvas
    except Exception as exc:
        raise RuntimeError(
            "Install reportlab to create sample PDFs: pip install reportlab"
        ) from exc

    output = Path(__file__).with_name("sample_text.pdf")
    pdf = canvas.Canvas(str(output), pagesize=A5)
    pdf.setTitle("PDF2EPUB AI Sample")
    pdf.drawString(50, 540, "Bölüm 1")
    pdf.drawString(50, 510, "Bug ün y er verildi. Her hangi bir sorun yok.")
    pdf.drawString(50, 490, "de vam etti ve k itap için geldi.")
    pdf.showPage()
    pdf.save()
    print(output)


if __name__ == "__main__":
    main()
