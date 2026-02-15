import logging
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from sqlmodel import Session, select
from models import LeadMemory, ChatMessageNew, ConversationThread
from zai_client import ZaiClient

logger = logging.getLogger(__name__)

class MemoryService:
    """
    Manages lead-specific memory (Summaries and Facts).
    Unified to use ZaiClient.
    """
    def __init__(self, session: Session, zai_client: Optional[ZaiClient] = None):
        self.session = session
        self.client = zai_client

    def get_lead_memory(self, lead_id: int) -> Optional[LeadMemory]:
        return self.session.exec(
            select(LeadMemory).where(LeadMemory.lead_id == lead_id)
        ).first()

    async def refresh_memory(self, lead_id: int, thread_id: int):
        """
        Triggers an LLM turn to summarize the conversation and extract facts.
        """
        if not self.client or not self.client.is_configured:
            logger.warning("ZaiClient not configured in MemoryService; skipping refresh.")
            return

        # Fetch recent messages
        messages = self.session.exec(
            select(ChatMessageNew)
            .where(ChatMessageNew.thread_id == thread_id)
            .order_by(ChatMessageNew.created_at.desc())
            .limit(20)
        ).all()
        messages.reverse()
        
        history_text = "\n".join([f"{m.role}: {m.content}" for m in messages])

        prompt = f"""
Analyze the following WhatsApp conversation history.
1. Provide a concise 2-sentence summary.
2. Extract key facts (e.g., name, location, specific interests, mentioned budget) as a simple list.

History:
{history_text}

JSON Format:
{{
  "summary": "...",
  "facts": ["...", "..."]
}}
"""
        try:
            # Request JSON formatting for extraction
            response_msg = await self.client.chat(
                messages=[{"role": "user", "content": prompt}],
                model="glm-4.7-flash",
                include_reasoning=False,
                response_format={"type": "json_object"}
            )
            
            if not response_msg.content:
                raise ValueError("Memory refresh returned empty content")

            data = json.loads(response_msg.content)
            
            memory = self.get_lead_memory(lead_id)
            if not memory:
                memory = LeadMemory(lead_id=lead_id)
            
            memory.summary = data.get("summary")
            memory.facts = data.get("facts", [])
            memory.last_updated_at = datetime.utcnow()
            
            self.session.add(memory)
            self.session.commit()
            logger.info(f"Memory refreshed for lead {lead_id}")
            
        except Exception as e:
            logger.error(f"Memory refresh failed for lead {lead_id}: {e}")
