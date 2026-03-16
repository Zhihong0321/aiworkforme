import asyncio

from src.app import background_tasks_inbound as inbound_tasks


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


def test_process_one_inbound_filters_unsupported_runtime_kwargs(monkeypatch):
    session = _FakeSession()
    message = type(
        "Msg",
        (),
        {
            "id": 30,
            "tenant_id": 99,
            "lead_id": 88,
            "thread_id": 777,
            "delivery_status": "received",
            "updated_at": None,
            "text_content": "hello",
        },
    )()
    lead = type("LeadObj", (), {"workspace_id": 77})()
    agent = type("AgentObj", (), {"id": 44, "name": "Compat Agent"})()
    captured = {}
    enqueue_calls = []

    monkeypatch.setattr(inbound_tasks, "_resolve_thread_agent", lambda *_args: agent)
    monkeypatch.setattr(inbound_tasks, "_build_thread_history", lambda *_args: [])
    monkeypatch.setattr(inbound_tasks, "_get_llm_router", lambda: object())

    async def _fake_enqueue_segmented_reply(*_args, **_kwargs):
        enqueue_calls.append(True)
        return []

    async def _fake_plan_sales_materials(*_args, **_kwargs):
        return []

    monkeypatch.setattr(inbound_tasks, "_enqueue_segmented_reply", _fake_enqueue_segmented_reply)
    monkeypatch.setattr(inbound_tasks, "_plan_sales_material_sends", _fake_plan_sales_materials)

    class _Runtime:
        def __init__(self, _session, _router):
            pass

        async def run_turn(
            self,
            lead_id,
            workspace_id=None,
            user_message=None,
            agent_id_override=None,
            bypass_safety=False,
            history_override=None,
            task_override=None,
            llm_extra_params=None,
        ):
            captured.update(
                {
                    "lead_id": lead_id,
                    "workspace_id": workspace_id,
                    "user_message": user_message,
                    "agent_id_override": agent_id_override,
                    "bypass_safety": bypass_safety,
                    "history_override": history_override,
                    "task_override": task_override,
                    "llm_extra_params": llm_extra_params,
                }
            )
            return {"status": "sent", "content": "reply"}

    monkeypatch.setattr(inbound_tasks, "ConversationAgentRuntime", _Runtime)
    monkeypatch.setattr(session, "get", lambda _model, _id: lead)

    asyncio.run(inbound_tasks._process_one_inbound(session, message))

    assert message.delivery_status == "inbound_ai_replied"
    assert enqueue_calls == [True]
    assert captured["lead_id"] == 88
    assert captured["workspace_id"] == 77
    assert captured["agent_id_override"] == 44
    assert captured["history_override"] == []
