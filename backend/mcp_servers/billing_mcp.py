from mcp.server.fastmcp import FastMCP
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastMCP
app = FastMCP("billing-mcp-server-v2")

@app.tool()
async def check_balance(account_id: str) -> str:
    """
    Checks the balance for a given account ID.
    """
    logger.info(f"Checking balance for {account_id}")
    # Mock response
    return f"Balance for account {account_id}: $1,250.00"

@app.tool()
async def get_invoice(invoice_id: str) -> str:
    """
    Retrieves details for a specific invoice.
    """
    logger.info(f"Fetching invoice {invoice_id}")
    return f"Invoice {invoice_id}: Status=Paid, Amount=$50.00, Date=2023-10-25"

if __name__ == "__main__":
    app.run()
