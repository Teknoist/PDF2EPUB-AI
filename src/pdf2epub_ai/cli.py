"""Command-line interface."""

from __future__ import annotations

from pathlib import Path

import click

from pdf2epub_ai.core.config import AiProviderName, AppConfig, OcrEngineName
from pdf2epub_ai.core.pipeline import ConversionPipeline
from pdf2epub_ai.utils.logging import configure_logging


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("input_pdf", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.argument("output_epub", type=click.Path(dir_okay=False, path_type=Path))
@click.option("--config", "config_path", type=click.Path(dir_okay=False, path_type=Path))
@click.option(
    "--ocr-engine",
    type=click.Choice([item.value for item in OcrEngineName]),
    default=None,
)
@click.option(
    "--ai-provider",
    type=click.Choice([item.value for item in AiProviderName]),
    default=None,
)
@click.option("--language", default=None)
@click.option("--resume", is_flag=True)
@click.option("--gpu", is_flag=True)
@click.option("--verbose", is_flag=True)
@click.option("--keep-temp", is_flag=True)
def main(
    input_pdf: Path,
    output_epub: Path,
    config_path: Path | None,
    ocr_engine: str | None,
    ai_provider: str | None,
    language: str | None,
    resume: bool,
    gpu: bool,
    verbose: bool,
    keep_temp: bool,
) -> None:
    """Convert scanned or mixed PDFs into EPUB 3."""

    configure_logging(verbose)
    config = AppConfig.from_file(config_path).merged(
        {
            "ocr.engine": ocr_engine,
            "ai.provider": ai_provider,
            "ocr.language": language,
            "ocr.gpu": gpu if gpu else None,
            "performance.keep_temp": keep_temp if keep_temp else None,
        }
    )

    with click.progressbar(length=100, label="Converting") as bar:
        last = 0

        def progress(current: int, total: int, message: str) -> None:
            nonlocal last
            percent = int((current / max(total, 1)) * 100)
            bar.update(max(0, percent - last))
            last = percent
            click.echo(f"\n{message}", err=True)

        result = ConversionPipeline(config).convert(
            input_pdf,
            output_epub,
            resume=resume,
            progress=progress,
        )
        bar.update(max(0, 100 - last))
    click.echo(str(result))
