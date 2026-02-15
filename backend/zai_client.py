import os
import httpx
import logging
import json
from typing import List, Dict, Optional, Any
from openai import AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

logger = logging.getLogger(__name__)

class ZaiClient:
    """
    Resilient Z.ai Client.
    Does NOT crash if API key is missing; gracefully waits for configuration.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.z.ai/api/coding/paas/v4", timeout: int = 300):
        self._api_key = api_key
        self.base_url = base_url
        self.timeout = timeout
        self._client: Optional[AsyncOpenAI] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        
        if self._api_key and self._api_key != "EMPTY_KEY":
            self._init_client()

    def _init_client(self):
        """Internal initialization of the OpenAI client."""
        if not self._http_client:
            self._http_client = httpx.AsyncClient(
                timeout=float(self.timeout),
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        
        self._client = AsyncOpenAI(
            api_key=self._api_key,
            base_url=self.base_url,
            http_client=self._http_client
        )
        logger.info(f"ZaiClient initialized with key ending in ...{self._api_key[-4:] if self._api_key else 'NONE'}")

    @property
    def is_configured(self) -> bool:
        return self._api_key is not None and len(self._api_key) > 5 and self._api_key != "EMPTY_KEY"

    def update_api_key(self, api_key: str):
        """Update the API key and re-initialize the client safely."""
        if not api_key:
            return
        self._api_key = api_key
        self._init_client()

    async def _ensure_client(self):
        """Check if configured before attempting a call."""
        if not self._client:
            # Fallback for startup race conditions
            key = os.getenv("ZAI_API_KEY")
            if key and key != "EMPTY_KEY":
                self.update_api_key(key)
                return self._client
            raise ValueError("ZaiClient is not configured. Please set ZAI_API_KEY in settings.")
        return self._client

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def chat(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "glm-4.7-flash", 
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        include_reasoning: bool = True,
        response_format: Optional[Dict[str, Any]] = None
    ) -> ChatCompletionMessage:
        client = await self._ensure_client()
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000
            }
            if tools:
                kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice
            if response_format:
                kwargs["response_format"] = response_format

            response = await client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            content = message.content
            reasoning_content = getattr(message, "reasoning_content", None)
            
            if include_reasoning and not content and reasoning_content:
                message.content = reasoning_content
                
            return message
        except Exception as e:
            logger.error(f"ZaiClient Chat Error: {e}")
            raise e
