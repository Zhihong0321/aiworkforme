"""
MODULE: Application Runtime - Agent Runtime
PURPOSE: Unified conversation runtime orchestration.
"""
import importlib
import logging
import json
import re
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlmodel import Session

from src.domain.entities.enums import LeadStage
from src.app.policy.evaluator import PolicyEvaluator
from src.app.runtime.agent_tooling import (
    extract_voice_note_action,
    load_agent_tools_for_runtime,
    tool_result_to_text,
)
from src.app.runtime.calendar_debug import record_calendar_debug
from src.app.runtime.context_builder import ContextBuilder
from src.app.runtime.memory_service import MemoryService
from src.app.runtime.leads_service import get_or_create_default_workspace
from src.ports.llm import LLMRouterPort

logger = logging.getLogger(__name__)

CALENDAR_TOOL_NAMES = {"book_appointment", "get_user_availability", "create_pending_appointment"}
SCHEDULING_KEYWORDS = (
    "appoint",
    "appointment",
    "availability",
    "available",
    "book",
    "booking",
    "calendar",
    "meeting",
    "reschedule",
    "schedule",
    "slot",
    "time slot",
)
SCHEDULING_TIME_PATTERN = re.compile(
    r"\b(?:\d{1,2}(?::\d{2})?\s?(?:am|pm)|tomorrow|today|next week|next monday|next tuesday|next wednesday|next thursday|next friday|next saturday|next sunday|\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
CALENDAR_TOOL_RULES = (
    "CALENDAR TOOL RULES:\n"
    "- For calendar, scheduling, availability, booking, rescheduling, or appointment requests, you must call the relevant calendar tool before answering.\n"
    "- Never say an appointment is booked, scheduled, or confirmed unless the tool result explicitly succeeded.\n"
    "- If the lead wants to meet but time or region is not finalized, create a pending appointment for follow-up.\n"
    "- The system injects internal tenant_id and agent_id automatically. Do not invent them."
)


def _normalize_usage(usage: Dict[str, Any]) -> Dict[str, Any]:
    usage = usage or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
    completion_tokens = int(usage.get("completion_tokens", 0) or 0)
    total_tokens = int(usage.get("total_tokens", 0) or 0)
    if total_tokens <= 0:
        total_tokens = prompt_tokens + completion_tokens
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
        "raw_usage": usage.get("raw_usage", usage),
    }


def _is_calendar_tool(tool_name: str) -> bool:
    return str(tool_name or "").strip() in CALENDAR_TOOL_NAMES


def _is_scheduling_request(message: Optional[str]) -> bool:
    text = str(message or "").strip().lower()
    if not text:
        return False
    if any(keyword in text for keyword in SCHEDULING_KEYWORDS):
        return True
    return bool(SCHEDULING_TIME_PATTERN.search(text))


def _inject_runtime_tool_args(
    tool_name: str,
    parsed_args: Dict[str, Any],
    *,
    tenant_id: Optional[int],
    agent_id: Optional[int],
) -> Dict[str, Any]:
    resolved_args = dict(parsed_args or {})
    if _is_calendar_tool(tool_name):
        if tenant_id is not None:
            resolved_args["tenant_id"] = int(tenant_id)
        if agent_id is not None:
            resolved_args["agent_id"] = int(agent_id)
    return resolved_args


class ConversationAgentRuntime:
    """
    Unified Conversation Runtime.
    Orchestrates the policy-aware, intent-first messaging loop.
    """
    def __init__(self, session: Session, llm_router: LLMRouterPort):
        self.session = session
        self.router = llm_router
        self.policy = PolicyEvaluator(session)
        self.builder = ContextBuilder(session)

    @staticmethod
    def _crm_models():
        models = importlib.import_module("src.adapters.db.crm_models")
        return (
            models.Lead,
            models.Workspace,
            models.PolicyDecision,
            models.ChatMessageNew,
            models.ConversationThread,
        )

    @staticmethod
    def _agent_model():
        return importlib.import_module("src.adapters.db.agent_models").Agent

    @staticmethod
    def _llm_task():
        return importlib.import_module("src.infra.llm.schemas").LLMTask

    @staticmethod
    def _estimate_llm_cost():
        return importlib.import_module("src.infra.llm.costs").estimate_llm_cost_usd

    @staticmethod
    def _get_bool_system_setting():
        return importlib.import_module("src.adapters.db.system_settings").get_bool_system_setting

    async def _run_with_optional_tools(
        self,
        *,
        llm_task: Any,
        selected_task: Any,
        messages: List[Dict[str, Any]],
        execute_kwargs: Dict[str, Any],
        agent_id: Optional[int],
        tenant_id: Optional[int],
        tools_enabled: bool,
        user_message: Optional[str],
        debug_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        tools: List[Dict[str, Any]] = []
        tool_meta: Dict[str, Dict[str, Any]] = {}
        debug_context = dict(debug_context or {})
        selected_task_value = getattr(selected_task, "value", str(selected_task))
        conversation_task_value = getattr(llm_task.CONVERSATION, "value", "conversation")
        if tools_enabled and agent_id and selected_task_value == conversation_task_value:
            tools, tool_meta = await load_agent_tools_for_runtime(self.session, int(agent_id))

        effective_messages = list(messages)
        if tools and any(_is_calendar_tool(name) for name in tool_meta):
            effective_messages = list(messages)
            effective_messages.append({"role": "system", "content": CALENDAR_TOOL_RULES})

        scheduling_request = _is_scheduling_request(user_message)
        has_calendar_tools = any(_is_calendar_tool(name) for name in tool_meta)
        if scheduling_request or has_calendar_tools:
            record_calendar_debug(
                self.session,
                tenant_id=tenant_id,
                agent_id=agent_id,
                lead_id=debug_context.get("lead_id"),
                thread_id=debug_context.get("thread_id"),
                inbound_message_id=debug_context.get("inbound_message_id"),
                stage="runtime_calendar_context",
                status="info",
                message="Calendar runtime context evaluated.",
                details={
                    "tools_enabled": bool(tools_enabled),
                    "has_any_tools": bool(tools),
                    "has_calendar_tools": has_calendar_tools,
                    "calendar_tool_names": sorted([name for name in tool_meta if _is_calendar_tool(name)]),
                    "scheduling_request": scheduling_request,
                    "user_message_preview": str(user_message or "")[:240],
                },
            )

        if not tools:
            if scheduling_request:
                record_calendar_debug(
                    self.session,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    lead_id=debug_context.get("lead_id"),
                    thread_id=debug_context.get("thread_id"),
                    inbound_message_id=debug_context.get("inbound_message_id"),
                    stage="runtime_calendar_tools_missing",
                    status="warn",
                    message="Scheduling request detected but no tools were loaded.",
                    details={"selected_task": selected_task_value},
                )
            response = await self.router.execute(
                task=selected_task,
                messages=effective_messages,
                **execute_kwargs,
            )
            return {"response": response, "voice_note_action": None, "tool_events": []}

        tool_events: List[Dict[str, Any]] = []
        tool_mode_task = llm_task.TOOL_USE
        loop_messages: List[Dict[str, Any]] = list(effective_messages)
        require_calendar_tool_first = (
            bool(tools)
            and any(_is_calendar_tool(name) for name in tool_meta)
            and scheduling_request
        )
        if require_calendar_tool_first:
            record_calendar_debug(
                self.session,
                tenant_id=tenant_id,
                agent_id=agent_id,
                lead_id=debug_context.get("lead_id"),
                thread_id=debug_context.get("thread_id"),
                inbound_message_id=debug_context.get("inbound_message_id"),
                stage="runtime_calendar_tool_required",
                status="info",
                message="Calendar tool use is required for this turn.",
                details={"turn_limit": 5},
            )

        for turn_idx in range(5):
            loop_execute_kwargs = dict(execute_kwargs)
            if require_calendar_tool_first and turn_idx == 0:
                loop_execute_kwargs["tool_choice"] = "required"
            response = await self.router.execute(
                task=tool_mode_task,
                messages=loop_messages,
                tools=tools,
                **loop_execute_kwargs,
            )
            tool_calls = list(response.tool_calls or [])
            if not tool_calls:
                if require_calendar_tool_first:
                    record_calendar_debug(
                        self.session,
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        lead_id=debug_context.get("lead_id"),
                        thread_id=debug_context.get("thread_id"),
                        inbound_message_id=debug_context.get("inbound_message_id"),
                        stage="runtime_calendar_tool_not_called",
                        status="warn",
                        message="Model returned no tool calls on a scheduling turn.",
                        details={"turn_index": turn_idx, "response_preview": str(response.content or "")[:240]},
                    )
                return {"response": response, "voice_note_action": None, "tool_events": tool_events}

            loop_messages.append(
                {
                    "role": "assistant",
                    "content": response.content,
                    "tool_calls": tool_calls,
                }
            )

            for tool_call in tool_calls:
                function_data = tool_call.get("function") if isinstance(tool_call, dict) else {}
                tool_name = str((function_data or {}).get("name") or "").strip()
                tool_args_str = str((function_data or {}).get("arguments") or "{}")
                meta = tool_meta.get(tool_name) or {}
                tool_result_text = "Tool not found"
                parsed_args: Dict[str, Any] = {}

                try:
                    parsed_args = json.loads(tool_args_str) if tool_args_str else {}
                    if not isinstance(parsed_args, dict):
                        parsed_args = {}
                except Exception:
                    parsed_args = {}
                parsed_args = _inject_runtime_tool_args(
                    tool_name,
                    parsed_args,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                )
                if _is_calendar_tool(tool_name):
                    record_calendar_debug(
                        self.session,
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        lead_id=debug_context.get("lead_id"),
                        thread_id=debug_context.get("thread_id"),
                        inbound_message_id=debug_context.get("inbound_message_id"),
                        stage="runtime_calendar_tool_called",
                        status="info",
                        message=f"Calling calendar tool: {tool_name}",
                        details={"arguments": parsed_args, "turn_index": turn_idx},
                    )

                if meta.get("server_id"):
                    manager = importlib.import_module("src.adapters.api.dependencies").get_mcp_manager()
                    try:
                        tool_result = await manager.call_mcp_tool(
                            str(meta["server_id"]),
                            tool_name,
                            parsed_args,
                        )
                        tool_result_text = tool_result_to_text(tool_result)
                    except Exception as exc:
                        tool_result_text = f"Error executing tool: {exc}"

                tool_events.append(
                    {
                        "tool_name": tool_name,
                        "arguments": parsed_args,
                        "result": tool_result_text,
                    }
                )
                if _is_calendar_tool(tool_name):
                    record_calendar_debug(
                        self.session,
                        tenant_id=tenant_id,
                        agent_id=agent_id,
                        lead_id=debug_context.get("lead_id"),
                        thread_id=debug_context.get("thread_id"),
                        inbound_message_id=debug_context.get("inbound_message_id"),
                        stage="runtime_calendar_tool_result",
                        status="ok" if not str(tool_result_text).lower().startswith("error") else "error",
                        message=f"Calendar tool returned: {tool_name}",
                        details={"result": tool_result_text[:1000]},
                    )

                voice_note_action = extract_voice_note_action(tool_name, tool_result_text, meta)
                if voice_note_action:
                    return {
                        "response": response,
                        "voice_note_action": voice_note_action,
                        "tool_events": tool_events,
                    }

                loop_messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": str(tool_call.get("id") or ""),
                        "content": tool_result_text,
                    }
                )

        return {"response": None, "voice_note_action": None, "tool_events": tool_events}

    async def run_turn(
        self,
        lead_id: int,
        workspace_id: Optional[int] = None,
        user_message: Optional[str] = None,
        agent_id_override: Optional[int] = None,
        thread_id_override: Optional[int] = None,
        bypass_safety: bool = False,
        history_override: Optional[List[Dict[str, str]]] = None,
        task_override: Optional[Any] = None,
        llm_extra_params: Optional[Dict[str, Any]] = None,
        debug_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a single workflow turn.

        history_override: when provided (e.g. from the inbound worker which reads
        from et_messages), skip fetching from ChatMessageNew and use this history
        directly. Format: [{"role": "user"|"assistant", "content": "..."}]
        """
        # Resolve workspace lazily when callers do not provide one.
        Lead, _, _, _, _ = self._crm_models()
        lead = self.session.get(Lead, lead_id)
        if not lead:
            return {"status": "blocked", "reason": "LEAD_NOT_FOUND"}
        if workspace_id is None:
            workspace_id = lead.workspace_id
        if workspace_id is None:
            if lead.tenant_id is None:
                return {"status": "blocked", "reason": "LEAD_TENANT_NOT_FOUND"}
            workspace = get_or_create_default_workspace(self.session, int(lead.tenant_id))
            lead.workspace_id = workspace.id
            self.session.add(lead)
            self.session.commit()
            workspace_id = workspace.id

        # 1. PRE-SEND POLICY CHECK
        policy_decision = self.policy.evaluate_outbound(lead_id, workspace_id, bypass_safety=bypass_safety)
        self.policy.record_decision(policy_decision)

        if not policy_decision.allow_send:
            logger.info(f"Send blocked: {policy_decision.reason_code} for lead {lead_id}")
            return {"status": "blocked", "reason": policy_decision.reason_code}

        # 2. BUILD CONTEXT (agent system_prompt + RAG knowledge + lead memory)
        context = await self.builder.build_context(
            lead_id,
            workspace_id,
            query=user_message,
            agent_id_override=agent_id_override,
            thread_id=thread_id_override,
        )

        # 3. PREPARE MESSAGES
        # Use caller-supplied history when available (inbound worker uses et_messages);
        # otherwise fall back to ChatMessageNew (playground / legacy path).
        if history_override is not None:
            history = history_override
        else:
            thread = self._get_or_create_thread(lead_id, workspace_id)
            history = self._get_recent_history(thread.id)

        messages = [{"role": "system", "content": context["system_instruction"]}]
        messages.extend(history)

        if user_message:
            messages.append({"role": "user", "content": user_message})
            # Only persist to ChatMessageNew on the legacy (playground) path
            if history_override is None:
                thread = self._get_or_create_thread(lead_id, workspace_id)
                self._save_message(thread.id, "user", user_message)

        # 4. EXECUTE LLM CALL — let exceptions propagate so callers see real errors
        llm_task = self._llm_task()
        selected_task = llm_task.CONVERSATION
        if task_override is not None:
            selected_task = (
                llm_task(task_override)
                if isinstance(task_override, str)
                else task_override
            )
        execute_kwargs: Dict[str, Any] = {}
        if llm_extra_params:
            execute_kwargs.update(llm_extra_params)
        tool_run = await self._run_with_optional_tools(
            llm_task=llm_task,
            selected_task=selected_task,
            messages=messages,
            execute_kwargs=execute_kwargs,
            agent_id=context.get("agent_id"),
            tenant_id=lead.tenant_id,
            tools_enabled=bool(context.get("tools_enabled")),
            user_message=user_message,
            debug_context={
                "lead_id": lead_id,
                "thread_id": thread_id_override,
                **(debug_context or {}),
            },
        )
        response = tool_run.get("response")
        if tool_run.get("voice_note_action"):
            response = response or type("Response", (), {"provider_info": {}, "usage": {}, "content": None})()
            provider_info = response.provider_info or {}
            usage = _normalize_usage(response.usage or {})
            provider_name = provider_info.get("provider") or "unknown"
            model_name = provider_info.get("model") or "unknown"
            estimated_cost_usd = self._estimate_llm_cost()(
                provider_name,
                model_name,
                usage["prompt_tokens"],
                usage["completion_tokens"],
            )
            include_context_prompt = self._get_bool_system_setting()(
                self.session, "record_context_prompt", default=False
            )
            ai_trace = {
                "schema_version": "1.0",
                "task": selected_task.value,
                "provider": provider_name,
                "model": model_name,
                "usage": {**usage, "estimated_cost_usd": estimated_cost_usd},
                "context_prompt": context["system_instruction"] if include_context_prompt else None,
                "recorded_at": datetime.now(timezone.utc).isoformat(),
                "tool_events": tool_run.get("tool_events") or [],
            }
            if context.get("conversation_skills"):
                ai_trace["conversation_skills"] = context["conversation_skills"]
            voice_note_action = dict(tool_run["voice_note_action"])
            return {
                "status": "sent",
                "content": voice_note_action.get("text_content") or "",
                "message_type": "audio",
                "raw_payload": voice_note_action,
                "ai_trace": ai_trace,
                "llm_provider": provider_name,
                "llm_model": model_name,
                "llm_prompt_tokens": usage["prompt_tokens"],
                "llm_completion_tokens": usage["completion_tokens"],
                "llm_total_tokens": usage["total_tokens"],
                "llm_estimated_cost_usd": estimated_cost_usd,
            }

        if response is None:
            raise ValueError("LLM returned no response")
        model_text = response.content
        if not model_text:
            raise ValueError("LLM returned empty content")

        # 5. POST-GENERATION RISK CHECK
        risk_decision = self.policy.validate_risk(lead_id, workspace_id, model_text, confidence_score=0.9)
        self.policy.record_decision(risk_decision)

        if not risk_decision.allow_send:
            logger.warning(f"Response blocked by risk check: {risk_decision.reason_code}")
            return {"status": "blocked", "reason": risk_decision.reason_code}

        # 6. COMMIT MESSAGE & UPDATE LEAD (legacy path only)
        if history_override is None:
            thread = self._get_or_create_thread(lead_id, workspace_id)
            self._save_message(thread.id, "model", model_text)
            self._update_lead_after_send(lead_id)

            # 7. ASYNC MEMORY REFRESH
            memory_service = MemoryService(self.session, self.router)
            await memory_service.refresh_memory(lead_id, thread.id)

        provider_info = response.provider_info or {}
        usage = _normalize_usage(response.usage or {})
        provider_name = provider_info.get("provider") or "unknown"
        model_name = provider_info.get("model") or "unknown"
        estimated_cost_usd = self._estimate_llm_cost()(
            provider_name,
            model_name,
            usage["prompt_tokens"],
            usage["completion_tokens"],
        )
        include_context_prompt = self._get_bool_system_setting()(
            self.session, "record_context_prompt", default=False
        )
        ai_trace = {
            "schema_version": "1.0",
            "task": selected_task.value,
            "provider": provider_name,
            "model": model_name,
            "usage": {**usage, "estimated_cost_usd": estimated_cost_usd},
            "context_prompt": context["system_instruction"] if include_context_prompt else None,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }
        if tool_run.get("tool_events"):
            ai_trace["tool_events"] = tool_run["tool_events"]
        if context.get("conversation_skills"):
            ai_trace["conversation_skills"] = context["conversation_skills"]
        result: Dict[str, Any] = {
            "status": "sent",
            "content": model_text,
            "ai_trace": ai_trace,
            "llm_provider": provider_name,
            "llm_model": model_name,
            "llm_prompt_tokens": usage["prompt_tokens"],
            "llm_completion_tokens": usage["completion_tokens"],
            "llm_total_tokens": usage["total_tokens"],
            "llm_estimated_cost_usd": estimated_cost_usd,
        }
        return result

    def _get_or_create_thread(self, lead_id: int, workspace_id: int) -> Any:
        from sqlmodel import select
        Lead, _, _, _, ConversationThread = self._crm_models()
        thread = self.session.exec(
            select(ConversationThread)
            .where(ConversationThread.lead_id == lead_id)
            .where(ConversationThread.status == "active")
        ).first()
        
        if not thread:
            lead = self.session.get(Lead, lead_id)
            thread = ConversationThread(
                lead_id=lead_id, 
                workspace_id=workspace_id,
                tenant_id=lead.tenant_id if lead else None
            )
            self.session.add(thread)
            self.session.commit()
            self.session.refresh(thread)
        return thread

    def _get_recent_history(self, thread_id: int) -> List[Dict[str, str]]:
        from sqlmodel import select
        _, _, _, ChatMessageNew, _ = self._crm_models()
        msgs = self.session.exec(
            select(ChatMessageNew)
            .where(ChatMessageNew.thread_id == thread_id)
            .order_by(ChatMessageNew.created_at.desc())
            .limit(10)
        ).all()
        msgs.reverse()
        return [{"role": m.role, "content": m.content} for m in msgs]

    def _save_message(self, thread_id: int, role: str, content: str):
        # We need the tenant_id for the message as well. 
        # Better to fetch it from the thread which we already have.
        _, _, _, ChatMessageNew, ConversationThread = self._crm_models()
        thread = self.session.get(ConversationThread, thread_id)
        msg = ChatMessageNew(
            thread_id=thread_id, 
            role=role, 
            content=content,
            tenant_id=thread.tenant_id if thread else None
        )
        self.session.add(msg)
        self.session.commit()

    def _update_lead_after_send(self, lead_id: int):
        from datetime import datetime
        Lead, _, _, _, _ = self._crm_models()
        lead = self.session.get(Lead, lead_id)
        if lead:
            lead.last_followup_at = datetime.now(timezone.utc)
            lead.stage = LeadStage.CONTACTED if lead.stage == LeadStage.NEW else lead.stage
            self.session.add(lead)
            self.session.commit()
