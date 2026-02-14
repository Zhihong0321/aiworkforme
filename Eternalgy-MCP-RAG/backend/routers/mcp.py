from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlmodel import Session, select
from typing import List
import shutil
import os
import hashlib
import json
import logging

from database import get_session
from models import MCPServer
from dependencies import get_mcp_manager
from mcp_manager import MCPManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/mcp", tags=["MCP Management"])

@router.get("/servers", response_model=List[MCPServer])
async def list_mcp_servers(session: Session = Depends(get_session), mcp_manager: MCPManager = Depends(get_mcp_manager)):
    servers = session.exec(select(MCPServer)).all()
    
    # Determine paths relative to this file's parent (backend/) to ensure compatibility
    # with different environments (Docker, Railway, Local).
    # This file is in routers/, so parent is backend/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    scripts_dir = os.getenv("MCP_SCRIPTS_DIR", os.path.join(base_dir, "mcp-runtime-scripts"))
    
    # Enrich with runtime status if available
    for server in servers:
        status_info = await mcp_manager.get_mcp_status(str(server.id))
        
        # Check script existence
        # We join directly to support subdirectories (e.g. "billing-v2/main.py")
        script_path = os.path.join(scripts_dir, server.script)
        script_exists = os.path.exists(script_path)

        if status_info.get("status") != "not found":
             server.status = status_info.get("status")
             server.last_heartbeat = status_info.get("last_heartbeat")
             server.last_error = status_info.get("last_error")
        else:
             # Not running, check if script is missing
             if not script_exists:
                 server.status = "missing_script"
             else:
                 server.status = "ready" # Ready to start

    return servers

@router.post("/servers", response_model=MCPServer)
def create_mcp_server(server: MCPServer, session: Session = Depends(get_session)):
    # Validate env_vars and args are valid JSON
    try:
        json.loads(server.env_vars)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="env_vars must be a valid JSON string")
    
    try:
        json.loads(server.args)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="args must be a valid JSON string")

    session.add(server)
    session.commit()
    session.refresh(server)
    return server

@router.delete("/servers/{server_id}")
async def delete_mcp_server(server_id: int, session: Session = Depends(get_session), mcp_manager: MCPManager = Depends(get_mcp_manager)):
    server = session.get(MCPServer, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Stop if running
    await mcp_manager.terminate_mcp(str(server_id))
    
    session.delete(server)
    session.commit()
    return {"ok": True}

@router.post("/servers/{server_id}/start")
async def start_mcp_server(server_id: int, session: Session = Depends(get_session), mcp_manager: MCPManager = Depends(get_mcp_manager)):
    server = session.get(MCPServer, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")

    # Determine paths relative to this file's parent (backend/) to ensure compatibility
    # with different environments (Docker, Railway, Local).
    # This file is in routers/, so parent is backend/
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    
    scripts_dir = os.getenv("MCP_SCRIPTS_DIR", os.path.join(base_dir, "mcp-runtime-scripts"))

    # Correctly resolve the script path, supporting subdirectories
    full_script_path_in_scripts_dir = os.path.join(scripts_dir, server.script)
    
    logger.info(f"Attempting to start MCP {server_id}. Script path: {full_script_path_in_scripts_dir}")
    logger.info(f"os.path.exists({full_script_path_in_scripts_dir}): {os.path.exists(full_script_path_in_scripts_dir)}")

    if not os.path.exists(full_script_path_in_scripts_dir):
         raise HTTPException(status_code=404, detail=f"Script file not found: {server.script}")
    
    # Parse env_vars
    try:
        env_vars = json.loads(server.env_vars) if server.env_vars else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON in env_vars")

    # Parse args
    try:
        args = json.loads(server.args) if server.args else []
        if not isinstance(args, list):
             # Fallback if it was just a string in old db
             args = [server.script] # Use the original server.script for arg if fallback
    except json.JSONDecodeError:
        # Fallback
        args = [server.script] # Use the original server.script for arg if fallback
    
    # If args is empty and command is python, default to full_script_path_in_scripts_dir
    if not args and server.command == "python":
        args = [full_script_path_in_scripts_dir]
    elif args and server.command == "python" and args[0] == server.script:
        # If the first arg is just the filename, replace with absolute path to be safe
        args[0] = full_script_path_in_scripts_dir

    try:
        result = await mcp_manager.spawn_mcp(
            mcp_id=str(server_id), 
            command=server.command, 
            args=args, 
            cwd=server.cwd,
            env=env_vars
        )
        return result
    except Exception as e:
        logger.error(f"Failed to start MCP {server_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/servers/{server_id}/stop")
async def stop_mcp_server(server_id: int, mcp_manager: MCPManager = Depends(get_mcp_manager)):
    await mcp_manager.terminate_mcp(str(server_id))
    return {"message": "Server stopped"}

@router.get("/servers/{server_id}/status")
async def mcp_server_status(server_id: int, mcp_manager: MCPManager = Depends(get_mcp_manager)):
    status = await mcp_manager.get_mcp_status(str(server_id))
    return status

@router.get("/servers/{server_id}/tools")
async def mcp_server_tools(server_id: int, mcp_manager: MCPManager = Depends(get_mcp_manager)):
    try:
        tools = await mcp_manager.list_mcp_tools(str(server_id))
        return {"tools": [tool.model_dump() for tool in tools]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/servers/{server_id}/call/{tool_name}")
async def call_mcp_server_tool(server_id: int, tool_name: str, tool_args: dict, mcp_manager: MCPManager = Depends(get_mcp_manager)):
    try:
        result = await mcp_manager.call_mcp_tool(str(server_id), tool_name, tool_args)
        return {"result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/upload")
async def upload_mcp_script(file: UploadFile = File(...)):
    """
    Upload an MCP asset (server script or data). Allows .py and .json so data
    files like bill.json can ship alongside the server script.
    """
    # 1. Validation
    allowed_exts = (".py", ".json")
    if not any(file.filename.endswith(ext) for ext in allowed_exts):
        raise HTTPException(status_code=400, detail="Only .py or .json files are allowed.")
    
    # 2. Path Traversal Prevention
    filename = os.path.basename(file.filename)
    if not filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    upload_dir = os.getenv("MCP_UPLOAD_DIR", os.getenv("MCP_SCRIPTS_DIR", "/app/scripts"))
    os.makedirs(upload_dir, exist_ok=True)
    file_path = os.path.join(upload_dir, filename)
    
    # 3. Size Limit & Checksum
    MAX_SIZE = 10 * 1024 * 1024 # 10MB
    sha256_hash = hashlib.sha256()
    size = 0
    
    with open(file_path, "wb") as buffer:
        while True:
            chunk = await file.read(4096)
            if not chunk:
                break
            size += len(chunk)
            if size > MAX_SIZE:
                buffer.close()
                os.remove(file_path)
                raise HTTPException(status_code=400, detail="File too large (max 10MB)")
            
            sha256_hash.update(chunk)
            buffer.write(chunk)
            
    checksum = sha256_hash.hexdigest()
        
    return {
        "filename": filename, 
        "path": file_path, 
        "size_bytes": size, 
        "checksum": checksum
    }
