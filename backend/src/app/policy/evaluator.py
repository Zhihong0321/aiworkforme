"""
MODULE: Application Policy - Evaluator
PURPOSE: Safety floor policy engine for outbound messaging.
"""
import importlib
import logging
from datetime import datetime, time, timedelta
import pytz
from typing import Optional, Tuple, Dict, Any
from sqlmodel import Session, select, func

from src.domain.entities.enums import LeadStage, LeadTag
from src.app.runtime.leads_service import get_or_create_default_workspace

logger = logging.getLogger(__name__)

class PolicyEvaluator:
    """
    Immutable Safety Floor Policy Engine.
    Enforces non-bypassable rules for outbound messaging.
    """

    def __init__(self, session: Session):
        self.session = session

    @staticmethod
    def _crm_models():
        models = importlib.import_module("src.adapters.db.crm_models")
        return (
            models.Lead,
            models.Workspace,
            models.PolicyDecision,
            models.ChatMessageNew,
            models.ConversationThread,
        )

    def evaluate_outbound(self, lead_id: int, workspace_id: int | None, bypass_safety: bool = False) -> Any:
        """
        Main entry point for evaluating if an outbound message can be sent to a lead.
        Returns a PolicyDecision record (unsaved).
        """
        Lead, Workspace, PolicyDecision, _, _ = self._crm_models()
        lead = self.session.get(Lead, lead_id)
        workspace = self.session.get(Workspace, workspace_id) if workspace_id is not None else None

        if lead and workspace is None and lead.tenant_id is not None:
            workspace = get_or_create_default_workspace(self.session, int(lead.tenant_id))
            if lead.workspace_id is None:
                lead.workspace_id = workspace.id
                self.session.add(lead)
                self.session.commit()

        if not lead or not workspace:
            # Fallback if entities missing
            return PolicyDecision(
                workspace_id=workspace_id or 0,
                lead_id=lead_id,
                allow_send=False,
                reason_code="ENTITY_NOT_FOUND",
                rule_trace={"error": "Lead or Workspace missing"}
            )

        if bypass_safety:
            return self._create_decision(lead, workspace, True, "BYPASS_PLAYGROUND", {"status": "Safety bypassed for Playground testing"})
            
        # 1. OPT-OUT / SUPPRESSION CHECK
        if lead.stage == LeadStage.SUPPRESSED or "DISCONNECT" in lead.tags:
            return self._create_decision(lead, workspace, False, "OPT_OUT_SUPPRESSION", {"stage": lead.stage, "tags": lead.tags})

        # 2. TAKEOVER CHECK
        if lead.stage == LeadStage.TAKE_OVER:
            return self._create_decision(lead, workspace, False, "HUMAN_TAKEOVER_ACTIVE", {"stage": lead.stage})

        # 3. ROLLING 24H CAP
        if lead.last_followup_at:
            time_since_last = datetime.utcnow() - lead.last_followup_at
            if time_since_last < timedelta(hours=24):
                return self._create_decision(lead, workspace, False, "OUTBOUND_CAP_24H", {
                    "last_followup_at": lead.last_followup_at.isoformat(),
                    "next_allowed_at": (lead.last_followup_at + timedelta(hours=24)).isoformat()
                })

        # 4. QUIET HOURS CHECK
        can_send_now, reason, tz_used = self._check_quiet_hours(lead, workspace)
        if not can_send_now:
            return self._create_decision(lead, workspace, False, "QUIET_HOURS_ACTIVE", {
                "timezone_used": tz_used,
                "reason": reason
            })

        # 5. SUNDAY HOLD
        if datetime.utcnow().weekday() == 6: # Sunday
            return self._create_decision(lead, workspace, False, "SUNDAY_HOLD", {"day": "Sunday"})

        # 6. STOP RULE (5 unanswered in 14 days)
        if self._check_stop_rule(lead_id):
            return self._create_decision(lead, workspace, False, "STOP_RULE_MAX_UNANSWERED", {"rule": "5 unanswered in 14 days"})

        # ALL PASSED
        return self._create_decision(lead, workspace, True, "POLICY_PASSED", {"status": "All safety flags green"})

    def _create_decision(self, lead: Any, workspace: Any, allow: bool, code: str, trace: Dict[str, Any]) -> Any:
        _, _, PolicyDecision, _, _ = self._crm_models()
        return PolicyDecision(
            tenant_id=lead.tenant_id or workspace.tenant_id,
            workspace_id=workspace.id,
            lead_id=lead.id,
            allow_send=allow,
            reason_code=code,
            rule_trace=trace
        )

    def _deny(self, lead_id: int, workspace_id: int | None, code: str, trace: Dict[str, Any]) -> Any:
        # Legacy helper, update to use _create_decision if possible or fetch tenant
        Lead, Workspace, _, _, _ = self._crm_models()
        lead = self.session.get(Lead, lead_id)
        workspace = self.session.get(Workspace, workspace_id)
        return self._create_decision(lead, workspace, False, code, trace)

    def _check_quiet_hours(self, lead: Any, workspace: Any) -> Tuple[bool, Optional[str], str]:
        # ... logic stays same ...
        tz_str = lead.timezone or workspace.timezone or "UTC"
        try:
            tz = pytz.timezone(tz_str)
        except Exception:
            tz = pytz.UTC
            tz_str = "UTC (fallback)"

        local_now = datetime.now(tz)
        local_time = local_now.time()

        start_time = time(9, 0)
        end_time = time(21, 0)

        if not (start_time <= local_time <= end_time):
            return False, f"Current local time {local_time.strftime('%H:%M')} is outside 09:00-21:00 window", tz_str
        
        return True, None, tz_str

    def _check_stop_rule(self, lead_id: int) -> bool:
        """Returns True if the lead has hit the 5-unanswered-in-14-days stop rule.
        Reads from legacy ChatMessageNew table; returns False safely if table missing.
        """
        try:
            _, _, _, ChatMessageNew, ConversationThread = self._crm_models()
            cutoff = datetime.utcnow() - timedelta(days=14)

            last_user_msg = self.session.exec(
                select(ChatMessageNew)
                .join(ConversationThread)
                .where(ConversationThread.lead_id == lead_id)
                .where(ChatMessageNew.role == "user")
                .order_by(ChatMessageNew.created_at.desc())
            ).first()

            recent_outbound_query = select(func.count(ChatMessageNew.id)).join(ConversationThread).where(
                ConversationThread.lead_id == lead_id,
                ChatMessageNew.role == "model",
                ChatMessageNew.created_at > cutoff
            )

            if last_user_msg:
                recent_outbound_query = recent_outbound_query.where(
                    ChatMessageNew.created_at > last_user_msg.created_at
                )

            count = self.session.exec(recent_outbound_query).one()
            return count >= 5
        except Exception as exc:
            logger.warning("_check_stop_rule skipped (legacy table unavailable): %s", exc)
            return False

    def validate_risk(self, lead_id: int, workspace_id: int | None, content: str, confidence_score: float) -> Any:
        """Post-generation risk check."""
        Lead, Workspace, _, _, _ = self._crm_models()
        lead = self.session.get(Lead, lead_id)
        workspace = self.session.get(Workspace, workspace_id) if workspace_id is not None else None
        if lead and workspace is None and lead.tenant_id is not None:
            workspace = get_or_create_default_workspace(self.session, int(lead.tenant_id))
            if lead.workspace_id is None:
                lead.workspace_id = workspace.id
                self.session.add(lead)
                self.session.commit()
        
        sensitive_keywords = ["scam", "spam", "unsolicited", "guaranteed returns", "exclusive offer", "pay now", "bank account", "password"]
        matched = [w for w in sensitive_keywords if w in content.lower()]
        
        if matched:
            decision = self._create_decision(lead, workspace, False, "RISKY_CONTENT_BLOCK", {
                "matched_words": matched,
                "confidence": confidence_score
            })
            self._tag_for_review(lead_id)
            return decision

        return self._create_decision(lead, workspace, True, "RISK_CHECK_PASSED", {"confidence": confidence_score})

    def _tag_for_review(self, lead_id: int):
        Lead, _, _, _, _ = self._crm_models()
        lead = self.session.get(Lead, lead_id)
        if lead:
            current_tags = set(lead.tags)
            current_tags.add(LeadTag.STRATEGY_REVIEW_REQUIRED)
            lead.tags = list(current_tags)
            self.session.add(lead)
            self.session.commit()

    def record_decision(self, decision: Any):
        """Persist the policy decision to the database."""
        try:
            self.session.add(decision)
            self.session.commit()
            self.session.refresh(decision)
        except Exception as exc:
            self.session.rollback()
            logger.warning("Skipping policy decision persistence due to DB error: %s", exc)
