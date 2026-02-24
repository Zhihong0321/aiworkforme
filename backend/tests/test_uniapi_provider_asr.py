import pytest

from src.infra.llm.providers.uniapi import UniAPIProvider
from src.infra.llm.schemas import LLMMessage, LLMRequest, LLMTask


class _FakeResponse:
    def __init__(self, status_code=200, data=None, text="", headers=None):
        self.status_code = status_code
        self._data = data if data is not None else {}
        self.text = text
        self.headers = headers or {"content-type": "application/json"}

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"http error: {self.status_code}")

    def json(self):
        return self._data


class _FakeHttpClient:
    def __init__(self):
        self.poll_count = 0
        self.calls = []

    async def post(self, url, headers=None, json=None):
        self.calls.append(("POST", url, json))
        return _FakeResponse(
            data={"output": {"task_id": "task-123"}},
        )

    async def get(self, url, headers=None):
        self.calls.append(("GET", url, None))
        if "/ali/api/v1/tasks/task-123" in url:
            self.poll_count += 1
            if self.poll_count == 1:
                return _FakeResponse(data={"output": {"task_status": "RUNNING"}})
            return _FakeResponse(
                data={
                    "output": {
                        "task_status": "SUCCEEDED",
                        "result": {"transcription_url": "https://example.com/asr-result.json"},
                    }
                }
            )
        if url == "https://example.com/asr-result.json":
            return _FakeResponse(
                data={"transcripts": [{"text": "repeat what is said, voice note is ok"}]}
            )
        return _FakeResponse(status_code=404, data={"error": "not found"})


def test_uniapi_models_include_ali_asr_filetrans():
    provider = UniAPIProvider(api_key="dummy")
    models = provider.list_supported_models()
    assert any(
        m.get("model") == "qwen3-asr-flash-filetrans"
        and m.get("schema") == "ali_asr_filetrans"
        for m in models
    )


@pytest.mark.asyncio
async def test_uniapi_ali_asr_filetrans_generate_transcript():
    provider = UniAPIProvider(api_key="dummy")
    fake_http = _FakeHttpClient()
    provider.http_client = fake_http

    req = LLMRequest(
        task=LLMTask.VOICE_NOTE,
        messages=[LLMMessage(role="user", content="Transcribe this voice note to text.")],
        extra_params={
            "model": "qwen3-asr-flash-filetrans",
            "audio_url": "https://example.com/voice.ogg",
            "asr_poll_interval_seconds": 0,
            "asr_max_polls": 3,
        },
    )

    resp = await provider.generate(req)

    assert resp.provider_info.get("schema") == "ali_asr_filetrans"
    assert resp.provider_info.get("model") == "qwen3-asr-flash-filetrans"
    assert "voice note is ok" in (resp.content or "")
