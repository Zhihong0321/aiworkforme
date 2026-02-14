import os
from mcp_manager import MCPManager
from zai_client import ZaiClient

# Singleton instances
mcp_manager = MCPManager()
zai_client = ZaiClient(api_key=os.getenv("ZAI_API_KEY"))

def get_mcp_manager() -> MCPManager:
    return mcp_manager

def get_zai_client() -> ZaiClient:
    return zai_client