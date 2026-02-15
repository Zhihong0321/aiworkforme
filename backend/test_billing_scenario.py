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
    log("Starting Billing Scenario Test")
    
    if not check_health():
        log("Server not healthy/reachable. Is it running?")
        sys.exit(1)

    # 1. Create or Reuse Agent
    agent_id = None
    existing_agents_resp = requests.get(f"{BASE_URL}/agents/")
    if existing_agents_resp.status_code == 200:
        existing_agents = existing_agents_resp.json()
        for ag in existing_agents:
            if ag.get("name") == "BillingAgent":
                agent_id = ag["id"]
                log(f"Reusing existing Billing Agent with ID: {agent_id}")
                break

    if agent_id is None:
        log("Creating Billing Agent...")
        agent_data = {
            "name": "BillingAgent",
            "system_prompt": "You are a helpful assistant for checking utility bills and solar savings.",
            "model": "gemini-2.0-flash-exp"
        }
        resp = requests.post(f"{BASE_URL}/agents/", json=agent_data)
        if resp.status_code != 200:
            log(f"Create Agent failed: {resp.text}")
            sys.exit(1)
        agent = resp.json()
        agent_id = agent["id"]
        log(f"Agent created with ID: {agent_id}")

    # 2. Create MCP Server
    log("Creating Billing MCP Server...")
    script_rel_path = "billing-mcp-server-v2/main.py"
    
    mcp_data = {
        "name": "BillingMCP",
        "script": script_rel_path,
        "env_vars": "{}"
    }
    resp = requests.post(f"{BASE_URL}/mcp/servers", json=mcp_data)
    if resp.status_code != 200:
        log(f"Create MCP failed: {resp.text}")
        sys.exit(1)
    mcp_server = resp.json()
    server_id = mcp_server["id"]
    log(f"MCP Server created with ID: {server_id}")

    # 3. Start MCP Server (Explicit start might be needed depending on implementation)
    log("Starting MCP Server...")
    resp = requests.post(f"{BASE_URL}/mcp/servers/{server_id}/start")
    if resp.status_code != 200:
        log(f"Start MCP failed: {resp.text}")
        # Proceeding anyway as some implementations might auto-start or be stateless
    else:
        log("MCP Server started.")

    # 4. Link Agent and MCP (Optional for this test but good practice)
    log("Linking Agent and MCP...")
    resp = requests.post(f"{BASE_URL}/agents/{agent_id}/link-mcp/{server_id}")
    if resp.status_code != 200:
        log(f"Link MCP failed: {resp.text}")
        sys.exit(1)
    log("Linked successfully")

    # 5. Call MCP Tool Directly (Bypassing LLM)
    log("Calling MCP Tool 'calculate_solar_impact' directly...")
    tool_payload = {
        "rm": 300
    }
    
    try:
        resp = requests.post(f"{BASE_URL}/mcp/servers/{server_id}/call/calculate_solar_impact", json=tool_payload)
        log(f"Tool Call Response Code: {resp.status_code}")
        
        if resp.status_code == 200:
            result = resp.json()
            log("------ TOOL RESPONSE ------")
            print(result)
            log("---------------------------")
            
            result_str = str(result)
            
            if "Qty Panel Required" in result_str and "Total Saved" in result_str:
                log("SUCCESS: MCP returned the new format.")
            else:
                log("FAILURE: Response does not match expected format.")
        else:
            log(f"Tool call failed: {resp.text}")
            
    except Exception as e:
        log(f"Exception during tool call: {e}")
    finally:
        # Cleanup: Delete the created MCP server and Agent
        if server_id:
            log(f"Deleting MCP Server {server_id}...")
            requests.delete(f"{BASE_URL}/mcp/servers/{server_id}")
        if agent_id:
            log(f"Deleting Agent {agent_id}...")
            requests.delete(f"{BASE_URL}/agents/{agent_id}")



if __name__ == "__main__":
    run_test()
