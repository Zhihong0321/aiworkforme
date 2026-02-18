import os
import json
import logging
import sys
from typing import List, Dict, Optional, Any
from mcp.server.fastmcp import FastMCP
from sqlalchemy import create_engine, text

# Configure logging to stderr for MCP communication
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger("catalog_mcp")

# Database Configuration
# Default to sqlite for local dev if not provided, but use the env var in prod/docker
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///app_test.db")

engine = create_engine(DATABASE_URL)

# Initialize FastMCP
app = FastMCP("product_catalog")

@app.tool()
async def list_categories() -> str:
    """
    Lists all available product categories in the store. 
    Use this to see what types of products are available.
    """
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT id, name, parent_id FROM et_product_categories"))
            categories = [dict(row._mapping) for row in result]
            if not categories:
                return "The product catalog is currently empty (no categories found)."
            return json.dumps(categories, indent=2)
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        return f"Error: {str(e)}"

@app.tool()
async def search_products(query: str, category_id: Optional[int] = None) -> str:
    """
    Searches for products by keyword in title or description.
    You can optionally filter by category_id.
    """
    try:
        with engine.connect() as conn:
            # Note: SQLite uses LIKE with % for case-insensitive usually, 
            # while Postgres might need ILIKE. We'll use a generic approach or check.
            like_op = "ILIKE" if "postgresql" in DATABASE_URL else "LIKE"
            
            sql = f"SELECT id, title, price, description FROM et_products WHERE (title {like_op} :q OR description {like_op} :q)"
            params = {"q": f"%{query}%"}
            if category_id:
                sql += " AND category_id = :cat"
                params["cat"] = category_id
            
            sql += " LIMIT 5"
            result = conn.execute(text(sql), params)
            products = [dict(row._mapping) for row in result]
            
            if not products:
                return f"No products found matching '{query}'."
            
            # Format nicely for the LLM
            output = "Found the following products:\n"
            for p in products:
                price_str = f"${p['price']}" if p['price'] is not None else "N/A"
                output += f"- [{p['id']}] {p['title']} - {price_str}\n  Description: {p['description']}\n"
            
            return output
    except Exception as e:
        logger.error(f"Error searching products: {e}")
        return f"Error: {str(e)}"

@app.tool()
async def get_product_details(product_id: int) -> str:
    """
    Retrieves full details for a specific product by its ID, including specs, images, and attachments.
    Use this when a user asks for more information about a specific item.
    """
    try:
        with engine.connect() as conn:
            sql = "SELECT * FROM et_products WHERE id = :id"
            result = conn.execute(text(sql), {"id": product_id}).first()
            
            if not result:
                return "Product not found."
            
            data = dict(result._mapping)
            # Remove internal fields
            data.pop("tenant_id", None)
            
            # Handle JSON fields
            if "details" in data and isinstance(data["details"], str):
                try:
                    data["details"] = json.loads(data["details"])
                except:
                    pass
            
            # Format as a detailed block for the LLM
            details_str = json.dumps(data.get("details", {}), indent=2)
            output = f"Product Details for '{data['title']}' (ID: {data['id']}):\n"
            output += f"- Price: ${data.get('price', 'N/A')}\n"
            output += f"- Image: {data.get('image_url', 'No image')}\n"
            output += f"- User Manual/Attachment: {data.get('attachment_url', 'No attachment')}\n"
            output += f"- Description: {data.get('description', 'N/A')}\n"
            if details_str != "{}":
                output += f"- Specs/Details: {details_str}\n"
            
            return output
    except Exception as e:
        logger.error(f"Error getting product details: {e}")
        return f"Error: {str(e)}"

if __name__ == "__main__":
    app.run()
