from abc import ABC, abstractmethod
from typing import List, Dict, Any


class ModelAdapter(ABC):
    """Base interface for all model providers."""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], system: str = "") -> str:
        """Send messages to the model and return the response text."""
        pass

    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def model_name(self) -> str:
        pass
