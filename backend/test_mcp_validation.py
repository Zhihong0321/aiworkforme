import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock
import json
import os
import tempfile
import shutil

# Import app and dependencies
from main import app
from database import get_session
from dependencies import get_mcp_manager
from models import MCPServer
from sqlmodel import Session, create_engine, SQLModel
from sqlmodel.pool import StaticPool

# Setup In-Memory DB
engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
SQLModel.metadata.create_all(engine)

def get_session_override():
    with Session(engine) as session:
        yield session

# Setup Mock MCP Manager
mock_mcp_manager = MagicMock()
mock_mcp_manager.spawn_mcp = AsyncMock(return_value={"status": "registered"})
mock_mcp_manager.get_mcp_status = AsyncMock(return_value={"status": "stopped"})
mock_mcp_manager.list_mcp_tools = AsyncMock(return_value=[])
mock_mcp_manager.call_mcp_tool = AsyncMock(return_value="Tool Result")
mock_mcp_manager.terminate_mcp = AsyncMock()

# Apply Overrides
app.dependency_overrides[get_session] = get_session_override
app.dependency_overrides[get_mcp_manager] = lambda: mock_mcp_manager

client = TestClient(app)

# Setup Temp Dir for Uploads
test_upload_dir = tempfile.mkdtemp()
os.environ["MCP_UPLOAD_DIR"] = test_upload_dir
os.environ["MCP_SCRIPTS_DIR"] = test_upload_dir

@pytest.fixture(scope="module", autouse=True)
def cleanup_temp_dir():
    yield
    shutil.rmtree(test_upload_dir)

def test_upload_mcp_script_validation():
    # Test 1: Invalid Extension
    response = client.post(
        "/api/v1/mcp/upload",
        files={"file": ("test.txt", b"print('hello')", "text/plain")}
    )
    assert response.status_code == 400
    assert "Only .py files" in response.json()["detail"]

    # Test 2: Valid Upload
    response = client.post(
        "/api/v1/mcp/upload",
        files={"file": ("good_script.py", b"print('hello')", "text/x-python")}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "good_script.py"
    assert "checksum" in data
    assert os.path.exists(os.path.join(test_upload_dir, "good_script.py"))

def test_create_mcp_server_validation():
    # Test Invalid JSON in env_vars
    response = client.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Bad Env",
            "script": "script.py",
            "env_vars": "{bad_json",
            "command": "python"
        }
    )
    assert response.status_code == 400
    assert "env_vars" in response.json()["detail"]

    # Test Valid creation
    response = client.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Good Server",
            "script": "script.py",
            "env_vars": "{\"KEY\": \"VALUE\"}",
            "command": "python",
            "args": "[\"arg1\"]"
        }
    )
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "Good Server"
    assert data["env_vars"] == "{\"KEY\": \"VALUE\"}"
    
    return data["id"]

@pytest.mark.asyncio
async def test_start_mcp_server():
    # Create the script file
    script_path = os.path.join(test_upload_dir, "start.py")
    with open(script_path, "w") as f:
        f.write("print('started')")

    # Create server first
    response = client.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Start Server",
            "script": "start.py",
            "env_vars": "{\"API_KEY\": \"123\"}",
            "command": "python3",
            "cwd": "/tmp"
        }
    )
    server_id = response.json()["id"]

    # Start Server
    response = client.post(f"/api/v1/mcp/servers/{server_id}/start")
    assert response.status_code == 200
    
    # Verify mock call
    mock_mcp_manager.spawn_mcp.assert_called_with(
        mcp_id=str(server_id),
        command="python3",
        args=[script_path], # Expect absolute path now
        cwd="/tmp",
        env={"API_KEY": "123"}
    )

@pytest.mark.asyncio
async def test_start_mcp_server_with_custom_args():
    # Create script
    script_path = os.path.join(test_upload_dir, "args.py")
    with open(script_path, "w") as f:
        f.write("print('args')")

    # Create server
    response = client.post(
        "/api/v1/mcp/servers",
        json={
            "name": "Args Server",
            "script": "args.py",
            "args": "[\"-v\", \"--flag\"]"
        }
    )
    server_id = response.json()["id"]

    # Start
    client.post(f"/api/v1/mcp/servers/{server_id}/start")

    # Verify mock
    # get the last call
    call_args = mock_mcp_manager.spawn_mcp.call_args
    assert call_args.kwargs['args'] == ["-v", "--flag"]
