from typing import List, Dict, Any, Optional
from sqlmodel import Session, select
from models import Lead, Workspace, StrategyVersion, StrategyStatus, BudgetTier, LeadMemory
from runtime.memory_service import MemoryService

class ContextBuilder:
    """
    Assembles the prompt context for the Conversation Agent.
    Combines Strategy, Knowledge (RAG), and Memory.
    """
    def __init__(self, session: Session):
        self.session = session

    async def build_context(self, lead_id: int, workspace_id: int) -> Dict[str, Any]:
        lead = self.session.get(Lead, lead_id)
        workspace = self.session.get(Workspace, workspace_id)
        
        # 1. Fetch Active Strategy
        strategy = self.session.exec(
            select(StrategyVersion)
            .where(StrategyVersion.workspace_id == workspace_id)
            .where(StrategyVersion.status == StrategyStatus.ACTIVE)
        ).first()

        if not strategy:
            strategy_prompt = "You are a helpful assistant helping SMBs with WhatsApp outreach."
        else:
            strategy_prompt = self._compile_strategy_prompt(strategy)

        # 2. Fetch Lead Memory
        memory_service = MemoryService(self.session)
        memory = memory_service.get_lead_memory(lead_id)
        memory_context = ""
        if memory:
            memory_context = f"\nLead Summary: {memory.summary}\nKnown Facts: {', '.join(memory.facts)}"

        # 3. Add Knowledge (RAG Placeholder)
        knowledge_context = "Knowledge: Use available documents via tools."

        # 4. Handle Budget Tiers (Context Truncation & Cost Governance)
        if workspace.budget_tier == BudgetTier.RED:
            # RED: Minimal context, no memory, no tools, compact prompt
            final_system_instruction = f"Role: SMB Assistant. Objectives: {strategy.objectives if strategy else 'Reply helpful'}. Keep it very brief. No tools."
            generation_config = {"maxOutputTokens": 512, "temperature": 0.5}
            tools_enabled = False
        elif workspace.budget_tier == BudgetTier.YELLOW:
            # YELLOW: Truncated history, summary only (no facts), limited tools
            final_system_instruction = f"{strategy_prompt}\nSummary: {memory.summary if memory else ''}\n{knowledge_context}"
            generation_config = {"maxOutputTokens": 1024, "temperature": 0.7}
            tools_enabled = True
        else:
            # GREEN: Full context, memory, tools
            final_system_instruction = f"{strategy_prompt}{memory_context}\n{knowledge_context}"
            generation_config = {"maxOutputTokens": 2048, "temperature": 0.7}
            tools_enabled = True

        return {
            "system_instruction": final_system_instruction,
            "budget_tier": workspace.budget_tier,
            "generation_config": generation_config,
            "tools_enabled": tools_enabled
        }

    def _compile_strategy_prompt(self, strategy: StrategyVersion) -> str:
        return f"""
Tone: {strategy.tone}
Objectives: {strategy.objectives}
Objection Handling: {strategy.objection_handling}
CTA Rules: {strategy.cta_rules}
"""
