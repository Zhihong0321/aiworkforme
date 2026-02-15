import os
import httpx
from typing import List, Dict, Optional, Any
from openai import AsyncOpenAI, RateLimitError
from openai.types.chat import ChatCompletionMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

class ZaiClient:
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.z.ai/api/coding/paas/v4", timeout: int = 300):
        self.api_key = api_key or "EMPTY_KEY"
        self.base_url = base_url
        self.timeout = timeout
        
        # Create a custom Async HTTP client for better performance and stability
        self.http_client = httpx.AsyncClient(
            timeout=float(self.timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=self.http_client
        )

    def update_api_key(self, api_key: str):
        """Update the API key and re-initialize the client."""
        if not api_key:
            return
        self.api_key = api_key
        self.client = AsyncOpenAI(
            api_key=self.api_key,
            base_url=self.base_url,
            http_client=self.http_client
        )
        print(f"ZaiClient API Key updated to: {api_key[:4]}***")

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
        include_reasoning: bool = True
    ) -> ChatCompletionMessage:
        """
        Send a chat request to Z.ai API, optionally with tools.
        Returns the full message object (content, tool_calls, etc).
        Retries on RateLimitError up to 3 times.
        """
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

            response = await self.client.chat.completions.create(**kwargs)
            message = response.choices[0].message
            
            # Handle reasoning content fallback logic
            content = message.content
            reasoning_content = getattr(message, "reasoning_content", None)
            
            if include_reasoning and not content and reasoning_content:
                message.content = reasoning_content
                
            return message

        except Exception as e:
            raise e

    @retry(
        retry=retry_if_exception_type(RateLimitError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10)
    )
    async def chat_stream(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "glm-4.7-flash", 
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_choice: Optional[Any] = None,
        stream_options: Optional[Dict[str, Any]] = None
    ):
        """
        Send a streaming chat request to Z.ai API.
        Yields chunks of the response.
        Retries on RateLimitError.
        """
        try:
            kwargs = {
                "model": model,
                "messages": messages,
                "temperature": 0.7,
                "max_tokens": 2000,
                "stream": True
            }
            if tools:
                kwargs["tools"] = tools
            if tool_choice:
                kwargs["tool_choice"] = tool_choice
            if stream_options:
                kwargs["stream_options"] = stream_options

            stream = await self.client.chat.completions.create(**kwargs)
            async for chunk in stream:
                yield chunk

        except Exception as e:
            raise e
