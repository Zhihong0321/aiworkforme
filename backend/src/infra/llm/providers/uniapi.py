import logging
import httpx
import asyncio
from typing import Dict, Optional, Any, List

from ..schemas import LLMRequest, LLMResponse, LLMMessage
from ..base import BaseLLMProvider

logger = logging.getLogger(__name__)

class UniAPIProvider(BaseLLMProvider):
    """
    Adapter for UniAPI with multi-schema support.
    Supported schemas:
    - gemini_native: /gemini/v1beta/models/{model}:generateContent
    - openai_chat: /v1/chat/completions
    - openai_responses: /v1/responses
    - ali_asr_filetrans: /ali/api/v1/services/audio/asr/transcription
    """
    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = "https://api.uniapi.io",
        default_model: str = "gemini-3-flash-preview",
        default_schema: str = "gemini_native",
    ):
        self.api_key = api_key
        self.base_url = base_url
        self.default_model = default_model
        self.default_schema = default_schema
        self.http_client = httpx.AsyncClient(timeout=60.0)

    # Curated model catalog for OpenAI-compatible UniAPI endpoints.
    OPENAI_CHAT_MODELS: List[str] = [
        "gpt-5-nano-2025-08-07",
        "gpt-oss-120b",
        "gpt-5.1-chat-latest",
        "deepseek-v3.2#thinking",
        "deepseek-v3.2-speciale",
        "grok-4-1-fast",
        "doubao-seed-1-6-251015",
    ]

    GEMINI_NATIVE_MODELS: List[str] = [
        "gemini-3-flash-preview",
    ]

    ALI_ASR_FILETRANS_MODELS: List[str] = [
        "qwen3-asr-flash-filetrans",
    ]

    def set_api_key(self, api_key: str) -> None:
        self.api_key = api_key.strip() if api_key else None

    def list_supported_models(self) -> List[Dict[str, str]]:
        models: List[Dict[str, str]] = []
        for model in self.GEMINI_NATIVE_MODELS:
            models.append(
                {
                    "provider": "uniapi",
                    "model": model,
                    "schema": "gemini_native",
                }
            )
        for model in self.OPENAI_CHAT_MODELS:
            models.append(
                {
                    "provider": "uniapi",
                    "model": model,
                    "schema": "openai_chat",
                }
            )
        for model in self.ALI_ASR_FILETRANS_MODELS:
            models.append(
                {
                    "provider": "uniapi",
                    "model": model,
                    "schema": "ali_asr_filetrans",
                }
            )
        return models

    def is_healthy(self) -> bool:
        return bool(self.api_key and len(self.api_key) > 5)

    async def generate(self, request: LLMRequest) -> LLMResponse:
        api_key = self.api_key
        if not api_key:
            raise ValueError("UniAPIProvider not configured (missing API Key)")
        extra = request.extra_params or {}
        model = (extra.get("model") or extra.get("llm_model") or self.default_model).strip()
        schema = (extra.get("uniapi_schema") or "").strip().lower() or self._infer_schema(model)

        logger.info(
            "UniAPIProvider generate schema=%s model=%s extra=%s",
            schema,
            model,
            list(extra.keys()),
        )

        if schema == "gemini_native":
            return await self._generate_gemini_native(request, api_key, model)
        if schema == "openai_chat":
            return await self._generate_openai_chat(request, api_key, model)
        if schema == "openai_responses":
            return await self._generate_openai_responses(request, api_key, model)
        if schema == "ali_asr_filetrans":
            return await self._generate_ali_asr_filetrans(request, api_key, model)

        raise ValueError(f"Unsupported UniAPI schema '{schema}'")

    def _infer_schema(self, model: str) -> str:
        if model.startswith("gemini-"):
            return "gemini_native"
        if model.startswith("qwen3-asr-flash-filetrans"):
            return "ali_asr_filetrans"
        return "openai_chat"

    async def _generate_ali_asr_filetrans(
        self, request: LLMRequest, api_key: str, model: str
    ) -> LLMResponse:
        extra = request.extra_params or {}
        file_url = (
            str(
                extra.get("file_url")
                or extra.get("audio_url")
                or extra.get("media_url")
                or ""
            )
            .strip()
        )
        if not file_url:
            raise ValueError("ali_asr_filetrans requires file_url/audio_url/media_url")

        submit_url = f"{self.base_url}/ali/api/v1/services/audio/asr/transcription"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }

        params: Dict[str, Any] = {
            "channel_id": extra.get("asr_channel_id") or [0],
            "enable_itn": bool(extra.get("asr_enable_itn", False)),
        }
        if extra.get("asr_language"):
            params["language"] = str(extra["asr_language"]).strip()
        if "asr_enable_words" in extra:
            params["enable_words"] = bool(extra.get("asr_enable_words"))
        corpus_text = str(extra.get("asr_corpus_text", "") or "").strip()
        if corpus_text:
            params["corpus"] = {"text": corpus_text}

        submit_payload: Dict[str, Any] = {
            "model": model,
            "input": {"file_url": file_url},
            "parameters": params,
        }

        submit_resp = await self.http_client.post(
            submit_url, headers=headers, json=submit_payload
        )
        submit_resp.raise_for_status()
        submit_data = submit_resp.json()
        task_id = (
            ((submit_data.get("output") or {}).get("task_id"))
            if isinstance(submit_data, dict)
            else None
        )
        if not task_id:
            raise RuntimeError(f"ASR submit missing task_id: {submit_data}")

        max_polls = int(extra.get("asr_max_polls", 40) or 40)
        poll_interval = float(extra.get("asr_poll_interval_seconds", 1.0) or 1.0)
        poll_data: Dict[str, Any] = {}
        output: Dict[str, Any] = {}

        for _ in range(max_polls):
            poll_data = await self._fetch_ali_task(task_id, headers)
            output = poll_data.get("output") or {}
            task_status = str(output.get("task_status") or "").upper()
            if task_status == "SUCCEEDED":
                break
            if task_status in {"FAILED", "UNKNOWN"}:
                code = output.get("code")
                message = output.get("message")
                raise RuntimeError(f"ASR task {task_status}: {code} {message}".strip())
            await asyncio.sleep(max(poll_interval, 0.1))
        else:
            raise TimeoutError(f"ASR task polling timeout for task_id={task_id}")

        result = output.get("result") if isinstance(output, dict) else {}
        transcript = ""
        if isinstance(result, dict):
            transcription_url = str(result.get("transcription_url") or "").strip()
            if transcription_url:
                transcript_data = await self._fetch_json_or_text(transcription_url)
                transcript = self._extract_transcript_text(transcript_data)
            else:
                transcript = self._extract_transcript_text(result)
        if not transcript:
            transcript = self._extract_transcript_text(poll_data)
        if not transcript:
            raise RuntimeError("ASR task succeeded but transcript is empty")

        return LLMResponse(
            content=transcript,
            usage={},
            provider_info={"provider": "uniapi", "model": model, "schema": "ali_asr_filetrans"},
        )

    async def _fetch_ali_task(self, task_id: str, headers: Dict[str, str]) -> Dict[str, Any]:
        task_id = str(task_id).strip()
        candidates = [
            f"{self.base_url}/ali/api/v1/tasks/{task_id}",
            f"{self.base_url}/api/v1/tasks/{task_id}",
        ]
        last_error: Optional[Exception] = None
        for url in candidates:
            try:
                resp = await self.http_client.get(url, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, dict):
                    return data
                raise RuntimeError(f"Unexpected ASR task response shape from {url}")
            except Exception as exc:
                last_error = exc
                continue
        raise RuntimeError(f"ASR task polling failed for task_id={task_id}: {last_error}")

    async def _fetch_json_or_text(self, url: str) -> Any:
        resp = await self.http_client.get(url)
        resp.raise_for_status()
        content_type = str(resp.headers.get("content-type", "")).lower()
        if "application/json" in content_type:
            try:
                return resp.json()
            except Exception:
                return resp.text
        try:
            return resp.json()
        except Exception:
            return resp.text

    def _extract_transcript_text(self, payload: Any) -> str:
        chunks: List[str] = []
        self._collect_transcript_chunks(payload, chunks)
        merged = "\n".join([c for c in chunks if isinstance(c, str) and c.strip()]).strip()
        return merged

    def _collect_transcript_chunks(self, payload: Any, chunks: List[str]) -> None:
        if payload is None:
            return
        if isinstance(payload, str):
            text = payload.strip()
            if text:
                chunks.append(text)
            return
        if isinstance(payload, list):
            for item in payload:
                self._collect_transcript_chunks(item, chunks)
            return
        if not isinstance(payload, dict):
            return

        for key in ("transcript_text", "transcription_text", "text", "transcript", "sentence"):
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                chunks.append(value.strip())

        for key in ("sentences", "segments", "utterances", "transcripts", "results", "channels", "channel_results"):
            value = payload.get(key)
            if isinstance(value, (dict, list)):
                self._collect_transcript_chunks(value, chunks)

        for value in payload.values():
            if isinstance(value, (dict, list)):
                self._collect_transcript_chunks(value, chunks)

    async def _generate_gemini_native(
        self, request: LLMRequest, api_key: str, model: str
    ) -> LLMResponse:
        url = f"{self.base_url}/gemini/v1beta/models/{model}:generateContent"
        headers = {"x-goog-api-key": api_key, "Content-Type": "application/json"}

        import base64

        gemini_contents: List[Dict[str, Any]] = []
        system_instruction = None

        image_content = request.extra_params.get("image_content")
        image_mime = request.extra_params.get("image_mime_type", "image/jpeg")
        audio_content = request.extra_params.get("audio_content")
        audio_mime = request.extra_params.get("audio_mime_type", "audio/ogg")
        user_message_indexes = [
            idx
            for idx, m in enumerate(request.messages)
            if m.role != "system" and m.role != "assistant"
        ]
        last_user_index = user_message_indexes[-1] if user_message_indexes else -1

        for idx, msg in enumerate(request.messages):
            if msg.role == "system":
                text = msg.content or ""
                if system_instruction:
                    system_instruction["parts"][0]["text"] += "\n" + text
                else:
                    system_instruction = {"parts": [{"text": text}]}
                continue

            gemini_role = "model" if msg.role == "assistant" else "user"
            current_parts = [{"text": msg.content or ""}]

            if image_content and gemini_role == "user" and idx == last_user_index:
                b64_data = base64.b64encode(image_content).decode("utf-8")
                current_parts.append(
                    {"inline_data": {"mime_type": image_mime, "data": b64_data}}
                )
                image_content = None

            if audio_content and gemini_role == "user" and idx == last_user_index:
                b64_data = base64.b64encode(audio_content).decode("utf-8")
                current_parts.append(
                    {"inline_data": {"mime_type": audio_mime, "data": b64_data}}
                )
                audio_content = None

            if gemini_contents and gemini_contents[-1]["role"] == gemini_role:
                gemini_contents[-1]["parts"].extend(current_parts)
            else:
                gemini_contents.append({"role": gemini_role, "parts": current_parts})

        payload: Dict[str, Any] = {
            "contents": gemini_contents,
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }

        if system_instruction:
            payload["system_instruction"] = system_instruction
        if request.response_format and request.response_format.get("type") == "json_object":
            payload["generationConfig"]["responseMimeType"] = "application/json"

        response = await self.http_client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        candidate = (data.get("candidates") or [{}])[0]
        parts = ((candidate.get("content") or {}).get("parts") or [{}])
        content = parts[0].get("text")
        usage_metadata = data.get("usageMetadata", {}) if isinstance(data, dict) else {}

        return LLMResponse(
            content=content,
            usage={
                "prompt_tokens": int(usage_metadata.get("promptTokenCount", 0) or 0),
                "completion_tokens": int(usage_metadata.get("candidatesTokenCount", 0) or 0),
                "total_tokens": int(usage_metadata.get("totalTokenCount", 0) or 0),
                "raw_usage": usage_metadata,
            },
            provider_info={"provider": "uniapi", "model": model, "schema": "gemini_native"},
        )

    async def _generate_openai_chat(
        self, request: LLMRequest, api_key: str, model: str
    ) -> LLMResponse:
        url = f"{self.base_url}/v1/chat/completions"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        messages: List[Dict[str, Any]] = []
        for msg in request.messages:
            mapped: Dict[str, Any] = {"role": msg.role, "content": msg.content}
            if msg.tool_calls:
                mapped["tool_calls"] = msg.tool_calls
            if msg.tool_call_id:
                mapped["tool_call_id"] = msg.tool_call_id
            messages.append(mapped)

        payload: Dict[str, Any] = {
            "model": model,
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if request.tools:
            payload["tools"] = request.tools
        if request.response_format:
            payload["response_format"] = request.response_format

        response = await self.http_client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        choice = (data.get("choices") or [{}])[0].get("message", {})
        usage_data = data.get("usage", {}) if isinstance(data, dict) else {}
        tool_calls = choice.get("tool_calls")

        return LLMResponse(
            content=choice.get("content"),
            tool_calls=tool_calls,
            usage={
                "prompt_tokens": int(usage_data.get("prompt_tokens", 0) or 0),
                "completion_tokens": int(usage_data.get("completion_tokens", 0) or 0),
                "total_tokens": int(usage_data.get("total_tokens", 0) or 0),
                "raw_usage": usage_data,
            },
            provider_info={"provider": "uniapi", "model": model, "schema": "openai_chat"},
        )

    async def _generate_openai_responses(
        self, request: LLMRequest, api_key: str, model: str
    ) -> LLMResponse:
        url = f"{self.base_url}/v1/responses"
        headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

        instructions = "\n".join(
            [m.content or "" for m in request.messages if m.role == "system"]
        ).strip() or None

        input_items: List[Dict[str, Any]] = []
        for msg in request.messages:
            if msg.role == "system":
                continue
            role = msg.role if msg.role in ("user", "assistant") else "user"
            input_items.append(
                {
                    "role": role,
                    "content": [{"type": "input_text", "text": msg.content or ""}],
                }
            )

        payload: Dict[str, Any] = {
            "model": model,
            "input": input_items,
            "temperature": request.temperature,
            "max_output_tokens": request.max_tokens,
        }
        if instructions:
            payload["instructions"] = instructions
        if request.tools:
            payload["tools"] = request.tools
        if request.response_format and request.response_format.get("type") == "json_object":
            payload["text"] = {"format": {"type": "json_object"}}

        response = await self.http_client.post(url, headers=headers, json=payload)
        response.raise_for_status()
        data = response.json()

        content = data.get("output_text")
        if content is None:
            content = self._extract_responses_output_text(data)

        usage_data = data.get("usage", {}) if isinstance(data, dict) else {}
        tool_calls = self._extract_response_tool_calls(data)

        return LLMResponse(
            content=content,
            tool_calls=tool_calls or None,
            usage={
                "prompt_tokens": int(usage_data.get("input_tokens", 0) or 0),
                "completion_tokens": int(usage_data.get("output_tokens", 0) or 0),
                "total_tokens": int(usage_data.get("total_tokens", 0) or 0),
                "raw_usage": usage_data,
            },
            provider_info={"provider": "uniapi", "model": model, "schema": "openai_responses"},
        )

    def _extract_responses_output_text(self, data: Dict[str, Any]) -> str:
        output = data.get("output") or []
        chunks: List[str] = []
        for item in output:
            content_items = item.get("content") if isinstance(item, dict) else None
            if not isinstance(content_items, list):
                continue
            for part in content_items:
                if part.get("type") in ("output_text", "text") and part.get("text"):
                    chunks.append(part["text"])
        return "\n".join(chunks).strip()

    def _extract_response_tool_calls(self, data: Dict[str, Any]) -> List[Dict[str, Any]]:
        output = data.get("output") or []
        tool_calls: List[Dict[str, Any]] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function_call":
                continue
            tool_calls.append(
                {
                    "id": item.get("id"),
                    "type": "function",
                    "function": {
                        "name": item.get("name"),
                        "arguments": item.get("arguments", "{}"),
                    },
                }
            )
        return tool_calls

    async def close(self):
        await self.http_client.aclose()
