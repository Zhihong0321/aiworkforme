import logging
from typing import Optional, List, Dict, Any
from sqlmodel import Session, select
from models import LeadMemory, ChatMessageNew, ConversationThread
from providers.uniapi import UniAPIClient

logger = logging.getLogger(__name__)

class MemoryService:
    """
    Manages lead-specific memory (Summaries and Facts).
    """
    def __init__(self, session: Session, uniapi_client: Optional[UniAPIClient] = None):
        self.session = session
        self.client = uniapi_client

    def get_lead_memory(self, lead_id: int) -> Optional[LeadMemory]:
        return self.session.exec(
            select(LeadMemory).where(LeadMemory.lead_id == lead_id)
        ).first()

    async def refresh_memory(self, lead_id: int, thread_id: int):
        """
        Triggers an LLM turn to summarize the conversation and extract facts.
        """
        if not self.client:
            logger.warning("No UniAPIClient provided to MemoryService; skipping refresh.")
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
            # We use a compact generation config for background tasks
            response = await self.client.generate_content(
                messages=[{"role": "user", "content": prompt}],
                system_instruction="You are a data extraction assistant. Output valid JSON only.",
                generation_config={"responseMimeType": "application/json"}
            )
            
            data = json.loads(response["candidates"][0]["content"]["parts"][0]["text"])
            
            memory = self.get_lead_memory(lead_id)
            if not memory:
                memory = LeadMemory(lead_id=lead_id)
            
            memory.summary = data.get("summary")
            memory.facts = data.get("facts", [])
            memory.last_updated_at = datetime.utcnow()
            
            self.session.add(memory)
            self.session.commit()
            
        except Exception as e:
            logger.error(f"Memory refresh failed for lead {lead_id}: {e}")

import json
from datetime import datetime
