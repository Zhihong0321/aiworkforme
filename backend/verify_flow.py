import requests
import json
import sys

BASE_URL = "http://127.0.0.1:8000/api/v1"

def test_flow():
    print("--- Starting Backend SoC Verification Test ---")
    
    # 1. Login
    print("\n1. Testing Login...")
    login_data = {"username": "admin@aiworkfor.me", "password": "admin12345"}
    resp = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if resp.status_code != 200:
        print(f"FAILED: Login failed {resp.text}")
        return
    token = resp.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "X-Tenant-Id": "1"
    }
    print("SUCCESS: Logged in.")

    # 2. Get/Create Workspace
    print("\n2. Getting Workspaces...")
    resp = requests.get(f"{BASE_URL}/workspaces/", headers=headers)
    workspaces = resp.json()
    print(f"Workspaces response: {workspaces}")
    if not isinstance(workspaces, list) or not workspaces:
        print("Creating a test workspace...")
        ws_resp = requests.post(f"{BASE_URL}/workspaces/", json={"name": "Test Workspace", "tenant_id": 1}, headers=headers)
        workspace = ws_resp.json()
    else:
        workspace = workspaces[0]
    ws_id = workspace["id"]
    print(f"SUCCESS: Using Workspace ID {ws_id}")

    # 3. Add Lead
    print("\n3. Adding Lead...")
    lead_data = {
        "name": "John Doe",
        "external_id": "whatsapp:+123456789",
        "stage": "NEW",
        "tenant_id": 1
    }
    resp = requests.post(f"{BASE_URL}/workspaces/{ws_id}/leads", json=lead_data, headers=headers)
    if resp.status_code != 200:
        print(f"FAILED: Add Lead failed {resp.text}")
        return
    else:
        lead = resp.json()
        print(f"SUCCESS: Lead created with ID {lead['id']}")

    # 4. Add Skill (MCP)
    print("\n4. Adding Skill (MCP)...")
    mcp_data = {
        "name": "Test Skill",
        "script": "test_skill.py",
        "env_vars": "{}"
    }
    resp = requests.post(f"{BASE_URL}/mcp/servers", json=mcp_data, headers=headers)
    if resp.status_code != 200:
        print(f"FAILED: Add MCP failed {resp.text}")
    else:
        mcp = resp.json()
        print(f"SUCCESS: MCP Server created with ID {mcp['id']}")

    # 5. Add Knowledge
    print("\n5. Adding Knowledge...")
    resp = requests.get(f"{BASE_URL}/agents/", headers=headers)
    agents = resp.json()
    if not agents:
        print("Creating agent first...")
        agent_data = {"name": "Test Agent", "system_prompt": "Helpful", "model": "gpt-4", "tenant_id": 1}
        agent_resp = requests.post(f"{BASE_URL}/agents/", json=agent_data, headers=headers)
        agent = agent_resp.json()
    else:
        agent = agents[0]
    agent_id = agent["id"]
    
    files = {'file': ('test.txt', 'This is some test knowledge.', 'text/plain')}
    data = {'tags': '["test"]', 'description': 'Test file'}
    resp = requests.post(f"{BASE_URL}/agents/{agent_id}/knowledge", files=files, data=data, headers=headers)
    if resp.status_code != 200:
        print(f"FAILED: Add Knowledge failed {resp.text}")
    else:
        print("SUCCESS: Knowledge added.")

    # 6. Playground Chat
    print("\n6. Testing Playground Chat...")
    # This uses ZaiClient, if dummy-key is used it might fail if it tries real LLM.
    # But we check if the endpoint is reachable and logic executes.
    chat_data = {
        "lead_id": lead["id"],
        "workspace_id": ws_id,
        "message": "Hello, who are you?"
    }
    resp = requests.post(f"{BASE_URL}/playground/chat", json=chat_data, headers=headers)
    if resp.status_code == 503:
         print("SUCCESS: Chat endpoint reached (503 Service Unavailable as expected with dummy key).")
    elif resp.status_code == 200:
         print("SUCCESS: Chat successful.")
    else:
         print(f"FAILED: Chat failed with {resp.status_code}: {resp.text}")

    print("\n--- Verification Test Completed ---")

if __name__ == "__main__":
    test_flow()
