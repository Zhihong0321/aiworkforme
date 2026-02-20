"""
MODULE: Application Runtime - Memory Service
PURPOSE: Management of lead-specific memory (summaries/facts).
"""
import logging
import json
import importlib
from typing import Optional, Any
from datetime import datetime
from sqlmodel import Session, select

from src.ports.llm import LLMRouterPort

logger = logging.getLogger(__name__)

class MemoryService:
    """
    Manages lead-specific memory (Summaries and Facts).
    """
    def __init__(self, session: Session, llm_router: Optional[LLMRouterPort] = None):
        self.session = session
        self.router = llm_router

    @staticmethod
    def _crm_models():
        models = importlib.import_module("src.adapters.db.crm_models")
        return models.LeadMemory, models.ChatMessageNew

    def get_lead_memory(self, lead_id: int) -> Optional[Any]:
        lead_memory_model, _ = self._crm_models()
        return self.session.exec(
            select(lead_memory_model).where(lead_memory_model.lead_id == lead_id)
        ).first()

    async def refresh_memory(self, lead_id: int, thread_id: int):
        """
        Triggers an LLM turn to summarize the conversation and extract facts.
        """
        if not self.router:
            logger.warning("LLMRouter not provided to MemoryService; skipping refresh.")
            return

        # Fetch recent messages
        _, chat_message_model = self._crm_models()
        messages = self.session.exec(
            select(chat_message_model)
            .where(chat_message_model.thread_id == thread_id)
            .order_by(chat_message_model.created_at.desc())
            .limit(20)
        ).all()
        messages.reverse()
        
        history_text = "\n".join([f"{m.role}: {m.content}" for m in messages])

        prompt = f"""
Analyze the following WhatsApp conversation history.
1. Provide a concise 2-sentence summary.
2. Extract key facts (name, location, budget, etc.) as a simple list.

History:
{history_text}

JSON Format:
{{
  "summary": "...",
  "facts": ["...", "..."]
}}
"""
        try:
            llm_task = importlib.import_module("src.infra.llm.schemas").LLMTask
            response = await self.router.execute(
                task=llm_task.EXTRACTION,
                messages=[{"role": "user", "content": prompt}],
                response_format={"type": "json_object"}
            )
            
            if not response.content:
                raise ValueError("Memory refresh returned empty content")

            data = json.loads(response.content)
            
            memory = self.get_lead_memory(lead_id)
            if not memory:
                lead_memory_model, _ = self._crm_models()
                memory = lead_memory_model(lead_id=lead_id)
            
            memory.summary = data.get("summary")
            memory.facts = data.get("facts", [])
            memory.last_updated_at = datetime.utcnow()
            
            self.session.add(memory)
            self.session.commit()
            logger.info(f"Memory refreshed for lead {lead_id}")
            
        except Exception as e:
            logger.error(f"Memory refresh failed for lead {lead_id}: {e}")
            self.session.rollback()
