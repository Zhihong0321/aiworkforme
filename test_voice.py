import requests
import json
import os

url = "https://api.uniapi.io/v1/audio/speech"

payload = json.dumps({
  "model": "qwen3-tts-flash",
  "voice": "Cherry",
  "input": "Today is a wonderful day to build something people love!",
  "instructions": "Speak in a cheerful and positive tone."
})
headers = {
  'Authorization': 'Bearer sk-0DKo24DHKjaQb6D_iL6HjeN8WORuuA5c_Qmcz7v9VvKYa5BFwcBgYZeMOVQ',
  'Content-Type': 'application/json'
}

response = requests.request("POST", url, headers=headers, data=payload)

if response.status_code == 200:
    with open("speech.mp3", "wb") as f:
        f.write(response.content)
    print("Generated voice note at speech.mp3")
else:
    print(f"Error {response.status_code}: {response.text}")
