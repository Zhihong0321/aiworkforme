
import requests
import json
import sys

BASE_URL = "http://localhost:9555/api/v1"
PLAYGROUND_URL = f"{BASE_URL}/playground"

def test_playground_flow():
    # 1. Login (Mock if needed, or use existing token if we have one)
    # We'll assume no auth needed for local localhost testing if we disabled it, 
    # BUT we know it needs auth.
    # Note: We are running from OUTSIDE container, so localhost:9555.
    
    # Authenticate
    print("Authenticating...")
    try:
        resp = requests.post(f"{BASE_URL}/auth/login", data={"username": "1@1.com", "password": "1234", "grant_type": "password"}) # correct creds
        if resp.status_code != 200:
            print(f"Login failed: {resp.text}")
            # Try to register or assume seeding worked
            return
        token = resp.json()["access_token"]
        headers = {
            "Authorization": f"Bearer {token}",
            "X-Tenant-Id": "1"
        }
    except Exception as e:
        print(f"Auth failed: {e}")
        return

    # 2. Get Agents
    print("Fetching Agents...")
    resp = requests.get(f"{BASE_URL}/agents/", headers=headers)
    if resp.status_code != 200:
        print(f"Get Agents failed: {resp.text}")
        return
    agents = resp.json()
    if not agents:
        print("No agents found. Creating one...")
        agent_data = {"name": "Test Agent", "model": "glm-4.7-flash", "system_prompt": "You are a tester."}
        resp = requests.post(f"{BASE_URL}/agents/", json=agent_data, headers=headers)
        agent_id = resp.json()["id"]
    else:
        agent_id = agents[0]["id"]
    print(f"Using Agent ID: {agent_id}")

    # 3. Send Message
    print("Sending Chat Message...")
    chat_payload = {
        "message": "Hello from Python Test Script",
        "agent_id": agent_id
    }
    resp = requests.post(f"{PLAYGROUND_URL}/chat", json=chat_payload, headers=headers)
    print(f"Chat Response Code: {resp.status_code}")
    print(f"Chat Response Payload: {resp.text}")

    if resp.status_code == 200:
        data = resp.json()
        if data.get("result", {}).get("status") == "error":
            print(f"Chat Logic Error: {data['result']['message']}")
        else:
            print("Chat Success!")

    # 4. Fetch Thread
    # We need lead_id from the decision or guess it. 
    # The chat response includes decisions.
    decisions = resp.json().get("decisions", [])
    if decisions:
        lead_id = decisions[0]["lead_id"]
        print(f"Fetching Thread for Lead {lead_id}...")
        resp = requests.get(f"{PLAYGROUND_URL}/thread/{lead_id}", headers=headers)
        print(f"Thread Messages Count: {len(resp.json())}")
        print(resp.json())
    else:
        print("No decisions returned, cannot guess lead_id.")

if __name__ == "__main__":
    test_playground_flow()
