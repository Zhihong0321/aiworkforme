"""
MODULE: Application Runtime - RAG Service
PURPOSE: Knowledge retrieval service for agents.
"""
import logging
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select

from src.adapters.db.agent_models import AgentKnowledgeFile

logger = logging.getLogger(__name__)

class RAGService:
    """
    Real Knowledge Retrieval Service.
    Performs keyword-based search across agent knowledge files.
    """
    def __init__(self, session: Session):
        self.session = session

    async def retrieve_context(self, query: str, agent_id: Optional[int] = None, tenant_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves relevant knowledge chunks from the database, strictly scoped by tenant.
        """
        if not agent_id or not query or not tenant_id:
            logger.warning(f"RAG retrieval skipped: Missing required scoping (Agent:{agent_id}, Query:{bool(query)}, Tenant:{tenant_id})")
            return []

        # Simple keyword search for MVP
        words = query.lower().split()
        if not words:
            return []

        # Find files for this agent AND this tenant
        statement = select(AgentKnowledgeFile).where(
            AgentKnowledgeFile.agent_id == agent_id,
            AgentKnowledgeFile.tenant_id == tenant_id
        )
        files = self.session.exec(statement).all()
        
        results = []
        for file in files:
            content_lower = file.content.lower()
            score = 0
            for word in words:
                if word in content_lower:
                    score += 1
            
            if score > 0:
                results.append({
                    "content": file.content[:1000], 
                    "source": file.filename,
                    "relevance": score / len(words),
                    "id": file.id
                })

        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results[:3] 


    def format_for_prompt(self, chunks: List[Dict[str, Any]], token_budget: int = 1500) -> str:
        """
        Packs chunks into a string for the LLM prompt.
        """
        if not chunks:
            return ""

        formatted = "\n--- RELEVANT KNOWLEDGE ---\n"
        for chunk in chunks:
            formatted += f"Source: {chunk['source']}\n{chunk['content']}\n---\n"
        
        return formatted
