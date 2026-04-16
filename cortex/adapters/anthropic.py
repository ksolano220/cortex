import os
from typing import List, Dict, Any

from cortex.adapters.base import ModelAdapter


class AnthropicAdapter(ModelAdapter):
    def __init__(self, model: str = "claude-sonnet-4-20250514", api_key: str = None):
        self._model = model
        self._api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self._api_key:
            from cortex.vault import Vault
            self._api_key = Vault().get("ANTHROPIC_API_KEY")
        if not self._api_key:
            raise ValueError("ANTHROPIC_API_KEY is required — set it with: cortex vault set ANTHROPIC_API_KEY")

        import anthropic
        self._client = anthropic.Anthropic(api_key=self._api_key)

    def chat(self, messages: List[Dict[str, str]], system: str = "") -> str:
        kwargs = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
        }
        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)
        return response.content[0].text

    def provider_name(self) -> str:
        return "anthropic"

    def model_name(self) -> str:
        return self._model
