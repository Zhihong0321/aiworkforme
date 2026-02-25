import requests

url = "https://ee-baileys-production.up.railway.app/messages/send"
data = {
    "sessionId": "zhihong", 
    "to": "601158942400", 
    "text": "test_text"
}

response = requests.post(url, json=data)
print(response.status_code)
print(response.text)
