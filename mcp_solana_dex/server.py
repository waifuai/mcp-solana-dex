import asyncio
import json
import os
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import httpx
from pydantic import BaseModel, Field
from solders.hash import Hash as Blockhash
from solders.instruction import Instruction
from solders.keypair import Keypair
from solders.message import Message
from solders.pubkey import Pubkey
from solders.rpc.config import RpcTransactionConfig
from solders.rpc.responses import SendTransactionResp, SimulateTransactionResp, GetBalanceResp, GetTokenAccountBalanceResp # Added RPC response types
from solana.rpc.core import RPCException # Use general RPCException for error handling
from solana.rpc.async_api import AsyncClient # Corrected import path for AsyncClient
from solders.signature import Signature
from solders.transaction import Transaction
from spl.token.constants import TOKEN_PROGRAM_ID
from spl.token.instructions import transfer_checked, TransferCheckedParams, get_associated_token_address

from mcp.server.fastmcp import Context, FastMCP
from mcp.server.fastmcp.utilities.logging import get_logger
from dotenv import load_dotenv

# Load environment variables from .env file in this directory
dotenv_path = Path(__file__).parent.parent / '.env'
load_dotenv(dotenv_path=dotenv_path)

RPC_ENDPOINT = os.getenv("RPC_ENDPOINT", "http://localhost:8899")
ORDER_BOOK_FILE = Path(__file__).parent.parent / os.getenv("ORDER_BOOK_FILE", "data/order_book.json")
LAMPORTS_PER_SOL = 1_000_000_000
# Optional: Load token mint if needed, otherwise it might be passed in requests
# TOKEN_MINT_ADDRESS = Pubkey.from_string(os.getenv("TOKEN_MINT_ADDRESS"))

logger = get_logger(__name__)

# --- Data Structures ---

class Order(BaseModel):
    order_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    ico_id: str # Keep track of which ICO the token belongs to
    amount: int # In base units
    price: float # Price per token in SOL
    owner: str # Pubkey string
    is_sell_order: bool = True # True for sell, False for buy (if buy orders are added later)

# --- Persistence ---

# In-memory cache, loaded from/saved to file
order_book: Dict[str, List[Order]] = {} # {ico_id: [Order, ...]}

def load_order_book():
    """Loads the order book from the JSON file."""
    global order_book
    try:
        if ORDER_BOOK_FILE.exists():
            with open(ORDER_BOOK_FILE, 'r') as f:
                data = json.load(f)
                # Validate data structure if necessary
                order_book = {k: [Order(**o) for o in v] for k, v in data.items()}
                logger.info(f"Loaded order book from {ORDER_BOOK_FILE}")
        else:
            logger.info(f"Order book file {ORDER_BOOK_FILE} not found, starting fresh.")
            order_book = {}
    except (json.JSONDecodeError, IOError, TypeError) as e:
        logger.error(f"Error loading order book from {ORDER_BOOK_FILE}: {e}. Starting fresh.")
        order_book = {} # Start with an empty book on error

def save_order_book():
    """Saves the current order book to the JSON file."""
    print(f"--- ENTERING save_order_book for {ORDER_BOOK_FILE} ---") # Add simple print
    try:
        logger.info(f"Attempting to save order book to {ORDER_BOOK_FILE}...")
 # Use INFO for visibility
        logger.debug(f"ORDER_BOOK_FILE type: {type(ORDER_BOOK_FILE)}, value: {ORDER_BOOK_FILE}")
        logger.debug(f"Parent directory: {ORDER_BOOK_FILE.parent}")
        ORDER_BOOK_FILE.parent.mkdir(parents=True, exist_ok=True) # Ensure data directory exists
        logger.debug(f"Parent directory exists after mkdir: {ORDER_BOOK_FILE.parent.exists()}")
        # Convert Pubkey objects back to strings if they exist in the model
        serializable_book = {
            k: [o.model_dump() for o in v]
            for k, v in order_book.items()
        }
        with open(ORDER_BOOK_FILE, 'w') as f:
            logger.debug("Opened file for writing.")
            json.dump(serializable_book, f, indent=4)
            logger.debug("Finished json.dump.")
        logger.info(f"Successfully wrote to {ORDER_BOOK_FILE}") # Use INFO
        logger.debug(f"Checking existence immediately after write: {ORDER_BOOK_FILE.exists()}")
    except IOError as e:
        logger.exception(f"IOError saving order book to {ORDER_BOOK_FILE}: {e}")
 # Use exception for full traceback
        print(f"!!! IOError IN save_order_book !!!: {e}")
    except Exception as e:
        logger.exception(f"Unexpected error saving order book: {e}") # Catch any other errors
        print(f"!!! EXCEPTION IN save_order_book !!!: {e}") # Also print

# --- Server Setup ---
mcp = FastMCP(name="Solana DEX Server")

# Load the order book immediately when the server module is loaded
load_order_book()

# --- Helper Functions ---
# (Add any necessary helpers, e.g., for Solana interactions if not done client-side)

# --- MCP Tools ---

@mcp.tool()
async def create_order(
    context: Context,
    ico_id: str = Field(..., description="The ICO ID for the token being traded."),
    amount: int = Field(..., description="The amount of tokens to sell (in base units)."),
    price: float = Field(..., description="The price per token in SOL."),
    owner: str = Field(..., description="The public key string of the order owner."),
    # Add token_mint_address if not globally configured or derivable
    # token_mint_address: str = Field(..., description="The mint address of the token."),
) -> str:
    """Creates a new sell order in the DEX."""
    logger.info(f"Received create_order request for ico_id={ico_id}, amount={amount}, price={price}, owner={owner}")
    # TODO: Add validation (e.g., does owner have sufficient tokens? - requires Solana call)
    try:
        owner_pubkey = Pubkey.from_string(owner) # Validate pubkey format
        logger.debug(f"Validated owner pubkey: {owner_pubkey}")
        order = Order(ico_id=ico_id, amount=amount, price=price, owner=owner)
        logger.debug(f"Created Order object: {order.order_id}")

        if ico_id not in order_book:
            order_book[ico_id] = []
            logger.debug(f"Initialized order book for new ico_id: {ico_id}")
        order_book[ico_id].append(order)
        logger.debug(f"Appended order {order.order_id} to book for {ico_id}")
        logger.info("Calling save_order_book() from create_order...") # Add log
        save_order_book() # Save after modification
        logger.info(f"Created order {order.order_id} for {amount} tokens of {ico_id} by {owner}")
        return f"Order {order.order_id} created successfully for {amount} tokens of {ico_id} at price {price} SOL."
    except ValueError:
        return "Invalid owner public key format."
    except Exception as e:
        logger.exception(f"Error creating order: {e}")
        return f"An error occurred while creating the order: {e}"

@mcp.tool()
async def cancel_order(
    context: Context,
    ico_id: str = Field(..., description="The ICO ID for the token being traded."),
    order_id: str = Field(..., description="The ID of the order to cancel."),
    owner: str = Field(..., description="The public key string of the order owner."),
) -> str:
    """Cancels an existing order in the DEX."""
    try:
        owner_pubkey = Pubkey.from_string(owner) # Validate pubkey format
        if ico_id not in order_book:
            return f"No orders found for ICO {ico_id}."

        orders = order_book[ico_id]
        order_to_cancel = None
        for i, order in enumerate(orders):
            if order.order_id == order_id:
                if order.owner != owner:
                    return f"Error: You ({owner}) are not the owner of order {order_id}."
                order_to_cancel = order
                del orders[i]
                break

        if order_to_cancel:
            logger.info("Calling save_order_book() from cancel_order...") # Add log
            save_order_book() # Save after modification
            logger.info(f"Cancelled order {order_id} for ICO {ico_id} by {owner}")
            return f"Order {order_id} cancelled successfully."
        else:
            return f"Error: Order {order_id} not found for ICO {ico_id}."
    except ValueError:
        return "Invalid owner public key format."
    except Exception as e:
        logger.exception(f"Error cancelling order: {e}")
        return f"An error occurred while cancelling the order: {e}"

@mcp.tool()
async def execute_order(
    context: Context,
    ico_id: str = Field(..., description="The ICO ID for the token being traded."),
    order_id: str = Field(..., description="The ID of the order to execute (buy from)."),
    buyer: str = Field(..., description="The public key string of the buyer."),
    amount: int = Field(..., description="The amount of tokens to buy (in base units)."),
    # Removed pre-signed transaction signature parameters
    token_mint_address: str = Field(..., description="The mint address of the token being traded."),
    token_decimals: int = Field(..., description="The decimals of the token being traded."),
) -> str:
    """
    Performs pre-condition checks for executing a sell order and updates the internal
    order book if checks pass. Does NOT execute the on-chain transaction.
    Checks: Buyer SOL balance, Seller token balance.
    Clients must construct and submit the actual atomic swap transaction separately
    after receiving a success response from this tool.
    """
    logger.info(f"Received execute_order pre-check request for order {order_id}, ico_id={ico_id}, buyer={buyer}, amount={amount}")
    try:
        buyer_pubkey = Pubkey.from_string(buyer)
        mint_pubkey = Pubkey.from_string(token_mint_address)

        if ico_id not in order_book:
            return f"No orders found for ICO {ico_id}."

        orders = order_book[ico_id]
        order_to_execute = None
        order_index = -1
        for i, order in enumerate(orders):
            if order.order_id == order_id:
                order_to_execute = order
                order_index = i
                break

        if not order_to_execute:
            return f"Error: Order {order_id} not found for ICO {ico_id}."

        if amount <= 0:
            return "Error: Amount to buy must be positive."
        if amount > order_to_execute.amount:
            return f"Error: Not enough tokens available in order {order_id}. Available: {order_to_execute.amount}, Requested: {amount}."

        seller_pubkey = Pubkey.from_string(order_to_execute.owner)
        required_sol_float = (amount / (10**token_decimals)) * order_to_execute.price
        required_sol_lamports = int(required_sol_float * LAMPORTS_PER_SOL)

        # --- Pre-Condition Checks ---
        async with AsyncClient(RPC_ENDPOINT) as client:
            logger.debug(f"Connecting to RPC: {RPC_ENDPOINT}")
            is_connected = await client.is_connected()
            if not is_connected:
                logger.error(f"Failed to connect to RPC endpoint: {RPC_ENDPOINT}")
                return "Error: Could not connect to Solana RPC to verify balances."
            logger.debug("RPC Connection successful.")

            # 1. Check Buyer SOL Balance
            try:
                logger.debug(f"Checking buyer SOL balance for {buyer_pubkey}...")
                balance_resp: GetBalanceResp = await client.get_balance(buyer_pubkey)
                buyer_lamports = balance_resp.value
                logger.debug(f"Buyer ({buyer_pubkey}) balance: {buyer_lamports} lamports. Required: {required_sol_lamports}")
                if buyer_lamports < required_sol_lamports:
                    return (f"Error: Insufficient SOL balance for buyer {buyer}. "
                            f"Required: {required_sol_lamports} lamports ({required_sol_float:.9f} SOL), "
                            f"Available: {buyer_lamports} lamports.")
            except Exception as e:
                logger.exception(f"Error checking buyer SOL balance: {e}")
                return f"Error checking buyer SOL balance: {e}"

            # 2. Check Seller Token Balance
            try:
                seller_ata_pubkey = get_associated_token_address(seller_pubkey, mint_pubkey)
                logger.debug(f"Checking seller token balance for ATA {seller_ata_pubkey} (Owner: {seller_pubkey}, Mint: {mint_pubkey})...")
                try:
                    token_resp: GetTokenAccountBalanceResp = await client.get_token_account_balance(seller_ata_pubkey)
                    seller_token_balance = int(token_resp.value.amount) # Amount is string, convert to int
                    logger.debug(f"Seller ({seller_pubkey}) token balance: {seller_token_balance} base units. Required: {amount}")
                except RPCException as rpc_err: # Catch general RPCException
                    # Check if the error indicates the account doesn't exist
                    # This is a common way RPC indicates zero balance for non-existent ATAs
                    # Error structure might vary slightly, adjust if needed based on actual RPC responses
                    # Check the exception arguments for specific error messages/codes if available
                    err_str = str(rpc_err)
                    if "Account not found" in err_str or "Invalid param: could not find account" in err_str:
                         logger.warning(f"Seller's ATA {seller_ata_pubkey} not found. Assuming 0 balance.")
                         seller_token_balance = 0
                    else:
                         raise # Re-raise other RPC errors
                except Exception as e:
                     # Catch potential errors during parsing or unexpected issues
                     logger.exception(f"Unexpected error fetching seller token balance: {e}")
                     return f"Unexpected error fetching seller token balance: {e}"


                if seller_token_balance < amount:
                    return (f"Error: Insufficient token balance for seller {seller_pubkey}. "
                            f"Required: {amount} base units, Available: {seller_token_balance} base units.")
            except Exception as e:
                logger.exception(f"Error checking seller token balance: {e}")
                return f"Error checking seller token balance: {e}"

        logger.info("Pre-condition checks passed (Buyer SOL, Seller Tokens).")

        # --- Update Order Book ---
        order_to_execute.amount -= amount
        if order_to_execute.amount == 0:
            del orders[order_index]
            logger.info(f"Order {order_id} fully executed and removed.")
        else:
            logger.info(f"Order {order_id} partially executed. Remaining amount: {order_to_execute.amount}")

        logger.info("Calling save_order_book() from execute_order...") # Add log
        save_order_book() # Save after modification

        # Pre-checks passed, update internal state
        logger.info("Calling save_order_book() from execute_order after successful pre-checks...")
        save_order_book() # Save after modification

        return (f"Pre-conditions met for order {order_id}. "
                f"Buyer has sufficient SOL, Seller has sufficient tokens. "
                f"Order book updated. Client should now submit the atomic swap transaction.")

    except ValueError as e:
        return f"Invalid public key or mint address format: {e}"
    except Exception as e:
        logger.exception(f"Error executing order: {e}")
        return f"An error occurred while executing the order: {e}"


@mcp.tool()
async def get_orders(
    context: Context,
    ico_id: str = Field(..., description="The ICO ID to fetch orders for."),
        # Keep the Field definition for MCP schema generation, but handle default in code
    limit: Optional[int] = Field(None, description="Maximum number of orders to return (default 100)."),
) -> str:
    """Retrieves the current sell orders for a given ICO ID."""
    # Explicitly set default if None is passed or handle potential FieldInfo object
    # Check for None explicitly, as Field(None,...) might still pass FieldInfo
    effective_limit = 100 if limit is None else limit
    # Add an extra check in case FieldInfo object is passed despite default=None
    if not isinstance(effective_limit, int):
        logger.warning(f"Limit parameter was not None or int, defaulting to 100. Type: {type(limit)}")
        effective_limit = 100

    logger.debug(f"get_orders called for {ico_id} with limit={limit}, effective_limit={effective_limit}")

    if ico_id not in order_book:
        logger.debug(f"No orders found for ico_id {ico_id}")
        return json.dumps({"ico_id": ico_id, "orders": []})

    # Use the effective_limit which is guaranteed to be an int
    orders_to_return = order_book[ico_id][:effective_limit]
    # Sort by price (ascending) for a typical order book view
    orders_to_return.sort(key=lambda o: o.price)
    logger.debug(f"Returning {len(orders_to_return)} orders for {ico_id}")

    return json.dumps(
        {"ico_id": ico_id, "orders": [o.model_dump() for o in orders_to_return]},
        indent=2
    )


if __name__ == "__main__":
    print(f"Attempting to load orders from: {ORDER_BOOK_FILE}")
    print(f"Using RPC Endpoint: {RPC_ENDPOINT}")
    # Example: poetry run python ./mcp_solana_dex/server.py
    asyncio.run(mcp.run(transport="stdio"))