"""
MODULE: Application Runtime - Context Builder
PURPOSE: Assembler for lead context, strategy, and RAG data.
"""
import importlib
from typing import Dict, Any, Optional
from sqlmodel import Session, select

from src.domain.entities.enums import StrategyStatus, BudgetTier
from src.app.runtime.leads_service import get_or_create_default_workspace
from src.app.runtime.memory_service import MemoryService
from src.app.runtime.rag_service import RAGService

class ContextBuilder:
    """
    Real Context Assembler.
    Combines Active Strategy, Knowledge Retrieval (RAG), and Lead Memory.
    """
    def __init__(self, session: Session):
        self.session = session
        self.rag = RAGService(session)
        self.memory = MemoryService(session)

    @staticmethod
    def _crm_models():
        models = importlib.import_module("src.adapters.db.crm_models")
        return models.Lead, models.Workspace, models.StrategyVersion

    async def build_context(
        self,
        lead_id: int,
        workspace_id: Optional[int],
        query: Optional[str] = None,
        agent_id_override: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Assembles the full prompt context for a turn.
        """
        Lead, Workspace, StrategyVersion = self._crm_models()
        lead = self.session.get(Lead, lead_id)
        resolved_workspace_id = workspace_id or (lead.workspace_id if lead else None)
        workspace = self.session.get(Workspace, resolved_workspace_id) if resolved_workspace_id is not None else None
        if workspace is None and lead and lead.tenant_id is not None:
            workspace = get_or_create_default_workspace(self.session, int(lead.tenant_id))
            if lead.workspace_id is None:
                lead.workspace_id = workspace.id
                self.session.add(lead)
                self.session.commit()
            resolved_workspace_id = workspace.id
        
        # Determine agent id to use
        agent_id = agent_id_override or (workspace.agent_id if workspace else None)
        
        # 1. Fetch Active Strategy
        strategy = self.session.exec(
            select(StrategyVersion)
            .where(StrategyVersion.workspace_id == resolved_workspace_id)
            .where(StrategyVersion.status == StrategyStatus.ACTIVE)
        ).first()

        strategy_prompt = self._compile_strategy_prompt(strategy) if strategy else "Role: Professional Assistant."

        # 1.5 Fetch global context & goal from AgentKnowledgeFile
        global_context_prompt = ""
        agent_goal_prompt = ""
        agent_system_prompt = ""
        
        if agent_id:
            Agent = importlib.import_module("src.adapters.db.agent_models").Agent
            agent = self.session.get(Agent, agent_id)
            if agent and agent.system_prompt:
                agent_system_prompt = agent.system_prompt
                
            AgentKnowledgeFile = importlib.import_module("src.adapters.db.agent_models").AgentKnowledgeFile
            statement = select(AgentKnowledgeFile).where(AgentKnowledgeFile.agent_id == agent_id)
            all_files = self.session.exec(statement).all()
            for f in all_files:
                tags = f.tags or "[]"
                if '"fundamental_context"' in tags:
                    global_context_prompt += f"{f.content}\n"
                if '"agent_goal"' in tags:
                    agent_goal_prompt += f"{f.content}\n"

        # 2. Real Knowledge Retrieval (RAG)
        knowledge_context = ""
        if agent_id and query:
            chunks = await self.rag.retrieve_context(query, agent_id, tenant_id=workspace.tenant_id if workspace else None)
            knowledge_context = self.rag.format_for_prompt(chunks)

        # 3. Fetch Lead Memory
        memory = self.memory.get_lead_memory(lead_id)
        memory_context = ""
        if memory:
            memory_context = f"\n--- LEAD PROFILE ---\nSummary: {memory.summary}\nFacts: {', '.join(memory.facts)}\n"

        # 4. Handle Budget Tiers (Governance)
        if workspace and workspace.budget_tier == BudgetTier.RED:
            final_system_instruction = f"Role: Brief Assistant. Objectives: {strategy.objectives if strategy else 'Reply helpful'}. No tools."
            generation_config = {"max_tokens": 512, "temperature": 0.5}
            tools_enabled = False
        else:
            final_system_instruction = (
                f"{strategy_prompt}\n"
                f"{'--- AGENT SYSTEM PROMPT ---\n' + agent_system_prompt + '\n' if agent_system_prompt else ''}"
                f"{'--- FUNDAMENTAL CONTEXT ---\n' + global_context_prompt + '\n' if global_context_prompt else ''}"
                f"{'--- AGENT GOAL ---\n' + agent_goal_prompt + '\n' if agent_goal_prompt else ''}"
                f"{memory_context}\n"
                f"{knowledge_context}"
            )
            generation_config = {"max_tokens": 2048, "temperature": 0.7}
            tools_enabled = True

        # --- SYSTEM BEHAVIOUR INJECTIONS (always appended) ---

        # 1. SEGMENTED MESSAGES — applies to ALL agents globally
        final_system_instruction += (
            "\n\n--- MESSAGE SEGMENTATION RULES ---\n"
            "When your response is long or contains distinct meaningful ideas, "
            "chunk it into separate logical parts using the delimiter ||| between each segment.\n"
            "Example of a segmented reply:\n"
            "  Hey! Got your question 😊|||Let me check that for you real quick...|||"
            "  Okay so here's what I found:\n\n1. Point A\n2. Point B\n\n"
            "Rules:\n"
            "- Each segment will be delivered as a separate WhatsApp message in turn.\n"
            "- Chunk long messages into meaningful, digestible parts (e.g., greeting -> context -> main answer).\n"
            "- MAXIMUM 3 SEGMENTS PER REPLY. Never split into more than 3 parts.\n"
            "- Animated / sticker-style emoji are ONLY permitted inside segmented messages.\n"
            "- Do NOT use ||| if a single short message is sufficient.\n"
        )

        # 2. MIMIC HUMAN TYPING — injected only when flag is set on agent
        agent_obj = None
        if agent_id:
            Agent = importlib.import_module("src.adapters.db.agent_models").Agent
            agent_obj = self.session.get(Agent, agent_id)

        if agent_obj and getattr(agent_obj, "mimic_human_typing", False):
            final_system_instruction += (
                "\n\n--- HUMAN TYPING STYLE (WhatsApp) ---\n"
                "You MUST write exactly like a real human typing on WhatsApp. Strict rules:\n"
                "- Keep replies SHORT. 1–3 sentences max per segment.\n"
                "- Use casual short-forms: 'u', 'r', 'lah', 'la', 'k', 'ok', 'ya', 'yep', 'nope', 'tbh', 'btw', 'omg', 'nvm'.\n"
                "- NO formal punctuation. Avoid full stops at end of sentence. Use lowercase mostly.\n"
                "- Occasionally leave out articles (a, the) like humans do when typing fast.\n"
                "- Sound warm and friendly, NOT robotic or corporate.\n"
                "- Never write long formal paragraphs. Break long answers into segments with |||.\n"
                "- Mirror the user's energy: if they're casual, be casual. If they're urgent, be quick.\n"
            )

        # 3. EMOJI FREQUENCY (Google NOTO style) — injected based on emoji_level
        emoji_level = getattr(agent_obj, "emoji_level", "none") if agent_obj else "none"
        if emoji_level == "low":
            final_system_instruction += (
                "\n\n--- EMOJI USAGE (Low Frequency) ---\n"
                "Use Google NOTO emoji occasionally to feel friendly and human.\n"
                "Guidelines:\n"
                "- Use 1 emoji every 2–4 messages, not in every reply.\n"
                "- Place emoji naturally (end of sentence, or as emphasis).\n"
                "- Prefer common ones: 😊 👍 🙏 ✅ 🔥 💪 😅.\n"
                "- Animated/special emoji (like 🎉 🎊 ✨) only in segmented multi-part messages.\n"
                "- NEVER use more than 1 emoji per reply.\n"
            )
        elif emoji_level == "high":
            final_system_instruction += (
                "\n\n--- EMOJI USAGE (High Frequency) ---\n"
                "Use Google NOTO emoji to feel lively, warm and very human.\n"
                "Guidelines:\n"
                "- Use 1 emoji every 2 messages.\n"
                "- Place emoji naturally inline or at the end of sentences.\n"
                "- Mix a variety: 😊 😄 🙌 👏 💯 🔥 🙏 😅 😂 ✅ ❤️.\n"
                "- Animated/celebratory emoji (🎉 🎊 ✨ 🥳) only in segmented multi-part messages.\n"
                "- NEVER use more than 1 emoji per reply to avoid visual pollution.\n"
            )


        return {
            "system_instruction": final_system_instruction,
            "budget_tier": workspace.budget_tier if workspace else BudgetTier.GREEN,
            "generation_config": generation_config,
            "tools_enabled": tools_enabled
        }

    def _compile_strategy_prompt(self, strategy: Any) -> str:
        return f"""
TONE: {strategy.tone}
OBJECTIVES: {strategy.objectives}
OBJECTION HANDLING: {strategy.objection_handling}
CTA RULES: {strategy.cta_rules}
"""
