import requests
import json

url = "https://zlm-chatbot-production.up.railway.app/api/v1/chat/"
headers = {"Content-Type": "application/json"}
data = {
    "agent_id": 1,
    "message": "Hello",
    "include_reasoning": False
}

try:
    print(f"Sending POST to {url}")
    response = requests.post(url, headers=headers, json=data)
    print(f"Status Code: {response.status_code}")
    print(f"Response Body: {response.text}")
except Exception as e:
    print(f"Request failed: {e}")
