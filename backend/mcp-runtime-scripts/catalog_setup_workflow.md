---
description: Build and Register Product Catalog MCP + Skill
---

# Product Catalog Integration Workflow

This workflow sets up the Product Catalog MCP server and its associated Skill.md documentation.

## 1. Verify MCP Implementation
Check `backend/mcp-runtime-scripts/catalog_mcp.py`. It should provide tools:
- `list_categories()`
- `search_products(query, category_id)`
- `get_product_details(product_id)`

## 2. Create Skill Documentation
Create `backend/mcp-runtime-scripts/catalog_skill.md` with instructions for the AI Agent.

## 3. Register MCP Server
Run the registration script to add the MCP server to the database and link it to the default agent.

## 4. Test
Use the AI Agent Tester to ask about products.
