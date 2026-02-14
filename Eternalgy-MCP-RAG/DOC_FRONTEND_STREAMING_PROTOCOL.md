# Frontend Streaming Protocol Guide (WebSockets)

## 1. Overview
We have migrated the Chat interaction from a synchronous HTTP POST to a **WebSocket** connection. This enables:
-   **Real-time Streaming**: Users see the text appearing as the AI thinks.
-   **Tool Transparency**: The UI can show "Processing..." states when the AI uses tools (e.g., "Reading file...", "Searching database...").
-   **Queuing**: If the server is busy, the socket remains open and waits for its turn automatically.

## 2. Connection Details
**URL**: `ws://localhost:8001/api/v1/ws/chat/{agent_id}`
*   Replace `{agent_id}` with the actual ID of the agent (e.g., `1`, `2`).

**Handshake**:
-   Connect to the URL.
-   The connection stays open for the duration of the *session*. You can send multiple messages over one connection, or reconnect per session. Recommending **one connection per session**.

## 3. Communication Protocol

### 3.1 Sending a Message (Client -> Server)
Send a JSON string with the user's message.
```json
{
  "message": "Analyze the attached log file and tell me the error."
}
```

### 3.2 Receiving Events (Server -> Client)
The server sends JSON objects with a `type` field. Handle these events to update the UI.

#### A. Token (The "Streaming" Text)
Append this content to the Assistant's last message bubble.
```json
{
  "type": "token",
  "content": "The "
}
```
```json
{
  "type": "token",
  "content": "error "
}
```

#### B. Tool Start (Show a "Loading" or "Status" Indicator)
The AI has stopped generating text and is running a backend tool. Show a spinner or status text.
```json
{
  "type": "tool_start",
  "tool": "grep_file",
  "input": "{\"pattern\": \"ERROR\", \"file\": \"server.log\"}"
}
```
*UI Suggestion*: Display a small badge: `⚙️ Running grep_file...`

#### C. Tool End (Update Status or Show Result)
The tool finished. The AI will likely resume generating text (`token` events) immediately after this.
```json
{
  "type": "tool_end",
  "result": "Found 5 matches for 'ERROR'..."
}
```

#### D. Done (Turn Complete)
The AI has finished its turn. Stop the cursor blink/breathing effect.
This event now includes **Token Usage Stats**.
```json
{
  "type": "done",
  "tokens": {
    "prompt": 150,
    "completion": 45,
    "total": 195
  }
}
```

#### E. Error
Something went wrong. Show a toast or error message.
```json
{
  "type": "error",
  "content": "Agent not found"
}
```

## 4. Example Integration (Vue 3)

```javascript
const connectChat = (agentId) => {
  const ws = new WebSocket(`ws://localhost:8001/api/v1/ws/chat/${agentId}`)
  
  ws.onopen = () => {
    console.log('Connected to Z.ai Neural Stream')
  }
  
  ws.onmessage = (event) => {
    const data = JSON.parse(event.data)
    
    switch (data.type) {
      case 'token':
        // Append data.content to currentMessage.text
        currentMessage.value.text += data.content
        scrollToBottom()
        break
        
      case 'tool_start':
        // Show status: "Agent is using tool: " + data.tool
        isThinking.value = true
        statusText.value = `Using ${data.tool}...`
        break
        
      case 'tool_end':
        // Hide status
        isThinking.value = false
        break
        
      case 'done':
        console.log(`Turn finished. Used ${data.tokens.total} tokens.`).
        break
    }
  }
  
  return ws
}

// Sending
const sendMessage = (ws, text) => {
  ws.send(JSON.stringify({ message: text }))
}
```
