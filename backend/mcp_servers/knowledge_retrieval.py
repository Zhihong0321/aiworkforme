import os
import json
from typing import List, Dict, Optional, Any
from mcp.server import MCPServer, Tool
from sqlmodel import Session, create_engine, select
from models import AgentKnowledgeFile # Assuming models.py is accessible or copied
from datetime import datetime

# --- Configuration ---
# This will usually come from environment variables or a config file
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:password" + "@db:5432/chatbot_db")
# For local testing, ensure this points to your DB
# Example: DATABASE_URL = "postgresql://user:db_password" + "@localhost:5432/chatbot_db"

# --- Database Setup ---
engine = create_engine(DATABASE_URL)

def get_session():
    with Session(engine) as session:
        yield session

# --- Helper Functions ---
def parse_json_field(json_str: str) -> List[str]:
    try:
        parsed = json.loads(json_str)
        return [str(item) for item in parsed if isinstance(item, (str, int, float, bool))]
    except (json.JSONDecodeError, TypeError):
        return []

def update_last_trigger_inputs(session: Session, file_id: int, query: str):
    knowledge_file = session.get(AgentKnowledgeFile, file_id)
    if knowledge_file:
        trigger_inputs = parse_json_field(knowledge_file.last_trigger_inputs)
        # Add the new query, keep only the last 10
        trigger_inputs.insert(0, f"{datetime.utcnow().isoformat()} - {query}")
        knowledge_file.last_trigger_inputs = json.dumps(trigger_inputs[:10])
        knowledge_file.updated_at = datetime.utcnow()
        session.add(knowledge_file)
        session.commit()
        session.refresh(knowledge_file)

class KnowledgeRetrievalMCP(MCPServer):
    def __init__(self, name: str = "Knowledge Retrieval MCP"):
        super().__init__(name)

    @Tool(
        name="list_library",
        description="Lists available knowledge files for an agent. Use this to understand what knowledge domains are available. Does not return content.",
        input_schema={
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: Filter files by a list of associated tags (e.g., ['policy', 'billing']).",
                }
            },
            "required": [],
        },
        output_schema={
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "filename": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                },
            },
        },
    )
    async def list_library(self, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        session = next(get_session())
        query = select(AgentKnowledgeFile)
        
        if tags:
            # Filter by tags: Check if ANY of the file's tags are in the requested tags
            # This requires JSONB operations for PostgreSQL for optimal performance, 
            # but for TEXT, we'll do a simple LIKE check or parse then filter.
            # For now, a simple text search on the JSON string. This is not efficient for large datasets.
            for tag in tags:
                query = query.filter(AgentKnowledgeFile.tags.contains(f'"{tag}"'))

        files = session.exec(query).all()
        
        results = []
        for file in files:
            results.append({
                "id": file.id,
                "filename": file.filename,
                "description": file.description,
                "tags": parse_json_field(file.tags),
            })
        return results

    @Tool(
        name="read_knowledge",
        description="Searches and retrieves relevant snippets or full content from the knowledge base based on a query and optional tags. Prioritizes exact matches in filename/description. Only returns up to 3 most relevant results.",
        input_schema={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query or keywords to find in the knowledge base (e.g., 'refund policy', 'API endpoints').",
                },
                "tags": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: Filter search results by a list of associated tags (e.g., ['hr', 'finance']).",
                },
                "limit": {
                    "type": "integer",
                    "description": "Optional: Maximum number of results to return (default: 3).",
                    "default": 3,
                },
            },
            "required": ["query"],
        },
        output_schema={
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "filename": {"type": "string"},
                    "description": {"type": "string"},
                    "tags": {"type": "array", "items": {"type": "string"}},
                    "content_snippet": {"type": "string", "description": "A relevant snippet or the full content if small."},
                },
            },
        },
    )
    async def read_knowledge(
        self, query: str, tags: Optional[List[str]] = None, limit: int = 3
    ) -> List[Dict[str, Any]]:
        session = next(get_session())
        all_knowledge_files = session.exec(select(AgentKnowledgeFile)).all()

        candidates = []
        for file in all_knowledge_files:
            file_tags = parse_json_field(file.tags)
            
            # Tag filtering
            if tags and not any(tag in file_tags for tag in tags):
                continue # Skip if no tag overlap and tags were provided

            score = 0
            lower_query = query.lower()

            # Scoring based on where query appears
            if lower_query in file.filename.lower():
                score += 100
            if file.description and lower_query in file.description.lower():
                score += 50
            if any(lower_query in t.lower() for t in file_tags):
                score += 10 # Query in tags
            score += file.content.lower().count(lower_query) # Count occurrences in content

            if score > 0:
                candidates.append((score, file))

        # Sort by score, descending
        candidates.sort(key=lambda x: x[0], reverse=True)

        results = []
        for score, file in candidates[:limit]:
            # Extract a snippet around the query, or return full content if short
            snippet = file.content
            if lower_query in file.content.lower():
                # Find first occurrence and get context
                idx = file.content.lower().find(lower_query)
                start = max(0, idx - 150)
                end = min(len(file.content), idx + len(lower_query) + 150)
                snippet = "..." + file.content[start:end] + "..." if len(file.content) > (end - start) else file.content
            
            results.append({
                "id": file.id,
                "filename": file.filename,
                "description": file.description,
                "tags": parse_json_field(file.tags),
                "content_snippet": snippet,
            })
            
            # Update last_trigger_inputs
            update_last_trigger_inputs(session, file.id, query)

        return results

# This is how the MCP Server is instantiated and run
if __name__ == "__main__":
    server = KnowledgeRetrievalMCP()
    server.run()
