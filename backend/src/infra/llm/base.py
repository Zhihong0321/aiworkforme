from abc import ABC, abstractmethod
from typing import Optional
from .schemas import LLMRequest, LLMResponse

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate(self, request: LLMRequest) -> LLMResponse:
        """
        Takes a unified LLMRequest and returns a unified LLMResponse.
        """
        pass

    @abstractmethod
    def is_healthy(self) -> bool:
        """
        Checks if the provider is correctly configured and reachable.
        """
        pass
