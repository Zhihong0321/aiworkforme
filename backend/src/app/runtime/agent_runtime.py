"""
MODULE: Application Runtime - Agent Runtime
PURPOSE: Unified conversation runtime orchestration.
"""
import importlib
import logging
import json
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from sqlmodel import Session

from src.domain.entities.enums import LeadStage
from src.app.policy.evaluator import PolicyEvaluator
from src.app.runtime.context_builder import ContextBuilder
from src.app.runtime.memory_service import MemoryService
from src.app.runtime.leads_service import get_or_create_default_workspace
from src.ports.llm import LLMRouterPort

logger = logging.getLogger(__name__)


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

    async def run_turn(
        self,
        lead_id: int,
        workspace_id: Optional[int] = None,
        user_message: Optional[str] = None,
        agent_id_override: Optional[int] = None,
        bypass_safety: bool = False,
        history_override: Optional[List[Dict[str, str]]] = None,
        task_override: Optional[Any] = None,
        llm_extra_params: Optional[Dict[str, Any]] = None,
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
            lead_id, workspace_id, query=user_message, agent_id_override=agent_id_override
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
        response = await self.router.execute(
            task=selected_task,
            messages=messages,
            **execute_kwargs,
        )
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
