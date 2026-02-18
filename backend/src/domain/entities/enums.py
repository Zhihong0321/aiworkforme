"""
Shared Domain Enums for the system.
These are pure data types used across boundaries.
"""
from enum import Enum

class Role(str, Enum):
    PLATFORM_ADMIN = "PLATFORM_ADMIN"
    TENANT_ADMIN = "TENANT_ADMIN"
    TENANT_USER = "TENANT_USER"

class TenantStatus(str, Enum):
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"

class LeadStage(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    ENGAGED = "ENGAGED"
    SUPPRESSED = "SUPPRESSED"
    TAKE_OVER = "TAKE_OVER"
    CLOSED_WON = "CLOSED_WON"
    CLOSED_LOST = "CLOSED_LOST"

class LeadTag(str, Enum):
    DISCONNECT = "DISCONNECT"
    STRATEGY_REVIEW_REQUIRED = "STRATEGY_REVIEW_REQUIRED"

class StrategyStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DRAFT = "DRAFT"
    ROLLED_BACK = "ROLLED_BACK"

class BudgetTier(str, Enum):
    GREEN = "GREEN"
    YELLOW = "YELLOW"
    RED = "RED"

class FollowUpPreset(str, Enum):
    GENTLE = "GENTLE"
    BALANCED = "BALANCED"
    AGGRESSIVE = "AGGRESSIVE"
