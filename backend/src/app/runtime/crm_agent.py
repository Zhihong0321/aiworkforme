"""
MODULE: Application Runtime - CRM Agent
PURPOSE: Background progression and scheduling engine for leads.
"""
import importlib
import logging
from datetime import datetime, timedelta
from typing import Any, List, Optional
from sqlmodel import Session, select, or_

from src.domain.entities.enums import LeadStage, StrategyStatus, FollowUpPreset
from src.app.runtime.agent_runtime import ConversationAgentRuntime

logger = logging.getLogger(__name__)

class CRMAgent:
    """
    Background Progression & Scheduling Engine.
    Handles follow-up timing, state transitions, and automated review.
    """
    def __init__(self, session: Session, runtime: ConversationAgentRuntime):
        self.session = session
        self.runtime = runtime

    @staticmethod
    def _crm_models():
        models = importlib.import_module("src.adapters.db.crm_models")
        return models.Lead, models.Workspace, models.StrategyVersion

    async def run_review_loop(self):
        """
        Hourly Review Loop: identifies leads requiring follow-up planning.
        """
        Lead, _, _ = self._crm_models()
        cutoff = datetime.utcnow() - timedelta(hours=24)
        statement = select(Lead).where(
            or_(
                Lead.last_followup_review_at == None,
                Lead.last_followup_review_at <= cutoff
            ),
            Lead.stage.in_([LeadStage.NEW, LeadStage.CONTACTED, LeadStage.ENGAGED])
        )
        leads = self.session.exec(statement).all()
        
        for lead in leads:
            self.plan_lead_followup(lead)
            lead.last_followup_review_at = datetime.utcnow()
            self.session.add(lead)
        
        self.session.commit()
        logger.info(f"Review loop completed for {len(leads)} leads")

    async def run_due_dispatcher(self):
        """
        Continuous Due Dispatcher: triggers outbound turns when next_followup_at is reached.
        """
        Lead, _, _ = self._crm_models()
        now = datetime.utcnow()
        statement = select(Lead).where(
            Lead.next_followup_at <= now,
            Lead.stage.in_([LeadStage.NEW, LeadStage.CONTACTED, LeadStage.ENGAGED])
        )
        leads = self.session.exec(statement).all()
        
        for lead in leads:
            logger.info(f"Dispatching due follow-up for lead {lead.id}")
            # Execute turn
            result = await self.runtime.run_turn(lead.id, lead.workspace_id)
            
            # Post-turn timing update
            if result["status"] == "sent":
                self.plan_lead_followup(lead)
                self.session.add(lead)
            elif result["status"] == "blocked" and "CAP" in result["reason"]:
                # Try again in 24h
                lead.next_followup_at = now + timedelta(hours=24)
                self.session.add(lead)
        
        self.session.commit()

    def plan_lead_followup(self, lead: Any):
        """
        Calculates next_followup_at based on Workspace strategy presets.
        """
        _, _, StrategyVersion = self._crm_models()
        strategy = self.session.exec(
            select(StrategyVersion)
            .where(StrategyVersion.workspace_id == lead.workspace_id)
            .where(StrategyVersion.status == StrategyStatus.ACTIVE)
        ).first()

        preset = strategy.followup_preset if strategy else FollowUpPreset.BALANCED
        
        # Interval Logic (MVP Defaults)
        intervals = {
            FollowUpPreset.GENTLE: 72,      # 3 days
            FollowUpPreset.BALANCED: 48,    # 2 days
            FollowUpPreset.AGGRESSIVE: 24   # 1 day
        }
        
        hours = intervals.get(preset, 48)
        
        # Basic heuristic: if lead is ENGAGED, shorten interval
        if lead.stage == LeadStage.ENGAGED:
            hours = hours // 2

        lead.next_followup_at = datetime.utcnow() + timedelta(hours=hours)

    def transition_state(self, lead_id: int, new_stage: Optional[LeadStage] = None, add_tags: List[str] = []):
        """
        Hard lifecycle transition engine with auditability.
        """
        Lead, _, _ = self._crm_models()
        lead = self.session.get(Lead, lead_id)
        if not lead: return

        if new_stage:
            logger.info(f"Lead {lead.id} stage transition: {lead.stage} -> {new_stage}")
            lead.stage = new_stage
        
        if add_tags:
            current_tags = set(lead.tags)
            for tag in add_tags:
                current_tags.add(tag)
            lead.tags = list(current_tags)
            
        self.session.add(lead)
        self.session.commit()
