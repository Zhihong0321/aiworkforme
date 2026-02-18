from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from models import Lead, Workspace, StrategyVersion, StrategyStatus, BudgetTier, LeadMemory
from runtime.memory_service import MemoryService
from runtime.rag_service import RAGService

class ContextBuilder:
    """
    Real Context Assembler.
    Combines Active Strategy, Knowledge Retrieval (RAG), and Lead Memory.
    """
    def __init__(self, session: Session):
        self.session = session
        self.rag = RAGService(session)
        self.memory = MemoryService(session)

    async def build_context(self, lead_id: int, workspace_id: int, query: Optional[str] = None) -> Dict[str, Any]:
        """
        Assembles the full prompt context for a turn.
        """
        lead = self.session.get(Lead, lead_id)
        workspace = self.session.get(Workspace, workspace_id)
        
        # 1. Fetch Active Strategy
        strategy = self.session.exec(
            select(StrategyVersion)
            .where(StrategyVersion.workspace_id == workspace_id)
            .where(StrategyVersion.status == StrategyStatus.ACTIVE)
        ).first()

        strategy_prompt = self._compile_strategy_prompt(strategy) if strategy else "Role: Professional Assistant."

        # 2. Real Knowledge Retrieval (RAG)
        # We use the query (last user message) to find relevant docs linked to the workspace's agent
        knowledge_context = ""
        if workspace.agent_id and query:
            chunks = await self.rag.retrieve_context(query, workspace.agent_id)
            knowledge_context = self.rag.format_for_prompt(chunks)

        # 3. Fetch Lead Memory
        memory = self.memory.get_lead_memory(lead_id)
        memory_context = ""
        if memory:
            memory_context = f"\n--- LEAD PROFILE ---\nSummary: {memory.summary}\nFacts: {', '.join(memory.facts)}\n"

        # 4. Handle Budget Tiers (Governance)
        if workspace.budget_tier == BudgetTier.RED:
            # RED: No knowledge, no memory, bare strategy
            final_system_instruction = f"Role: Brief Assistant. Objectives: {strategy.objectives if strategy else 'Reply helpful'}. No tools."
            generation_config = {"max_tokens": 512, "temperature": 0.5}
            tools_enabled = False
        else:
            # GREEN/YELLOW: Include memory and knowledge
            final_system_instruction = f"{strategy_prompt}\n{memory_context}\n{knowledge_context}"
            generation_config = {"max_tokens": 2048, "temperature": 0.7}
            tools_enabled = True

        return {
            "system_instruction": final_system_instruction,
            "budget_tier": workspace.budget_tier,
            "generation_config": generation_config,
            "tools_enabled": tools_enabled
        }

    def _compile_strategy_prompt(self, strategy: StrategyVersion) -> str:
        return f"""
TONE: {strategy.tone}
OBJECTIVES: {strategy.objectives}
OBJECTION HANDLING: {strategy.objection_handling}
CTA RULES: {strategy.cta_rules}
"""
