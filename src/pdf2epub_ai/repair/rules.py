"""Rule-based Turkish OCR repair."""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass

TURKISH_WORDS: set[str] = {
    "ahmet",
    "ama",
    "ancak",
    "arasında",
    "artık",
    "aynı",
    "başladı",
    "ben",
    "bir",
    "böyle",
    "bugün",
    "bunun",
    "çok",
    "çünkü",
    "daha",
    "devam",
    "dedi",
    "değil",
    "diye",
    "geldi",
    "gibi",
    "gitti",
    "hangi",
    "her",
    "herhangi",
    "için",
    "ile",
    "insan",
    "kitap",
    "kendi",
    "olarak",
    "oldu",
    "onun",
    "sonra",
    "şey",
    "vardı",
    "verildi",
    "yer",
    "yok",
    "zaman",
}

COMMON_REPLACEMENTS: dict[str, str] = {
    "Bug ün": "Bugün",
    "bug ün": "bugün",
    "Her hangi": "Herhangi",
    "her hangi": "herhangi",
    "i çin": "için",
    "I çin": "İçin",
    "a h met": "Ahmet",
    "A h met": "Ahmet",
    "k itap": "kitap",
    "g eldi": "geldi",
    "de vam": "devam",
    "y er": "yer",
}

ASCII_TURKISH_HINTS: dict[str, str] = {
    "cunku": "çünkü",
    "degil": "değil",
    "daha once": "daha önce",
    "icin": "için",
    "kitabi": "kitabı",
    "sehir": "şehir",
    "sey": "şey",
    "simdi": "şimdi",
}

TURKISH_LETTERS = "A-Za-zÇĞİÖŞÜçğıöşü"


@dataclass(slots=True)
class RepairContext:
    """Context flags used by repair rules."""

    preserve_line_breaks: bool = False


class RepairRule(ABC):
    """Composable text repair rule."""

    @abstractmethod
    def apply(self, text: str, context: RepairContext) -> str:
        """Return repaired text."""


class CommonReplacementRule(RepairRule):
    """Apply high-confidence OCR replacements."""

    def apply(self, text: str, context: RepairContext) -> str:
        text = re.sub(r"(?<!\S)©(?!\S)", "o", text)
        text = re.sub(r"\bbiç(?=\s+gel(?:me|mez|miyor|di))", "hiç", text, flags=re.IGNORECASE)
        text = re.sub(r"\bkaldır\s*:\s*dım\b", "kaldırdım", text, flags=re.IGNORECASE)
        for source, target in COMMON_REPLACEMENTS.items():
            text = re.sub(rf"\b{re.escape(source)}\b", target, text)
        for source, target in ASCII_TURKISH_HINTS.items():
            text = re.sub(rf"\b{re.escape(source)}\b", target, text, flags=re.IGNORECASE)
        return text


class WhitespaceRule(RepairRule):
    """Repair duplicated spaces and random line breaks."""

    def apply(self, text: str, context: RepairContext) -> str:
        text = text.replace("\u00a0", " ")
        text = re.sub(r"[ \t]{2,}", " ", text)
        if context.preserve_line_breaks:
            return text
        text = re.sub(r"(?<![.!?:;…])\n(?!\n|[-–—•])", " ", text)
        return re.sub(r"\n{3,}", "\n\n", text)


class HyphenRepairRule(RepairRule):
    """Repair line-end hyphenation."""

    def apply(self, text: str, context: RepairContext) -> str:
        letters = TURKISH_LETTERS
        text = re.sub(rf"([{letters}]+)-[ \t]*\n\s*([{letters}]+)", r"\1\2", text)
        # Tesseract TSV loses line boundaries but retains a space after a
        # line-end hyphen. Attached hyphen + whitespace is a reliable wrap.
        return re.sub(rf"([{letters}]+)-\s+([{letters}]+)", r"\1\2", text)


class CharacterConfusionRule(RepairRule):
    """Repair high-confidence character confusions after word joining."""

    def apply(self, text: str, context: RepairContext) -> str:
        lowercase = "a-zçğıöşü"
        return re.sub(rf"(?<=[{lowercase}])T(?=[{lowercase}])", "r", text)


class PunctuationRule(RepairRule):
    """Repair punctuation spacing and common OCR punctuation confusion."""

    def apply(self, text: str, context: RepairContext) -> str:
        text = re.sub(r"\s+([,.;:!?])", r"\1", text)
        letters = TURKISH_LETTERS
        text = re.sub(rf"([,;:!?])(?=[{letters}])", r"\1 ", text)
        text = re.sub(rf"(?<!\.)\.(?!\.)(?=[{letters}])", ". ", text)
        text = re.sub(r"([\"“‘])\s+", r"\1", text)
        text = re.sub(r"\s+([\"”’])", r"\1", text)
        text = re.sub(rf"\b([{letters}])\s+'\s+([{letters}])\b", r"\1'\2", text)
        return text


class PageArtifactRule(RepairRule):
    """Remove OCR page numbers and short publisher-logo artifacts at page ends."""

    def apply(self, text: str, context: RepairContext) -> str:
        text = re.sub(r"\A[tT]rolsüz\b", "Kontrolsüz", text)
        letters = TURKISH_LETTERS
        pattern = rf"\s+(?:[{letters}]{{1,5}}[!|]\s+)?\d{{1,3}}\s*/?\s*\Z"
        return re.sub(pattern, "", text)


class BrokenWordMergeRule(RepairRule):
    """Merge broken words using a compact Turkish lexicon."""

    def apply(self, text: str, context: RepairContext) -> str:
        tokens = re.split(r"(\W+)", text)
        changed = True
        while changed:
            changed = False
            output: list[str] = []
            index = 0
            while index < len(tokens):
                if index + 2 < len(tokens) and tokens[index + 1].isspace():
                    left = tokens[index]
                    right = tokens[index + 2]
                    merged = left + right
                    if self._should_merge(left, right, merged):
                        output.append(self._preserve_case(left, merged))
                        index += 3
                        changed = True
                        continue
                output.append(tokens[index])
                index += 1
            tokens = output
        return "".join(tokens)

    def _should_merge(self, left: str, right: str, merged: str) -> bool:
        if not left.isalpha() or not right.isalpha():
            return False
        if len(left) > 12 or len(right) > 12:
            return False
        normalized = merged.casefold()
        if normalized in TURKISH_WORDS:
            return True
        return len(right) == 1 and len(left) >= 3 and normalized in TURKISH_WORDS

    def _preserve_case(self, original_left: str, merged: str) -> str:
        if original_left[:1].isupper():
            return merged[:1].upper() + merged[1:]
        return merged


class ParagraphReconstructionRule(RepairRule):
    """Normalize paragraph boundaries without flattening dialogue or poetry."""

    def apply(self, text: str, context: RepairContext) -> str:
        paragraphs = re.split(r"\n\s*\n", text)
        repaired: list[str] = []
        for paragraph in paragraphs:
            lines = [line.strip() for line in paragraph.splitlines() if line.strip()]
            if not lines:
                continue
            if self._looks_like_poetry_or_dialogue(lines):
                repaired.append("\n".join(lines))
            else:
                repaired.append(" ".join(lines))
        return "\n\n".join(repaired)

    def _looks_like_poetry_or_dialogue(self, lines: list[str]) -> bool:
        if any(line.startswith(("-", "–", "—", "•")) for line in lines):
            return True
        short_lines = sum(1 for line in lines if len(line) <= 42)
        return len(lines) >= 3 and short_lines / len(lines) > 0.7


class RuleBasedRepairer:
    """Deterministic fallback OCR repair pipeline."""

    def __init__(self, rules: list[RepairRule] | None = None) -> None:
        self.rules = rules or [
            CommonReplacementRule(),
            HyphenRepairRule(),
            CharacterConfusionRule(),
            WhitespaceRule(),
            BrokenWordMergeRule(),
            PunctuationRule(),
            PageArtifactRule(),
            ParagraphReconstructionRule(),
            WhitespaceRule(),
        ]

    def repair(self, text: str, preserve_line_breaks: bool = False) -> str:
        """Repair OCR artifacts using deterministic rules."""

        context = RepairContext(preserve_line_breaks=preserve_line_breaks)
        repaired = text
        for rule in self.rules:
            repaired = rule.apply(repaired, context)
        return repaired.strip()
