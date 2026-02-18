
import requests
import json

BASE_URL = "http://localhost:8000/api/v1" # Adjust if needed
TOKEN = "your_token_here" # I need a real token or I should check how to bypass/get one
TENANT_ID = "1"

def test_agents():
    headers = {
        "Authorization": f"Bearer {TOKEN}",
        "X-Tenant-Id": TENANT_ID,
        "Content-Type": "application/json"
    }

    # 1. List agents
    resp = requests.get(f"{BASE_URL}/agents/", headers=headers)
    print(f"List Agents: {resp.status_code}")
    print(resp.text)

    # 2. Create agent
    payload = {
        "name": "Test Agent",
        "model": "glm-4.7-flash",
        "system_prompt": "You are a helpful assistant",
        "reasoning_enabled": True
    }
    resp = requests.post(f"{BASE_URL}/agents/", headers=headers, json=payload)
    print(f"Create Agent: {resp.status_code}")
    print(resp.text)
    
    if resp.status_code == 200:
        agent_id = resp.json().get("id")
        # 3. Update agent
        payload["name"] = "Updated Test Agent"
        resp = requests.put(f"{BASE_URL}/agents/{agent_id}", headers=headers, json=payload)
        print(f"Update Agent: {resp.status_code}")
        print(resp.text)

if __name__ == "__main__":
    # In this environment, I might not have a running server or token.
    # I'll check if there's a test suite I can run.
    pass
