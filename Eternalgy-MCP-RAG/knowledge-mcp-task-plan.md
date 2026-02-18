# Knowledge Vault & Retrieval MCP - Task Plan

## Overview
This plan details the transformation of the current "File Attachment" system into a "Knowledge Vault". 
The goal is to move from "Prompt Stuffing" (injecting all files) to "Agentic Retrieval" (Agent searches for relevant info).
We will add a new "Knowledge Vault" page for management and a specialized MCP Server for retrieval.

## Phase 1: Database Schema & Backend API
**Goal:** Upgrade the storage to support structured knowledge (tags, logs).

- [ ] **1.1. Migration - Update `AgentKnowledgeFile` Table**
    - Add column `tags`: `TEXT` (JSON Array of strings).
    - Add column `description`: `TEXT` (Summary of content).
    - Add column `created_at`: `DATETIME` (Default now).
    - Add column `updated_at`: `DATETIME` (Default now, on update).
    - Add column `last_trigger_inputs`: `TEXT` (JSON Array of last 10 queries that matched this file).
- [ ] **1.2. Backend API - Update Endpoints**
    - Update `POST /api/v1/agents/{agent_id}/knowledge` to accept `tags` and `description` in the form data.
    - Create `PUT /api/v1/knowledge/{file_id}` to allow editing tags, description, and content.
    - Create `DELETE /api/v1/knowledge/{file_id}`.
    - Update `GET /api/v1/agents/{agent_id}/knowledge` to return the new fields.

## Phase 2: Frontend "Knowledge Vault" Page
**Goal:** Create a UI for users to manage the knowledge base effectively.

- [ ] **2.1. Router & Navigation**
    - Add `/agents/:id/knowledge` route (or a global `/knowledge` if intended to be cross-agent, currently assuming Agent-specific).
    - Add "Knowledge Vault" tab/button in the Agent details view.
- [ ] **2.2. Knowledge List View**
    - Display table of files.
    - Columns: Filename, Description, Tags (visual badges), Date Added.
    - Actions: Edit, Delete.
- [ ] **2.3. Add/Edit Knowledge Modal**
    - Input: Filename (or file upload).
    - Input: Description (Text area).
    - Input: Tags (Tag input component - enter to add).
    - Input: Content (Text area if editing text directly, or read-only preview).
- [ ] **2.4. Debug View (Smart Feature)**
    - Show "Recent Triggers" column or modal.
    - Display the content of `last_trigger_inputs` to help the user understand *why* a file was picked.

## Phase 3: Knowledge Retrieval MCP Server
**Goal:** Build the "Brain" that searches the vault.

- [ ] **3.1. Create `mcp_servers/knowledge_retrieval.py`**
    - **Tool 1: `list_library`**
        - Returns: List of `{filename, description, tags}`.
        - Usage: Agent browses what is available.
    - **Tool 2: `read_knowledge(query, tags, limit)`**
        - Logic: Hybrid Search.
            1. Filter by `tags` (if provided).
            2. Score match based on `query` appearing in Filename (High weight), Description (Medium), Tags (Low), Content (Lowest).
            3. **Side Effect:** Update the `last_trigger_inputs` column for the returned records with the `query` string (FIFO queue of 10).
- [ ] **3.2. Register MCP**
    - Ensure this new script is available to be linked to agents.

## Phase 4: Integration & Switch-Over
**Goal:** Stop the "Prompt Stuffing" and enable "Tool Use".

- [ ] **4.1. Disable Auto-Injection**
    - Modify `backend/routers/chat.py` and `websocket_chat.py`.
    - **Remove** the code that loops through `AgentKnowledgeFile` and appends to `system_prompt`.
- [ ] **4.2. Enable MCP Linking**
    - Ensure the `knowledge_retrieval` MCP is added to the Agent's toolset.
    - (Optional) Auto-link this MCP to all agents by default during the transition.
- [ ] **4.3. System Prompt Update**
    - Update default Agent System Prompt to encourage using the tool: *"You have access to a Knowledge Vault. Use `read_knowledge` to find specific information before answering."*

## Phase 5: Verification
- [ ] Test uploading a file with tags.
- [ ] Test chatting with the Agent; verify it calls `read_knowledge`.
- [ ] Verify the Agent answers correctly using the retrieved text.
- [ ] Check the Knowledge Vault UI to see the `last_trigger_inputs` populated.
