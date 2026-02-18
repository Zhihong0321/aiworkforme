"""
MODULE: Application Runtime - Agent Runtime
PURPOSE: Unified conversation runtime orchestration.
"""
import logging
import json
from typing import Dict, Any, List, Optional
from sqlmodel import Session

from src.adapters.db.crm_models import Lead, Workspace, PolicyDecision, ChatMessageNew, ConversationThread
from src.domain.entities.enums import LeadStage
from src.app.policy.evaluator import PolicyEvaluator
from src.app.runtime.context_builder import ContextBuilder
from src.app.runtime.memory_service import MemoryService
from src.infra.llm.router import LLMRouter
from src.infra.llm.schemas import LLMTask

logger = logging.getLogger(__name__)

class ConversationAgentRuntime:
    """
    Unified Conversation Runtime.
    Orchestrates the policy-aware, intent-first messaging loop.
    """
    def __init__(self, session: Session, llm_router: LLMRouter):
        self.session = session
        self.router = llm_router
        self.policy = PolicyEvaluator(session)
        self.builder = ContextBuilder(session)

    async def run_turn(
        self,
        lead_id: int,
        workspace_id: int,
        user_message: Optional[str] = None,
        agent_id_override: Optional[int] = None,
        bypass_safety: bool = False,
        history_override: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """
        Executes a single workflow turn.

        history_override: when provided (e.g. from the inbound worker which reads
        from et_messages), skip fetching from ChatMessageNew and use this history
        directly. Format: [{"role": "user"|"assistant", "content": "..."}]
        """
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
        response = await self.router.execute(
            task=LLMTask.CONVERSATION,
            messages=messages,
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

        return {"status": "sent", "content": model_text}

    def _get_or_create_thread(self, lead_id: int, workspace_id: int) -> ConversationThread:
        from sqlmodel import select
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
        lead = self.session.get(Lead, lead_id)
        if lead:
            lead.last_followup_at = datetime.utcnow()
            lead.stage = LeadStage.CONTACTED if lead.stage == LeadStage.NEW else lead.stage
            self.session.add(lead)
            self.session.commit()
