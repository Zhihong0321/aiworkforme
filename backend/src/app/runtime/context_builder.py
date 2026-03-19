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
from src.app.runtime.sales_materials import (
    build_sales_material_prompt_block,
    list_agent_sales_materials,
    thread_sales_material_state,
)
from src.app.runtime.agent_tooling import VOICE_NOTE_SCRIPT, has_agent_mcp_script
from src.app.conversation_skills import (
    ConversationTaskKind,
    compose_conversation_prompt,
    get_default_conversation_skill_registry,
)

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
        thread_id: Optional[int] = None,
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
        sales_material_prompt = ""
        agent_obj = None
        
        if agent_id:
            Agent = importlib.import_module("src.adapters.db.agent_models").Agent
            agent = self.session.get(Agent, agent_id)
            agent_obj = agent
            if agent and agent.system_prompt:
                agent_system_prompt = agent.system_prompt
            tenant_id = int(lead.tenant_id or (workspace.tenant_id if workspace else 0) or 0)
                
            AgentKnowledgeFile = importlib.import_module("src.adapters.db.agent_models").AgentKnowledgeFile
            statement = select(AgentKnowledgeFile).where(AgentKnowledgeFile.agent_id == agent_id)
            all_files = self.session.exec(statement).all()
            for f in all_files:
                tags = f.tags or "[]"
                if '"fundamental_context"' in tags:
                    global_context_prompt += f"{f.content}\n"
                if '"agent_goal"' in tags:
                    agent_goal_prompt += f"{f.content}\n"

            material_items = list_agent_sales_materials(
                self.session,
                tenant_id=tenant_id,
                agent_id=agent_id,
            )
            sent_state = thread_sales_material_state(
                self.session,
                tenant_id=tenant_id,
                thread_id=thread_id,
            )
            sales_material_prompt = build_sales_material_prompt_block(material_items, sent_state)

        # 2. Real Knowledge Retrieval (RAG)
        knowledge_context = ""
        if agent_id and query:
            chunks = await self.rag.retrieve_context(query, agent_id, tenant_id=workspace.tenant_id if workspace else None)
            knowledge_context = self.rag.format_for_prompt(chunks)

        # 3. Fetch Lead Memory
        memory = self.memory.get_lead_memory(lead_id)
        memory_context = ""
        if memory:
            memory_context = f"Summary: {memory.summary}\nFacts: {', '.join(memory.facts)}"

        # 4. Handle Budget Tiers (Governance)
        extra_sections = []
        if global_context_prompt:
            extra_sections.append(("FUNDAMENTAL CONTEXT", global_context_prompt))
        if agent_goal_prompt:
            extra_sections.append(("AGENT GOAL", agent_goal_prompt))
        if sales_material_prompt:
            extra_sections.append(("SALES MATERIALS", sales_material_prompt))
        if workspace and workspace.budget_tier == BudgetTier.RED:
            base_prompt = f"Role: Brief Assistant. Objectives: {strategy.objectives if strategy else 'Reply helpful'}. No tools."
            strategy_instruction = ""
            generation_config = {"max_tokens": 512, "temperature": 0.5}
            tools_enabled = False
        else:
            base_prompt = agent_system_prompt
            strategy_instruction = strategy_prompt
            generation_config = {"max_tokens": 2048, "temperature": 0.7}
            tools_enabled = True
        if not base_prompt and not strategy_instruction:
            base_prompt = "Role: Professional Assistant."
        if memory_context:
            extra_sections.append(("LEAD PROFILE", memory_context))
        if knowledge_context:
            extra_sections.append(("KNOWLEDGE CONTEXT", knowledge_context))

        # --- SYSTEM BEHAVIOUR INJECTIONS (always appended) ---

        # 1. SEGMENTED MESSAGES — applies to ALL agents globally
        extra_sections.append(("MESSAGE SEGMENTATION RULES", (
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
        )))

        if agent_obj and getattr(agent_obj, "mimic_human_typing", False):
            extra_sections.append(("HUMAN TYPING STYLE (WhatsApp)", (
                "You MUST write exactly like a real human typing on WhatsApp. Strict rules:\n"
                "- Keep replies SHORT. 1–3 sentences max per segment.\n"
                "- Use casual short-forms: 'u', 'r', 'lah', 'la', 'k', 'ok', 'ya', 'yep', 'nope', 'tbh', 'btw', 'omg', 'nvm'.\n"
                "- NO formal punctuation. Avoid full stops at end of sentence. Use lowercase mostly.\n"
                "- Occasionally leave out articles (a, the) like humans do when typing fast.\n"
                "- Sound warm and friendly, NOT robotic or corporate.\n"
                "- Never write long formal paragraphs. Break long answers into segments with |||.\n"
                "- Mirror the user's energy: if they're casual, be casual. If they're urgent, be quick.\n"
            )))

        # 3. EMOJI FREQUENCY (Google NOTO style) — injected based on emoji_level
        emoji_level = getattr(agent_obj, "emoji_level", "none") if agent_obj else "none"
        if emoji_level == "low":
            extra_sections.append(("EMOJI USAGE (Low Frequency)", (
                "Use Google NOTO emoji occasionally to feel friendly and human.\n"
                "Guidelines:\n"
                "- Use 1 emoji every 2–4 messages, not in every reply.\n"
                "- Place emoji naturally (end of sentence, or as emphasis).\n"
                "- Prefer common ones: 😊 👍 🙏 ✅ 🔥 💪 😅.\n"
                "- Animated/special emoji (like 🎉 🎊 ✨) only in segmented multi-part messages.\n"
                "- NEVER use more than 1 emoji per reply.\n"
            )))
        elif emoji_level == "high":
            extra_sections.append(("EMOJI USAGE (High Frequency)", (
                "Use Google NOTO emoji to feel lively, warm and very human.\n"
                "Guidelines:\n"
                "- Use 1 emoji every 2 messages.\n"
                "- Place emoji naturally inline or at the end of sentences.\n"
                "- Mix a variety: 😊 😄 🙌 👏 💯 🔥 🙏 😅 😂 ✅ ❤️.\n"
                "- Animated/celebratory emoji (🎉 🎊 ✨ 🥳) only in segmented multi-part messages.\n"
                "- NEVER use more than 1 emoji per reply to avoid visual pollution.\n"
            )))

        if tools_enabled and agent_id and has_agent_mcp_script(self.session, agent_id, VOICE_NOTE_SCRIPT):
            extra_sections.append(("VOICE NOTE FOLLOW-UP SKILL", (
                "A voice-note follow-up tool is available, but it is expensive and must be used sparingly.\n"
                "Use it only when the lead is cold, dismissive, not replying well, soft-rejecting, or when text/image follow-ups have not worked.\n"
                "Do NOT use voice notes for normal Q&A, routine replies, or first-pass informative answers.\n"
                "If a short sincere voice note gives stronger emotional weight, call the tool instead of replying with normal text.\n"
                "Strict rules:\n"
                "- Voice note cost is much higher than text, so default to text unless there is a strong persuasion reason.\n"
                "- Voice note must be 1-2 short sentences only.\n"
                "- Hard maximum: 15 seconds.\n"
                "- Good use cases include respectful appointment requests and honest feedback probes.\n"
                "- Example style: 希望老板可以给我一次拜访您向您学习的机会。\n"
                "- Example style: 老板，我不介意被拒绝，但是我希望你可以告诉我，我哪里不达标？\n"
                "- When you choose the voice-note tool, do not also send a normal text reply in the same turn.\n"
            )))

        composed = compose_conversation_prompt(
            registry=get_default_conversation_skill_registry(),
            base_prompt=base_prompt,
            task_kind=ConversationTaskKind.CONVERSATION,
            channel="whatsapp",
            agent_id=agent_id,
            tenant_id=int(lead.tenant_id or (workspace.tenant_id if workspace else 0) or 0) or None,
            strategy_prompt=strategy_instruction,
            extra_sections=extra_sections,
        )

        return {
            "system_instruction": composed.system_prompt,
            "budget_tier": workspace.budget_tier if workspace else BudgetTier.GREEN,
            "generation_config": generation_config,
            "tools_enabled": tools_enabled,
            "agent_id": agent_id,
            "conversation_skills": composed.debug_trace,
        }

    def _compile_strategy_prompt(self, strategy: Any) -> str:
        return f"""
TONE: {strategy.tone}
OBJECTIVES: {strategy.objectives}
OBJECTION HANDLING: {strategy.objection_handling}
CTA RULES: {strategy.cta_rules}
"""
