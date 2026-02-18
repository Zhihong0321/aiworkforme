import requests
import json

BASE_URL = "http://localhost:9555/api/v1"

def test_chat():
    # 1. Login
    print("Logging in...")
    login_data = {
        "username": "1@1.com",
        "password": "1234",
        "grant_type": "password"
    }
    resp = requests.post(f"{BASE_URL}/auth/login", data=login_data)
    if resp.status_code != 200:
        print(f"Login failed: {resp.status_code} - {resp.text}")
        return
    
    token = resp.json()["access_token"]
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-Tenant-Id": "1"
    }

    # 2. Chat
    print("Sending chat message...")
    chat_payload = {
        "message": "Hello Agent, this is a ROOT CAUSE test via API. Please respond.",
        "agent_id": 1
    }
    
    chat_resp = requests.post(f"{BASE_URL}/playground/chat", headers=headers, json=chat_payload)
    print(f"Chat Response Code: {chat_resp.status_code}")
    print(f"Chat Response Body: {chat_resp.text}")

if __name__ == "__main__":
    test_chat()
