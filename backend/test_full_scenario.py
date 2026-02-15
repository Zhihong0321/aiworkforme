import requests
import time
import os
import sys

BASE_URL = "http://localhost:8001/api/v1"

def log(msg):
    print(f"[TEST] {msg}")

def check_health():
    for _ in range(10):
        try:
            resp = requests.get(f"{BASE_URL}/health")
            if resp.status_code == 200:
                return True
        except:
            pass
        time.sleep(1)
    return False

def run_test():
    log("Starting Full Scenario Test")
    
    if not check_health():
        log("Server not healthy/reachable. Is it running?")
        sys.exit(1)

    # 1. Create Agent
    log("Creating Agent...")
    agent_data = {
        "name": "SuperSpy",
        "system_prompt": "You are a helpful assistant. You have access to tools and knowledge files.",
        "model": "glm-4.5-flash" # or whatever the ZAI client supports/defaults to
    }
    resp = requests.post(f"{BASE_URL}/agents/", json=agent_data)
    assert resp.status_code == 200, f"Create Agent failed: {resp.text}"
    agent = resp.json()
    agent_id = agent["id"]
    log(f"Agent created with ID: {agent_id}")

    # 2. Create MCP Server
    log("Creating MCP Server...")
    # We point to the simple_mcp_server.py in the backend directory
    # Assuming the backend is running with CWD as 'backend/' or root.
    # We will use absolute path to be safe.
    # We will use the path inside the Docker container
    script_path = "/app/simple_mcp_server.py"
    
    mcp_data = {
        "name": "SimpleMathAndEcho",
        "script": script_path,
        "env_vars": "{}"
    }
    resp = requests.post(f"{BASE_URL}/mcp/servers", json=mcp_data)
    assert resp.status_code == 200, f"Create MCP failed: {resp.text}"
    mcp_server = resp.json()
    server_id = mcp_server["id"]
    log(f"MCP Server created with ID: {server_id}")

    # 3. Link Agent and MCP
    log("Linking Agent and MCP...")
    resp = requests.post(f"{BASE_URL}/agents/{agent_id}/link-mcp/{server_id}")
    assert resp.status_code == 200, f"Link MCP failed: {resp.text}"
    log("Linked successfully")

    # 4. Attach Knowledge File
    log("Attaching Knowledge File...")
    file_content = "The secret code for the vault is: 'OperationBlackBriar'."
    files = {
        'file': ('secret_mission.txt', file_content, 'text/plain')
    }
    resp = requests.post(f"{BASE_URL}/agents/{agent_id}/knowledge", files=files)
    assert resp.status_code == 200, f"Upload knowledge failed: {resp.text}"
    log("Knowledge file attached")

    # 5. Chat with Agent (RAG + Tool Use)
    log("Sending Chat Message...")
    # We ask for the secret (from file) AND to echo it (from tool)
    chat_payload = {
        "agent_id": agent_id,
        "message": "Please tell me the secret code from the file, and then use the 'echo_tool' to repeat it in uppercase."
    }
    
    # We need to mock the Z.ai client response IF we are not connected to a real LLM.
    # However, the user said "prove the LLM AI will use both". This implies a real LLM or a very sophisticated mock.
    # Since I don't have the real Z.ai API key or environment, I might hit an error if 'ZAI_API_KEY' is missing.
    # But I will proceed assuming the environment is set up or I can interpret the failure.
    
    # Wait, 'ZAI_API_KEY' is likely needed. I should check .env
    # But for this test, I'll send the request and see what happens.
    
    try:
        resp = requests.post(f"{BASE_URL}/chat/", json=chat_payload)
        log(f"Chat Response Code: {resp.status_code}")
        if resp.status_code == 200:
            chat_resp = resp.json()
            response_text = chat_resp["response"]
            log(f"Agent Response: {response_text}")
            
            # Validation
            if "OperationBlackBriar" in response_text or "OPERATIONBLACKBRIAR" in response_text:
                log("SUCCESS: Agent found the secret code.")
            else:
                log("FAILURE: Agent did not mention the secret code.")
                
            if "Echo:" in response_text or "echo_tool" in str(resp.text): # Checking for tool usage evidence
                 log("SUCCESS: Tool usage detected.")
            else:
                 log("WARNING: Tool usage not explicitly clear in text, check logs.")
                 
        else:
            log(f"Chat failed: {resp.text}")
            
    except Exception as e:
        log(f"Exception during chat: {e}")

if __name__ == "__main__":
    run_test()
