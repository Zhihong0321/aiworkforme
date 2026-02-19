import logging
from typing import List, Dict, Optional, Any
from openai import AsyncOpenAI
import httpx

from ..schemas import LLMRequest, LLMResponse, LLMMessage
from ..base import BaseLLMProvider

logger = logging.getLogger(__name__)

class ZaiProvider(BaseLLMProvider):
    """
    Adapter for Z.ai (GLM-based) LLM provider.
    """
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.z.ai/api/coding/paas/v4"):
        self.api_key = api_key
        self.base_url = base_url
        self._client: Optional[AsyncOpenAI] = None
        self._http_client: Optional[httpx.AsyncClient] = None
        
        if self.is_healthy():
            self._init_client()

    def _init_client(self):
        if not self._http_client:
            self._http_client = httpx.AsyncClient(
                timeout=300.0,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
            )
        
        self._client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=self._http_client
        )

    def is_healthy(self) -> bool:
        return bool(self.api_key and self.api_key != "EMPTY_KEY" and len(self.api_key) > 5)

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key.strip() if api_key else None
        if self.is_healthy():
            self._init_client()
        else:
            self._client = None

    async def generate(self, request: LLMRequest) -> LLMResponse:
        if not self._client:
            if self.is_healthy():
                self._init_client()
            else:
                raise ValueError("ZaiProvider not configured (missing API Key)")

        # Map task to model
        model_map = {
            "conversation": "glm-4.7-flash",
            "extraction": "glm-4.7-flash",
            "reasoning": "glm-4.7-flash", # Could use a smarter model if available
            "tool_use": "glm-4.7-flash"
        }
        model = model_map.get(request.task.value, "glm-4.7-flash")

        # Map messages to OpenAI format
        messages = []
        for msg in request.messages:
            m = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                m["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                m["tool_call_id"] = msg.tool_call_id
            messages.append(m)

        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }

        if request.tools:
            kwargs["tools"] = request.tools
        
        if request.response_format:
            kwargs["response_format"] = request.response_format

        try:
            response = await self._client.chat.completions.create(**kwargs)
            choice = response.choices[0].message
            
            content = choice.content
            reasoning = getattr(choice, "reasoning_content", None)
            
            # Map tool calls
            tool_calls = None
            if choice.tool_calls:
                tool_calls = [
                    {
                        "id": tc.id,
                        "type": tc.type,
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments
                        }
                    } for tc in choice.tool_calls
                ]

            return LLMResponse(
                content=content,
                tool_calls=tool_calls,
                reasoning=reasoning,
                usage={
                    "prompt_tokens": response.usage.prompt_tokens,
                    "completion_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                },
                provider_info={
                    "provider": "zai",
                    "model": model
                }
            )
        except Exception as e:
            logger.error(f"ZaiProvider Error: {e}")
            raise
