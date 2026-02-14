import httpx
import json
import logging
from typing import List, Dict, Any, Optional
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

class UniAPIClient:
    """
    Client for UniAPI.io targeting Google Gemini models.
    Implements the Provider Contract defined in Masterplan M0.
    """
    def __init__(self, api_key: str, base_url: str = "https://api.uniapi.io"):
        self.api_key = api_key
        self.base_url = base_url
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def generate_content(
        self,
        messages: List[Dict[str, Any]],
        system_instruction: Optional[str] = None,
        model: str = "gemini-2.5-flash",
        generation_config: Optional[Dict[str, Any]] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        tool_config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Calls the generateContent endpoint matching the Gemini v1beta API schema.
        """
        url = f"{self.base_url}/gemini/v1beta/models/{model}:generateContent"
        
        headers = {
            "x-goog-api-key": self.api_key,
            "Content-Type": "application/json"
        }

        # Convert simple role/content messages to Gemini structured contents
        gemini_contents = []
        for msg in messages:
            gemini_contents.append({
                "role": "user" if msg["role"] == "user" else "model",
                "parts": [{"text": msg["content"]}]
            })

        payload: Dict[str, Any] = {
            "contents": gemini_contents
        }

        if system_instruction:
            payload["system_instruction"] = {
                "parts": {"text": system_instruction}
            }

        if generation_config:
            payload["generationConfig"] = generation_config
        
        if tools:
            payload["tools"] = tools
        
        if tool_config:
            payload["tool_config"] = tool_config

        try:
            response = await self.http_client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"UniAPI HTTP Error: {e.response.status_code} - {e.response.text}")
            raise
        except Exception as e:
            logger.error(f"UniAPI Connection Error: {str(e)}")
            raise

    async def close(self):
        await self.http_client.aclose()
