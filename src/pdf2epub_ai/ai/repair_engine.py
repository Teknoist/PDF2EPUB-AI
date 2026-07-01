"""AI-first OCR repair engine with deterministic fallback."""

from __future__ import annotations

import logging
import re
from collections import Counter
from difflib import SequenceMatcher

from wordfreq import word_frequency

from pdf2epub_ai.ai.providers import AiProvider, create_ai_provider
from pdf2epub_ai.core.config import AiConfig
from pdf2epub_ai.repair.rules import RuleBasedRepairer

LOGGER = logging.getLogger(__name__)
STYLE_TOKENS = {
    "“": "__PDF2EPUB_LDQ__",
    "”": "__PDF2EPUB_RDQ__",
    "‘": "__PDF2EPUB_LSQ__",
    "’": "__PDF2EPUB_RSQ__",
    "«": "__PDF2EPUB_LAQ__",
    "»": "__PDF2EPUB_RAQ__",
}


class AIRepairEngine:
    """Repair OCR text while preserving authorial content and style."""

    def __init__(
        self,
        config: AiConfig,
        provider: AiProvider | None = None,
        fallback: RuleBasedRepairer | None = None,
    ) -> None:
        self.config = config
        self.provider = provider or create_ai_provider(config)
        self.fallback = fallback or RuleBasedRepairer()

    def repair(self, text: str, preserve_line_breaks: bool = False) -> str:
        """Repair OCR errors only, falling back to rules when AI is unavailable."""

        if not text.strip():
            return ""
        rule_pass = self.fallback.repair(text, preserve_line_breaks=preserve_line_breaks)
        if not self.provider.is_available():
            return rule_pass
        protected = self._protect_style_tokens(rule_pass)
        try:
            model_output = self.provider.repair_text(protected)
        except Exception as exc:
            LOGGER.warning("AI repair unavailable; using rule-based repair: %s", exc)
            return rule_pass
        repaired = self._restore_style_tokens(protected, model_output)
        if repaired is None:
            LOGGER.warning("AI output changed protected style tokens; using rule-based repair")
            return rule_pass
        return self._guard_output(rule_pass, repaired)

    def _protect_style_tokens(self, text: str) -> str:
        for mark, token in STYLE_TOKENS.items():
            text = text.replace(mark, token)
        return text

    def _restore_style_tokens(self, protected: str, repaired: str) -> str | None:
        for mark, token in STYLE_TOKENS.items():
            if protected.count(token) != repaired.count(token):
                return None
            repaired = repaired.replace(token, mark)
        return repaired

    def _guard_output(self, original: str, repaired: str) -> str:
        cleaned = self._clean_model_output(repaired)
        if not cleaned:
            return original
        original_words = max(1, len(original.split()))
        repaired_words = len(cleaned.split())
        ratio = repaired_words / original_words
        if ratio < 0.65 or ratio > 1.45:
            LOGGER.warning("AI output length changed too much; using rule-based repair")
            return original
        similarity = SequenceMatcher(None, original, cleaned, autojunk=False).ratio()
        if similarity < 0.72:
            LOGGER.warning("AI output changed too much; using rule-based repair")
            return original
        if not self._preserves_quotation_style(original, cleaned):
            LOGGER.warning("AI output changed quotation style; using rule-based repair")
            return original
        if not self._introduces_only_known_words(original, cleaned):
            LOGGER.warning("AI output introduced an unknown word; using rule-based repair")
            return original
        return cleaned

    def _clean_model_output(self, text: str) -> str:
        cleaned = text.strip()
        cleaned = re.sub(r"^```(?:text|plaintext)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
        cleaned = re.sub(r"^<think>.*?</think>\s*", "", cleaned, flags=re.DOTALL)
        return cleaned.strip()

    def _preserves_quotation_style(self, original: str, repaired: str) -> bool:
        protected = "“”‘’«»"
        return all(original.count(mark) == repaired.count(mark) for mark in protected)

    def _introduces_only_known_words(self, original: str, repaired: str) -> bool:
        word_pattern = r"[^\W\d_]+"
        original_words = Counter(word.casefold() for word in re.findall(word_pattern, original))
        repaired_words = Counter(word.casefold() for word in re.findall(word_pattern, repaired))
        for word in repaired_words - original_words:
            if len(word) >= 3 and word_frequency(word, "tr") == 0:
                return False
        return not bool(re.search(r"[a-zçğıöşü][A-ZÇĞİÖŞÜ]", repaired))
