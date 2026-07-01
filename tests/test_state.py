from pathlib import Path

from pdf2epub_ai.core.state import ConversionState, PageState, StateStore


def test_state_store_round_trip(tmp_path: Path) -> None:
    store = StateStore(tmp_path, "abc")
    state = ConversionState(
        source_hash="abc",
        pages={
            1: PageState(
                page_number=1,
                raw_text="Bug ün",
                repaired_text="Bugün",
                layout="single-column",
                raw_blocks=[{"text": "Bug ün", "role": "paragraph"}],
                repair_signature="rule-v1",
            )
        },
    )

    store.save(state)
    loaded = store.load()

    assert loaded.source_hash == "abc"
    assert loaded.pages[1].repaired_text == "Bugün"
    assert loaded.pages[1].raw_blocks[0]["text"] == "Bug ün"
    assert loaded.pages[1].repair_signature == "rule-v1"
