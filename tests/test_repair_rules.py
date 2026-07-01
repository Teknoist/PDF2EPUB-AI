from pdf2epub_ai.ai.repair_engine import AIRepairEngine
from pdf2epub_ai.core.config import AiConfig
from pdf2epub_ai.repair.rules import RuleBasedRepairer


def test_rule_based_repair_examples() -> None:
    repairer = RuleBasedRepairer()

    assert repairer.repair("y er verildi") == "yer verildi"
    assert repairer.repair("a h met") == "Ahmet"
    assert repairer.repair("k itap") == "kitap"
    assert repairer.repair("Bug ün") == "Bugün"
    assert repairer.repair("Her hangi") == "Herhangi"
    assert repairer.repair("g eldi") == "geldi"
    assert repairer.repair("i çin") == "için"
    assert repairer.repair("de vam etti") == "devam etti"


def test_ai_repair_engine_falls_back_to_rules() -> None:
    engine = AIRepairEngine(AiConfig())

    assert engine.repair("Bug ün  g eldi") == "Bugün geldi"


def test_repair_preserves_valid_single_letter_words_and_ellipsis() -> None:
    repairer = RuleBasedRepairer()

    source = "o beni izledi... Bay K yanıma geldi."
    assert repairer.repair(source) == source


def test_repair_joins_tesseract_line_end_hyphenation() -> None:
    repairer = RuleBasedRepairer()

    assert repairer.repair("sustur- mak ve kur- tulmak") == "susturmak ve kurtulmak"


def test_repair_fixes_common_symbol_confusions() -> None:
    repairer = RuleBasedRepairer()

    assert repairer.repair("© uzun uzun anlattı") == "o uzun uzun anlattı"
    assert repairer.repair("© biç gelmese bile") == "o hiç gelmese bile"
    assert repairer.repair("yüTürken dizleTimde") == "yürürken dizlerimde"
    assert repairer.repair("yü- Türken dizle- Timde") == "yürürken dizlerimde"
    assert repairer.repair("bedenimi kaldır: dım") == "bedenimi kaldırdım"


def test_repair_removes_page_end_artifacts() -> None:
    repairer = RuleBasedRepairer()

    assert repairer.repair("Metin burada bitti. 15") == "Metin burada bitti."
    assert repairer.repair("trolsüz hisler. kon! 20") == "Kontrolsüz hisler."


def test_ai_guard_rejects_rewritten_content() -> None:
    engine = AIRepairEngine(AiConfig())
    source = "Bu metin yazarın özgün cümlesidir ve aynen korunmalıdır."

    assert engine._guard_output(source, "Tamamen farklı ve kısa bir özet.") == source


def test_ai_guard_removes_markdown_fence() -> None:
    engine = AIRepairEngine(AiConfig())

    assert engine._guard_output("Bugün geldi.", "```text\nBugün geldi.\n```") == "Bugün geldi."


def test_ai_guard_rejects_changed_quotation_style() -> None:
    engine = AIRepairEngine(AiConfig())
    source = "“Bugün geldi,” dedi."

    assert engine._guard_output(source, '"Bugün geldi," dedi.') == source


def test_ai_guard_rejects_unknown_or_randomly_capitalized_words() -> None:
    engine = AIRepairEngine(AiConfig())

    assert engine._guard_output("Özgür geldi.", "ÖzFür geldi.") == "Özgür geldi."
    assert engine._guard_output("Bedenimi kaldırdım.", "Bedenimi kaldırıdim.") == (
        "Bedenimi kaldırdım."
    )


def test_ai_style_tokens_round_trip() -> None:
    engine = AIRepairEngine(AiConfig())
    source = "“Merhaba,” dedi."
    protected = engine._protect_style_tokens(source)

    assert "“" not in protected and "”" not in protected
    assert engine._restore_style_tokens(protected, protected) == source
    assert (
        engine._restore_style_tokens(protected, protected.replace("__PDF2EPUB_RDQ__", "")) is None
    )
