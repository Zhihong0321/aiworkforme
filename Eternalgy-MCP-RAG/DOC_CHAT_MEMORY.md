# Chat and Memory Implementation Guide

## Overview
The system implements chat functionality with persistent memory, ensuring conversations are stateful and context-aware.

## 1. Chat Architecture
The chat system is built on a **FastAPI** backend with a **PostgreSQL** database.

### Core Components
*   **ChatSession**: Represents a conversation thread. Links a User to an Agent.
*   **ChatMessage**: Individual messages (User or Assistant) within a session.
*   **Agent**: The persona configuration (System Prompt, Model, Temperature).

## 2. Memory Persistence (Database)
Unlike simple in-memory scripts, the backend persists all interactions.

### Data Models (`backend/app/models/models.py`)
*   **`ChatSession`**: `id`, `user_id`, `agent_id`, `created_at`
*   **`ChatMessage`**: `id`, `session_id`, `role` (user/assistant), `content`, `reasoning_content`.

### Workflow (`backend/app/api/chat.py`)
1.  **Receive Message**: User POSTs message to `/{session_id}/messages`.
2.  **Persist User Message**: Input is immediately saved to `ChatMessage` table.
3.  **Context Construction**:
    *   Retrieves `Agent` details (System Prompt).
    *   Retrieves `SessionKnowledge` (Uploaded files).
    *   Constructs a `system_prompt` string containing all context.
4.  **AI Generation**: Calls Z.ai API.
5.  **Persist AI Response**: The result (Content + Reasoning) is saved to `ChatMessage` table.

## 3. Context & History Injection
To "remember" the conversation during generation, the system injects context into the API call.

*   **System Context**:
    ```python
    context = f"Agent: {agent.name}\nSystem Prompt: {agent.system_prompt}"
    ```
*   **Knowledge Context** (RAG-lite):
    Uploaded files are appended to the system prompt:
    ```python
    if knowledge_files:
        context += "\n\nKnowledge Context:\n"
        for kf in knowledge_files:
            context += f"\n--- {kf.filename} ---\n{kf.content}\n"
    ```

## 4. CLI vs Backend
*   **CLI (`zai_chatbot.py`)**: Uses a simple Python `list` (`messages = [...]`) to maintain history during the runtime of the script. Lost on exit.
*   **Backend**: Uses **PostgreSQL** to store history permanently. Context is reconstructed for each request.

## Summary
*   **Storage**: PostgreSQL (`chat_messages` table).
*   **Context**: System Prompt + Uploaded Knowledge Files.
*   **Retrieval**: Session-based lookup.
