import logging
import json
from typing import Dict, Any, List, Optional
from sqlmodel import Session
from models import Lead, Workspace, PolicyDecision, ChatMessageNew, ConversationThread, LeadStage
from policy.evaluator import PolicyEvaluator
from runtime.context_builder import ContextBuilder
from runtime.memory_service import MemoryService
from providers.uniapi import UniAPIClient

logger = logging.getLogger(__name__)

class ConversationAgentRuntime:
    """
    Unified Conversation Runtime.
    Orchestrates the policy-aware, intent-first messaging loop.
    """
    def __init__(self, session: Session, uniapi_client: UniAPIClient):
        self.session = session
        self.client = uniapi_client
        self.policy = PolicyEvaluator(session)
        self.builder = ContextBuilder(session)

    async def run_turn(self, lead_id: int, workspace_id: int, user_message: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes a single workflow turn (either response to inbound or scheduled outbound).
        """
        # 1. PRE-SEND POLICY CHECK
        policy_decision = self.policy.evaluate_outbound(lead_id, workspace_id)
        self.policy.record_decision(policy_decision)
        
        if not policy_decision.allow_send:
            logger.info(f"Send blocked: {policy_decision.reason_code} for lead {lead_id}")
            return {"status": "blocked", "reason": policy_decision.reason_code}

        # 2. BUILD CONTEXT
        context = await self.builder.build_context(lead_id, workspace_id)
        
        # 3. GET OR CREATE THREAD
        thread = self._get_or_create_thread(lead_id, workspace_id)
        
        # 4. PREPARE MESSAGES
        history = self._get_recent_history(thread.id)
        if user_message:
            history.append({"role": "user", "content": user_message})
            self._save_message(thread.id, "user", user_message)

        # 5. EXECUTE LLM CALL
        try:
            response = await self.client.generate_content(
                messages=history,
                system_instruction=context["system_instruction"],
                generation_config=context.get("generation_config")
            )
            model_text = response["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            logger.error(f"LLM failure: {e}")
            return {"status": "error", "message": "Model unreachable"}

        # 6. POST-GENERATION RISK CHECK
        risk_decision = self.policy.validate_risk(lead_id, workspace_id, model_text, confidence_score=0.9)
        self.policy.record_decision(risk_decision)

        if not risk_decision.allow_send:
            logger.warning(f"Response blocked by risk check: {risk_decision.reason_code}")
            return {"status": "blocked", "reason": risk_decision.reason_code}

        # 7. COMMIT MESSAGE & UPDATE LEAD
        self._save_message(thread.id, "model", model_text)
        self._update_lead_after_send(lead_id)

        # 8. ASYNC MEMORY REFRESH
        memory_service = MemoryService(self.session, self.client)
        # In a real app, this would be a background task (e.g., Celery/Redis)
        # For MVP implementation, we do it in-process for now or just trigger it.
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
            thread = ConversationThread(lead_id=lead_id, workspace_id=workspace_id)
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
        msg = ChatMessageNew(thread_id=thread_id, role=role, content=content)
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
