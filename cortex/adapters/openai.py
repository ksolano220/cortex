import os
from typing import List, Dict, Any

from cortex.adapters.base import ModelAdapter


class OpenAIAdapter(ModelAdapter):
    def __init__(self, model: str = "gpt-4o", api_key: str = None):
        self._model = model
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self._api_key:
            from cortex.vault import Vault
            self._api_key = Vault().get("OPENAI_API_KEY")
        if not self._api_key:
            raise ValueError("OPENAI_API_KEY is required — set it with: cortex vault set OPENAI_API_KEY")

        from openai import OpenAI
        self._client = OpenAI(api_key=self._api_key)

    def chat(self, messages: List[Dict[str, str]], system: str = "") -> str:
        all_messages = []
        if system:
            all_messages.append({"role": "system", "content": system})
        all_messages.extend(messages)

        response = self._client.chat.completions.create(
            model=self._model,
            messages=all_messages,
        )
        return response.choices[0].message.content

    def provider_name(self) -> str:
        return "openai"

    def model_name(self) -> str:
        return self._model
