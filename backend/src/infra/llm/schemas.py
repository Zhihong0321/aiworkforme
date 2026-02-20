from enum import Enum
from typing import List, Dict, Optional, Any
from pydantic import BaseModel, Field

class LLMTask(str, Enum):
    CONVERSATION = "conversation"
    EXTRACTION = "extraction"
    REASONING = "reasoning"
    TOOL_USE = "tool_use"
    AI_CRM = "ai_crm"

class LLMMessage(BaseModel):
    role: str  # 'system', 'user', 'assistant', 'tool'
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    tool_call_id: Optional[str] = None

class LLMRequest(BaseModel):
    task: LLMTask
    messages: List[LLMMessage]
    temperature: float = 0.7
    max_tokens: int = 2000
    response_format: Optional[Dict[str, Any]] = None
    tools: Optional[List[Dict[str, Any]]] = None
    extra_params: Dict[str, Any] = Field(default_factory=dict)

class LLMResponse(BaseModel):
    content: Optional[str] = None
    tool_calls: Optional[List[Dict[str, Any]]] = None
    reasoning: Optional[str] = None
    usage: Dict[str, Any] = Field(default_factory=dict)
    provider_info: Dict[str, str] = Field(default_factory=dict)
