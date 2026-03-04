import os
import re

base_dir = r"e:\AIworkforMe\backend\routers"

files = [
    "ai_crm_routes.py",
    "ai_crm_runtime.py",
    "ai_crm_helpers.py",
    "ai_crm_schemas.py"
]

for f in files:
    full_path = os.path.join(base_dir, f)
    with open(full_path, "r", encoding="utf-8") as file:
        content = file.read()
    
    # Simple replacements
    content = content.replace("AICRMWorkspaceControl", "AgentCRMProfile")
    content = content.replace("idx_ai_crm_workspace_controls_tenant_workspace", "idx_ai_crm_workspace_controls_tenant_agent")
    content = content.replace("AICRMWorkspaceControl.workspace_id", "AgentCRMProfile.agent_id")
    
    # The trickier part: variables and params
    content = content.replace("workspace_id", "agent_id")
    content = content.replace("validate_workspace", "validate_agent")
    content = content.replace("{workspace_id}", "{agent_id}")
    content = content.replace("WorkspaceControl", "AgentCRMProfile")
    content = content.replace("AICRMLeadStatus", "AICRMLeadStatus") # noop
    content = content.replace("workspace", "agent")

    # In ai_crm_helpers.py we also import Workspace. That might become Agent.
    content = content.replace("from src.adapters.db.crm_models import (", "from src.adapters.db.crm_models import (\n    AgentCRMProfile,")
    content = content.replace("from src.adapters.db.agent_models import Agent", "")
    
    with open(full_path, "w", encoding="utf-8") as file:
        file.write(content)

print("Refactored AI CRM Python files.")
