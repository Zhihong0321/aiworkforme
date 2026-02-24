import asyncio
from types import SimpleNamespace

from src.app import background_tasks_ai_crm as ai_crm_tasks
from src.app import background_tasks_inbound as inbound_tasks
from src.app import background_tasks_messaging as messaging_tasks
from src.app.runtime import agent_runtime as agent_runtime_mod


class _LoopExit(Exception):
    pass


class _FakeSessionCtx:
    def __init__(self, engine):
        self.engine = engine

    def __enter__(self):
        return object()

    def __exit__(self, exc_type, exc, tb):
        return False


class _FakeSession:
    def __init__(self):
        self.commits = 0
        self.added = []

    def add(self, obj):
        self.added.append(obj)

    def commit(self):
        self.commits += 1

    def refresh(self, _obj):
        return None

    def get(self, _model, _id):
        return None


class _FakePolicy:
    def __init__(self, pre_allow: bool, pre_reason: str, risk_allow: bool = True, risk_reason: str = "OK"):
        self.pre_allow = pre_allow
        self.pre_reason = pre_reason
        self.risk_allow = risk_allow
        self.risk_reason = risk_reason
        self.recorded = []
        self.validate_calls = 0

    def evaluate_outbound(self, *_args, **_kwargs):
        return SimpleNamespace(allow_send=self.pre_allow, reason_code=self.pre_reason)

    def record_decision(self, decision):
        self.recorded.append(decision)

    def validate_risk(self, *_args, **_kwargs):
        self.validate_calls += 1
        return SimpleNamespace(allow_send=self.risk_allow, reason_code=self.risk_reason)


class _FakeBuilder:
    async def build_context(self, *_args, **_kwargs):
        return {"system_instruction": "SYS"}


class _FakeRouter:
    def __init__(self, content: str):
        self.content = content
        self.calls = []

    async def execute(self, **kwargs):
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=self.content,
            provider_info={"provider": "uniapi", "model": "test-model"},
            usage={"prompt_tokens": 11, "completion_tokens": 7, "total_tokens": 18},
        )


def test_background_outbound_dispatch_loop_processes_available_work(monkeypatch):
    calls = {"tenant_ids": 0, "dispatch": []}
    sleep_calls = []

    monkeypatch.setattr(messaging_tasks, "_get_engine", lambda: object())
    monkeypatch.setattr(messaging_tasks, "Session", _FakeSessionCtx)

    def _list_tenants(_session):
        calls["tenant_ids"] += 1
        return [101, 202]

    tenant_dispatch_budget = {101: 2, 202: 1}

    def _dispatch(_session, tenant_id):
        calls["dispatch"].append(tenant_id)
        if tenant_dispatch_budget.get(tenant_id, 0) > 0:
            tenant_dispatch_budget[tenant_id] -= 1
            return {"ok": True}
        return None

    async def _sleep(seconds):
        sleep_calls.append(seconds)
        raise _LoopExit()

    monkeypatch.setattr(messaging_tasks, "list_tenant_ids_with_queued_outbound", _list_tenants)
    monkeypatch.setattr(messaging_tasks, "dispatch_next_outbound_for_tenant", _dispatch)
    monkeypatch.setattr(messaging_tasks.asyncio, "sleep", _sleep)

    try:
        asyncio.run(messaging_tasks.background_outbound_dispatch_loop())
    except _LoopExit:
        pass

    assert calls["tenant_ids"] == 1
    assert calls["dispatch"] == [101, 101, 101, 202, 202]
    assert sleep_calls == [0]


def test_background_outbound_dispatch_loop_sleeps_when_idle(monkeypatch):
    sleep_calls = []

    monkeypatch.setattr(messaging_tasks, "_get_engine", lambda: object())
    monkeypatch.setattr(messaging_tasks, "Session", _FakeSessionCtx)
    monkeypatch.setattr(messaging_tasks, "list_tenant_ids_with_queued_outbound", lambda _session: [])
    monkeypatch.setattr(messaging_tasks, "dispatch_next_outbound_for_tenant", lambda *_args: None)

    async def _sleep(seconds):
        sleep_calls.append(seconds)
        raise _LoopExit()

    monkeypatch.setattr(messaging_tasks.asyncio, "sleep", _sleep)

    try:
        asyncio.run(messaging_tasks.background_outbound_dispatch_loop())
    except _LoopExit:
        pass

    assert sleep_calls == [messaging_tasks.OUTBOUND_POLL_SECONDS]


def test_background_ai_crm_loop_runs_cycle_and_sleeps(monkeypatch):
    calls = {"router": 0, "cycle": 0}
    sleep_calls = []

    monkeypatch.setattr(ai_crm_tasks, "_get_engine", lambda: object())
    monkeypatch.setattr(ai_crm_tasks, "Session", _FakeSessionCtx)

    def _router():
        calls["router"] += 1
        return "router"

    async def _cycle(_session, llm_router):
        calls["cycle"] += 1
        assert llm_router == "router"
        return {"scanned": 1, "triggered": 0}

    async def _sleep(seconds):
        sleep_calls.append(seconds)
        raise _LoopExit()

    monkeypatch.setattr(ai_crm_tasks, "get_default_ai_crm_llm_router", _router)
    monkeypatch.setattr(ai_crm_tasks, "run_ai_crm_background_cycle", _cycle)
    monkeypatch.setattr(ai_crm_tasks.asyncio, "sleep", _sleep)

    try:
        asyncio.run(ai_crm_tasks.background_ai_crm_loop())
    except _LoopExit:
        pass

    assert calls["router"] == 1
    assert calls["cycle"] == 1
    assert sleep_calls == [ai_crm_tasks.AI_CRM_POLL_SECONDS]


def test_background_ai_crm_loop_recovers_from_cycle_exception(monkeypatch):
    sleep_calls = []

    monkeypatch.setattr(ai_crm_tasks, "_get_engine", lambda: object())
    monkeypatch.setattr(ai_crm_tasks, "Session", _FakeSessionCtx)
    monkeypatch.setattr(ai_crm_tasks, "get_default_ai_crm_llm_router", lambda: "router")

    async def _cycle(_session, _router):
        raise RuntimeError("boom")

    async def _sleep(seconds):
        sleep_calls.append(seconds)
        raise _LoopExit()

    monkeypatch.setattr(ai_crm_tasks, "run_ai_crm_background_cycle", _cycle)
    monkeypatch.setattr(ai_crm_tasks.asyncio, "sleep", _sleep)

    try:
        asyncio.run(ai_crm_tasks.background_ai_crm_loop())
    except _LoopExit:
        pass

    assert sleep_calls == [ai_crm_tasks.AI_CRM_POLL_SECONDS]


def test_process_one_inbound_handles_no_agent(monkeypatch):
    session = _FakeSession()
    message = type(
        "Msg",
        (),
        {
            "id": 1,
            "tenant_id": 99,
            "lead_id": 88,
            "delivery_status": "received",
            "updated_at": None,
            "text_content": "hi",
        },
    )()

    monkeypatch.setattr(inbound_tasks, "_resolve_thread_agent", lambda *_args: None)

    asyncio.run(inbound_tasks._process_one_inbound(session, message))

    assert message.delivery_status == "inbound_human_takeover"
    assert session.commits >= 2


def test_process_one_inbound_handles_blocked_result(monkeypatch):
    session = _FakeSession()
    message = type(
        "Msg",
        (),
        {
            "id": 2,
            "tenant_id": 99,
            "lead_id": 88,
            "delivery_status": "received",
            "updated_at": None,
            "text_content": "hi",
        },
    )()
    lead = type("LeadObj", (), {"workspace_id": 77})()
    agent = type("AgentObj", (), {"id": 33, "name": "A"})()

    monkeypatch.setattr(inbound_tasks, "_resolve_thread_agent", lambda *_args: agent)
    monkeypatch.setattr(inbound_tasks, "_build_thread_history", lambda *_args: [])
    monkeypatch.setattr(inbound_tasks, "_get_llm_router", lambda: object())

    class _Runtime:
        def __init__(self, _session, _router):
            pass

        async def run_turn(self, **_kwargs):
            return {"status": "blocked", "reason": "policy"}

    monkeypatch.setattr(inbound_tasks, "ConversationAgentRuntime", _Runtime)
    monkeypatch.setattr(session, "get", lambda _model, _id: lead)

    asyncio.run(inbound_tasks._process_one_inbound(session, message))

    assert message.delivery_status == "inbound_human_takeover"
    assert session.commits >= 2


def test_process_one_inbound_handles_sent_result(monkeypatch):
    session = _FakeSession()
    message = type(
        "Msg",
        (),
        {
            "id": 3,
            "tenant_id": 99,
            "lead_id": 88,
            "delivery_status": "received",
            "updated_at": None,
            "text_content": "hello",
        },
    )()
    lead = type("LeadObj", (), {"workspace_id": 77})()
    agent = type("AgentObj", (), {"id": 44, "name": "B"})()
    enqueue_calls = []

    monkeypatch.setattr(inbound_tasks, "_resolve_thread_agent", lambda *_args: agent)
    monkeypatch.setattr(inbound_tasks, "_build_thread_history", lambda *_args: [])
    monkeypatch.setattr(inbound_tasks, "_get_llm_router", lambda: object())
    monkeypatch.setattr(
        inbound_tasks,
        "_enqueue_outbound_reply",
        lambda *_args, **_kwargs: enqueue_calls.append(True),
    )

    class _Runtime:
        def __init__(self, _session, _router):
            pass

        async def run_turn(self, **_kwargs):
            return {"status": "sent", "content": "reply"}

    monkeypatch.setattr(inbound_tasks, "ConversationAgentRuntime", _Runtime)
    monkeypatch.setattr(session, "get", lambda _model, _id: lead)

    asyncio.run(inbound_tasks._process_one_inbound(session, message))

    assert message.delivery_status == "inbound_ai_replied"
    assert enqueue_calls == [True]


def test_prepare_media_inbound_for_runtime_pdf(monkeypatch):
    message = type(
        "Msg",
        (),
        {
            "message_type": "document",
            "text_content": "please check",
            "media_url": "https://cdn.example.com/invoice.pdf",
            "raw_payload": {
                "message": {
                    "documentMessage": {
                        "mimetype": "application/pdf",
                        "fileName": "invoice.pdf",
                    }
                }
            },
        },
    )()

    async def _fake_download(_url):
        return b"%PDF-sample%"

    monkeypatch.setattr(inbound_tasks, "_download_pdf_bytes", _fake_download)
    monkeypatch.setattr(
        inbound_tasks,
        "_extract_pdf_text",
        lambda _bytes: {"pages_read": 2, "text": "line one", "text_truncated": False},
    )

    prepared = asyncio.run(inbound_tasks._prepare_media_inbound_for_runtime(message))

    assert getattr(prepared["task"], "value", None) == "pdf"
    assert prepared["processing"]["status"] == "ok"
    assert prepared["processing"]["pages_read"] == 2
    assert "User attached a PDF document." in prepared["user_message"]


def test_prepare_media_inbound_for_runtime_image(monkeypatch):
    message = type(
        "Msg",
        (),
        {
            "message_type": "image",
            "text_content": "what is this?",
            "media_url": "https://cdn.example.com/photo.jpg",
            "raw_payload": {
                "message": {
                    "imageMessage": {
                        "mimetype": "image/jpeg",
                        "fileName": "photo.jpg",
                    }
                }
            },
        },
    )()

    async def _fake_download(_url):
        return b"image-bytes"

    monkeypatch.setattr(inbound_tasks, "_download_image_bytes", _fake_download)

    prepared = asyncio.run(inbound_tasks._prepare_media_inbound_for_runtime(message))

    assert getattr(prepared["task"], "value", None) == "images"
    assert prepared["processing"]["status"] == "ok"
    assert prepared["processing"]["bytes"] == len(b"image-bytes")
    assert prepared["llm_extra_params"]["image_content"] == b"image-bytes"
    assert prepared["llm_extra_params"]["image_mime_type"] == "image/jpeg"
    assert "User attached an image." in prepared["user_message"]


def test_message_media_url_supports_nested_payload_url():
    message = type(
        "Msg",
        (),
        {
            "media_url": None,
            "raw_payload": {
                "message": {
                    "imageMessage": {
                        "url": "https://cdn.example.com/nested-image.jpg",
                    }
                }
            },
        },
    )()

    resolved = inbound_tasks._message_media_url(message)
    assert resolved == "https://cdn.example.com/nested-image.jpg"


def test_prepare_media_inbound_for_runtime_voice_note(monkeypatch):
    message = type(
        "Msg",
        (),
        {
            "message_type": "audio",
            "text_content": None,
            "media_url": "https://cdn.example.com/voice.ogg",
            "raw_payload": {
                "message": {
                    "audioMessage": {
                        "mimetype": "audio/ogg",
                        "fileName": "voice.ogg",
                    }
                }
            },
        },
    )()

    async def _fake_download(_url):
        return b"audio-bytes"

    async def _fake_transcribe(_bytes, _mime, _media_url=""):
        return "hello from voice note"

    monkeypatch.setattr(inbound_tasks, "_download_audio_bytes", _fake_download)
    monkeypatch.setattr(inbound_tasks, "_transcribe_voice_note", _fake_transcribe)

    prepared = asyncio.run(inbound_tasks._prepare_media_inbound_for_runtime(message))

    assert getattr(prepared["task"], "value", None) == "conversation"
    assert prepared["processing"]["status"] == "ok"
    assert prepared["processing"]["bytes"] == len(b"audio-bytes")
    assert prepared["processing"]["transcript_chars"] == len("hello from voice note")
    assert prepared["should_run_runtime"] is True
    assert "Voice note transcript" in prepared["user_message"]


def test_prepare_media_inbound_for_runtime_blocks_unprocessable_media_without_text():
    message = type(
        "Msg",
        (),
        {
            "message_type": "video",
            "text_content": None,
            "media_url": None,
            "raw_payload": {},
        },
    )()

    prepared = asyncio.run(inbound_tasks._prepare_media_inbound_for_runtime(message))

    assert prepared["should_run_runtime"] is False
    assert prepared["skip_reason"] == "UNPROCESSABLE_MEDIA_NO_TEXT"
    assert prepared["processing"]["status"] == "error"


def test_process_one_inbound_skips_runtime_for_unprocessable_media(monkeypatch):
    session = _FakeSession()
    message = type(
        "Msg",
        (),
        {
            "id": 4,
            "tenant_id": 99,
            "lead_id": 88,
            "delivery_status": "received",
            "updated_at": None,
            "text_content": None,
            "raw_payload": {},
        },
    )()
    lead = type("LeadObj", (), {"workspace_id": 77})()
    agent = type("AgentObj", (), {"id": 55, "name": "C"})()

    monkeypatch.setattr(inbound_tasks, "_resolve_thread_agent", lambda *_args: agent)
    monkeypatch.setattr(inbound_tasks, "_build_thread_history", lambda *_args: [])
    async def _fake_prepare(*_args):
        return {
            "task": None,
            "user_message": "",
            "processing": {"type": "image", "status": "error", "error": "No media_url found"},
            "llm_extra_params": None,
            "should_run_runtime": False,
            "skip_reason": "IMAGE_PROCESSING_FAILED_NO_TEXT",
        }

    monkeypatch.setattr(inbound_tasks, "_prepare_media_inbound_for_runtime", _fake_prepare)
    monkeypatch.setattr(session, "get", lambda _model, _id: lead)

    class _Runtime:
        def __init__(self, *_args, **_kwargs):
            raise AssertionError("Runtime should not be instantiated when media processing blocks")

    monkeypatch.setattr(inbound_tasks, "ConversationAgentRuntime", _Runtime)

    asyncio.run(inbound_tasks._process_one_inbound(session, message))

    assert message.delivery_status == "inbound_human_takeover"
    assert message.raw_payload["inbound_skip_reason"] == "IMAGE_PROCESSING_FAILED_NO_TEXT"
    assert session.commits >= 2


def test_agent_runtime_run_turn_blocks_before_llm_call():
    session = _FakeSession()
    router = _FakeRouter(content="should-not-be-used")
    runtime = agent_runtime_mod.ConversationAgentRuntime(session, router)
    runtime.policy = _FakePolicy(pre_allow=False, pre_reason="OUTBOUND_CAP_24H")
    runtime.builder = _FakeBuilder()

    result = asyncio.run(
        runtime.run_turn(
            lead_id=10,
            workspace_id=20,
            user_message="hello",
            history_override=[],
        )
    )

    assert result == {"status": "blocked", "reason": "OUTBOUND_CAP_24H"}
    assert router.calls == []
    assert len(runtime.policy.recorded) == 1
    assert runtime.policy.validate_calls == 0


def test_agent_runtime_run_turn_sent_path_with_history_override():
    Workspace = type("WorkspaceModel", (), {})
    Agent = type("AgentModel", (), {})
    workspace_obj = SimpleNamespace(agent_id=77)
    agent_obj = SimpleNamespace(model="override-model")

    class _Session:
        def get(self, model, _id):
            if model is Workspace:
                return workspace_obj
            if model is Agent:
                return agent_obj
            return None

    session = _Session()
    router = _FakeRouter(content="assistant reply")
    runtime = agent_runtime_mod.ConversationAgentRuntime(session, router)
    runtime.policy = _FakePolicy(pre_allow=True, pre_reason="POLICY_PASSED", risk_allow=True)
    runtime.builder = _FakeBuilder()
    runtime._crm_models = lambda: (object, Workspace, object, object, object)
    runtime._agent_model = lambda: Agent
    runtime._llm_task = lambda: SimpleNamespace(CONVERSATION=SimpleNamespace(value="conversation"))
    runtime._estimate_llm_cost = lambda: (lambda *_args: 0.123)
    runtime._get_bool_system_setting = lambda: (lambda *_args, **_kwargs: False)

    result = asyncio.run(
        runtime.run_turn(
            lead_id=10,
            workspace_id=20,
            user_message="hello",
            history_override=[{"role": "assistant", "content": "prev"}],
        )
    )

    assert result["status"] == "sent"
    assert result["content"] == "assistant reply"
    assert result["llm_model"] == "test-model"
    assert result["llm_prompt_tokens"] == 11
    assert result["llm_completion_tokens"] == 7
    assert result["llm_total_tokens"] == 18
    assert result["llm_estimated_cost_usd"] == 0.123
    assert result["ai_trace"]["task"] == "conversation"
    assert result["ai_trace"]["context_prompt"] is None
    assert len(router.calls) == 1
    assert "model" not in router.calls[0]
    assert len(runtime.policy.recorded) == 2


def test_agent_runtime_run_turn_uses_task_override():
    Workspace = type("WorkspaceModel", (), {})
    Agent = type("AgentModel", (), {})
    workspace_obj = SimpleNamespace(agent_id=77)
    agent_obj = SimpleNamespace(model="override-model")

    class _Task:
        def __init__(self, value):
            self.value = value

    class _TaskEnum:
        CONVERSATION = _Task("conversation")
        PDF = _Task("pdf")

        def __call__(self, value):
            if value == "pdf":
                return self.PDF
            return self.CONVERSATION

    class _Session:
        def get(self, model, _id):
            if model is Workspace:
                return workspace_obj
            if model is Agent:
                return agent_obj
            return None

    session = _Session()
    router = _FakeRouter(content="assistant reply")
    runtime = agent_runtime_mod.ConversationAgentRuntime(session, router)
    runtime.policy = _FakePolicy(pre_allow=True, pre_reason="POLICY_PASSED", risk_allow=True)
    runtime.builder = _FakeBuilder()
    runtime._crm_models = lambda: (object, Workspace, object, object, object)
    runtime._agent_model = lambda: Agent
    runtime._llm_task = lambda: _TaskEnum()
    runtime._estimate_llm_cost = lambda: (lambda *_args: 0.123)
    runtime._get_bool_system_setting = lambda: (lambda *_args, **_kwargs: False)

    result = asyncio.run(
        runtime.run_turn(
            lead_id=10,
            workspace_id=20,
            user_message="hello",
            history_override=[],
            task_override="pdf",
            llm_extra_params={"image_content": b"img", "image_mime_type": "image/jpeg"},
        )
    )

    assert result["status"] == "sent"
    assert result["ai_trace"]["task"] == "pdf"
    assert router.calls[0]["task"].value == "pdf"
    assert router.calls[0]["image_content"] == b"img"
    assert router.calls[0]["image_mime_type"] == "image/jpeg"
