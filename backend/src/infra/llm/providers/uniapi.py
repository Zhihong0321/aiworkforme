import os
import logging
import httpx
from typing import List, Dict, Optional, Any

from ..schemas import LLMRequest, LLMResponse, LLMMessage
from ..base import BaseLLMProvider

logger = logging.getLogger(__name__)

class UniAPIProvider(BaseLLMProvider):
    """
    Adapter for UniAPI (targeting Gemini models).
    """
    def __init__(self, api_key: Optional[str] = None, base_url: str = "https://api.uniapi.io"):
        self.api_key = api_key or os.getenv("UNIAPI_API_KEY")
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(timeout=60.0)

    def is_healthy(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        api_key = self.api_key or os.getenv("UNIAPI_API_KEY")
        if not api_key:
            raise ValueError("UniAPIProvider not configured (missing API Key)")
        logger.info(f"UniAPIProvider Generating. Request Extra Params: {request.extra_params}")

        model = "gemini-3-flash-preview"
        url = f"{self.base_url}/gemini/v1beta/models/{model}:generateContent"
        
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json"
        }

        import base64
        # Gemini style content conversion
        gemini_contents = []
        system_instruction = None

        # Check for image content in extra_params (from KnowledgeProcessor via Router)
        image_content = request.extra_params.get("image_content")
        image_mime = request.extra_params.get("image_mime_type", "image/jpeg")

        last_role = None
        for msg in request.messages:
            if msg.role == "system":
                # Accumulate system instructions
                text = msg.content or ""
                if system_instruction:
                   system_instruction["parts"][0]["text"] += "\n" + text
                else:
                   system_instruction = {"parts": [{"text": text}]}
                continue

            # Map generic roles to Gemini roles
            # Gemini only supports "user" and "model" in the contents list.
            # "assistant" -> "model"
            # "tool" -> "user" (Contextually, tool outputs are inputs to the model, so we treat them as user-side data for now)
            gemini_role = "model" if msg.role == "assistant" else "user"
            
            content_text = msg.content or ""
            
            # Handle image attachment (only for first user message)
            current_parts = [{"text": content_text}]
            
            if image_content and gemini_role == "user" and not any(c["role"] == "user" for c in gemini_contents):
                 b64_data = base64.b64encode(image_content).decode('utf-8')
                 current_parts.append({
                    "inline_data": {
                        "mime_type": image_mime,
                        "data": b64_data
                    }
                 })
                 image_content = None

            # Merge with previous message if role matches (Strict Turn-Taking)
            if gemini_contents and gemini_contents[-1]["role"] == gemini_role:
                gemini_contents[-1]["parts"].extend(current_parts)
            else:
                gemini_contents.append({
                    "role": gemini_role,
                    "parts": current_parts
                })

        payload: Dict[str, Any] = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            }
        }

        if system_instruction:
            payload["system_instruction"] = system_instruction
        
        if request.response_format and request.response_format.get("type") == "json_object":
            payload["generationConfig"]["responseMimeType"] = "application/json"

        try:
            response = await self.http_client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            data = response.json()
            
            # Parse Gemini response
            candidate = data["candidates"][0]
            content = candidate["content"]["parts"][0]["text"]
            
            return LLMResponse(
                content=content,
                usage=data.get("usageMetadata", {}),
                provider_info={
                    "provider": "uniapi",
                    "model": model
                }
            )
        except Exception as e:
            logger.error(f"UniAPIProvider Error: {e}")
            raise

    async def close(self):
        await self.http_client.aclose()
