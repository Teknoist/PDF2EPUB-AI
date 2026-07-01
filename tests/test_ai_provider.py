import json
from unittest.mock import MagicMock, patch

from pdf2epub_ai.ai.providers import REPAIR_PROMPT, OllamaProvider
from pdf2epub_ai.core.config import AiConfig, AiProviderName


def test_ollama_provider_sends_strict_non_thinking_request() -> None:
    config = AiConfig(provider=AiProviderName.OLLAMA, model="qwen3:8b")
    response = MagicMock()
    response.read.return_value = json.dumps({"response": "Bugün geldi."}).encode()
    response.__enter__.return_value = response

    with patch("urllib.request.urlopen", return_value=response) as urlopen:
        result = OllamaProvider(config).repair_text("Bug ün geldi.")

    request = urlopen.call_args.args[0]
    payload = json.loads(request.data.decode())
    assert result == "Bugün geldi."
    assert payload["system"] == REPAIR_PROMPT
    assert payload["prompt"] == "Bug ün geldi."
    assert payload["think"] is False
    assert payload["stream"] is False
