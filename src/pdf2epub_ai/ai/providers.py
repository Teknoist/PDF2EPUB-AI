"""AI provider abstractions for OCR repair."""

from __future__ import annotations

import json
import subprocess
import urllib.error
import urllib.request
from abc import ABC, abstractmethod

from pdf2epub_ai.core.config import AiConfig, AiProviderName

REPAIR_PROMPT = (
    "You are a deterministic OCR proofreader.\n"
    "Repair OCR mistakes only.\n"
    "Never rewrite the content.\n"
    "Never summarize.\n"
    "Never change the author's writing style.\n"
    "Never translate.\n"
    "If uncertain, copy the original text unchanged.\n"
    "Never alter proper names or intentional capitalization.\n"
    "Do not infer or add missing text at page boundaries.\n"
    "Preserve typographic quote characters exactly; do not normalize them.\n"
    "Copy every __PDF2EPUB_*__ placeholder exactly and in the same position.\n"
    "Correct only clear character confusions, broken words, line-end hyphens, and spacing.\n"
    "When several corrections seem possible, use the smallest character edit.\n"
    "For Turkish OCR, distinguish clear symbol confusions such as ©/o and biç/hiç from context.\n"
    "Preserve names, quotations, dialogue, paragraph breaks, emphasis, and punctuation.\n"
    "Do not add explanations, labels, markdown, or commentary.\n"
    "Return only the corrected text."
)


class AiProvider(ABC):
    """Abstract AI provider."""

    def __init__(self, config: AiConfig) -> None:
        self.config = config

    @abstractmethod
    def is_available(self) -> bool:
        """Return provider availability."""

    @abstractmethod
    def repair_text(self, text: str) -> str:
        """Repair OCR text."""


class RuleOnlyProvider(AiProvider):
    """Provider that intentionally disables AI calls."""

    def is_available(self) -> bool:
        return False

    def repair_text(self, text: str) -> str:
        return text


class OpenAiCompatibleProvider(AiProvider):
    """OpenAI-compatible chat completions provider."""

    def is_available(self) -> bool:
        return bool(self.config.base_url and self.config.model)

    def repair_text(self, text: str) -> str:
        url = self.config.base_url.rstrip("/") + "/v1/chat/completions"
        payload = {
            "model": self.config.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": REPAIR_PROMPT},
                {"role": "user", "content": text},
            ],
        }
        return self._post_chat(url, payload)

    def _post_chat(self, url: str, payload: dict[str, object]) -> str:
        headers = {"Content-Type": "application/json"}
        if self.config.api_key:
            headers["Authorization"] = f"Bearer {self.config.api_key}"
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return str(data["choices"][0]["message"]["content"]).strip()


class OllamaProvider(AiProvider):
    """Ollama-compatible generate API provider."""

    def is_available(self) -> bool:
        try:
            with urllib.request.urlopen(
                self.config.base_url.rstrip("/") + "/api/tags",
                timeout=3,
            ) as response:
                return bool(response.status == 200)
        except (urllib.error.URLError, TimeoutError):
            return False

    def repair_text(self, text: str) -> str:
        request = urllib.request.Request(
            self.config.base_url.rstrip("/") + "/api/generate",
            data=json.dumps(
                {
                    "model": self.config.model,
                    "system": REPAIR_PROMPT,
                    "prompt": text,
                    "stream": False,
                    "think": False,
                    "keep_alive": "10m",
                    "options": {"temperature": 0, "num_ctx": 4096},
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=self.config.timeout_seconds) as response:
            data = json.loads(response.read().decode("utf-8"))
        return str(data.get("response", "")).strip()


class LocalCommandProvider(AiProvider):
    """Local model provider that reads text from stdin and writes repaired text to stdout."""

    def is_available(self) -> bool:
        return bool(self.config.command)

    def repair_text(self, text: str) -> str:
        command = [*self.config.command, REPAIR_PROMPT]
        completed = subprocess.run(
            command,
            input=text,
            capture_output=True,
            text=True,
            timeout=self.config.timeout_seconds,
            check=False,
        )
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or "local AI provider failed")
        return completed.stdout.strip()


def create_ai_provider(config: AiConfig) -> AiProvider:
    """Instantiate the configured AI provider."""

    providers: dict[AiProviderName, type[AiProvider]] = {
        AiProviderName.RULE: RuleOnlyProvider,
        AiProviderName.OPENAI_COMPATIBLE: OpenAiCompatibleProvider,
        AiProviderName.OLLAMA: OllamaProvider,
        AiProviderName.LOCAL: LocalCommandProvider,
    }
    return providers[config.provider](config)
