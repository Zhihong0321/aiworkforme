import logging
import json
from typing import List, Dict, Any, Optional
from sqlmodel import Session, select, or_
from models import AgentKnowledgeFile, AgentMCPServer

logger = logging.getLogger(__name__)

class RAGService:
    """
    Real Knowledge Retrieval Service.
    Performs keyword-based search across agent knowledge files for the MVP.
    """
    def __init__(self, session: Session):
        self.session = session

    async def retrieve_context(self, query: str, agent_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieves relevant knowledge chunks from the database based on the query.
        """
        if not agent_id or not query:
            return []

        # Simple keyword search for MVP
        # In a full V1, this would be PGVector / OpenAI Embeddings
        words = query.lower().split()
        if not words:
            return []

        # Find files for this agent
        statement = select(AgentKnowledgeFile).where(AgentKnowledgeFile.agent_id == agent_id)
        files = self.session.exec(statement).all()
        
        results = []
        for file in files:
            content_lower = file.content.lower()
            score = 0
            # Calculate simple relevance score
            for word in words:
                if word in content_lower:
                    score += 1
            
            if score > 0:
                results.append({
                    "content": file.content[:1000],  # Clip for prompt buffer
                    "source": file.filename,
                    "relevance": score / len(words),
                    "id": file.id
                })

        # Sort by relevance
        results.sort(key=lambda x: x["relevance"], reverse=True)
        
        return results[:3] # Return top 3

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
