from pathlib import Path

import pytest

from pdf2epub_ai.core.config import AiConfig, AiProviderName, AppConfig
from pdf2epub_ai.core.pipeline import ConversionPipeline
from pdf2epub_ai.core.state import ConversionState, PageState, StateStore
from pdf2epub_ai.exceptions import ConversionCancelledError


def test_cached_ocr_is_repaired_when_ai_mode_changes(tmp_path: Path) -> None:
    config = AppConfig(ai=AiConfig(provider=AiProviderName.RULE))
    pipeline = ConversionPipeline(config)
    store = StateStore(tmp_path, "source")
    page = PageState(
        page_number=1,
        raw_text="Bug ün  g eldi",
        repaired_text="stale output",
        layout="single-column",
        blocks=[{"text": "stale output", "role": "paragraph"}],
        raw_blocks=[{"text": "Bug ün  g eldi", "role": "paragraph"}],
        repair_signature="old-mode",
    )
    state = ConversionState(source_hash="source", pages={1: page})

    blocks = pipeline._cached_blocks(
        page,
        pipeline._repair_signature(),
        state,
        store,
        cancelled=None,
    )

    assert blocks[0].text == "Bugün geldi"
    assert page.repair_signature == pipeline._repair_signature()
    assert store.load().pages[1].repaired_text == "Bugün geldi"


def test_pipeline_honors_cancellation() -> None:
    pipeline = ConversionPipeline(AppConfig())

    with pytest.raises(ConversionCancelledError):
        pipeline._check_cancelled(lambda: True)
