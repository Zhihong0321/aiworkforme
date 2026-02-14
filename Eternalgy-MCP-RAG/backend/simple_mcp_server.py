import asyncio
import logging
import sys
from mcp.server.fastmcp import FastMCP

# Configure logging to stderr
logging.basicConfig(level=logging.INFO, stream=sys.stderr)
logger = logging.getLogger(__name__)

# Initialize FastMCP
app = FastMCP("simple_mcp")

@app.tool()
async def echo_tool(message: str) -> str:
    """
    Echoes the input message back.
    """
    logger.info(f"Received request to echo: {message}")
    return f"Echo: {message}"

@app.tool()
async def add_numbers(a: int, b: int) -> str:
    """
    Adds two numbers together.
    """
    logger.info(f"Received request to add: {a} + {b}")
    return f"Sum: {a + b}"

if __name__ == "__main__":
    logger.info("Starting FastMCP simple_mcp_server")
    app.run()
