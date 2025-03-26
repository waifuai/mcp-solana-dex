# MCP Solana DEX Server

This directory contains a a simple Decentralized Exchange (DEX) MCP server.

## Purpose

This server provides basic DEX functionalities for tokens associated with ICOs managed by the main server:

*   Creating sell orders.
*   Cancelling sell orders.
*   Executing sell orders (buying from existing orders).
*   Retrieving the current order book for an ICO.

## Features

*   **MCP Tools:** Exposes DEX functions as MCP tools (`create_order`, `cancel_order`, `execute_order`, `get_orders`).
*   **File-Based Persistence:** Stores the order book in a JSON file (`data/order_book.json` by default).
*   **ICO Association:** Orders are associated with specific `ico_id`s.

**Disclaimer:** This is a simplified example. The `execute_order` tool uses a non-atomic, potentially unsafe model requiring pre-signed transactions. **This is NOT suitable for production.** A real DEX requires atomic swaps for secure execution.

## Configuration (`./.env`)

Create a `.env` file in this directory (`./`) with the following:

```dotenv
# Configuration for MCP Solana DEX Sub-project

# Solana RPC Endpoint (use the same as the main project or specify a different one)
RPC_ENDPOINT="http://localhost:8899"

# Path to the order book data file (relative to this directory)
ORDER_BOOK_FILE="data/order_book.json"

# Optional: Define the token mint address if needed globally
# TOKEN_MINT_ADDRESS="TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
```

## Usage

This server is intended to be run as a separate process from the main ICO server.

1.  **Ensure Dependencies:** Make sure dependencies are installed (likely managed by the parent project's `poetry install`).
2.  **Navigate to Parent Directory:** Open your terminal in the main project root.
3.  **Start the DEX Server:**

    ```bash
    poetry run python mcp_solana_dex/server.py
    ```

4.  **Interact:** Use an MCP client connected to the standard input/output of this process.

## MCP Tools

*   **`create_order`:** Creates a new sell order.
    *   `ico_id`: (String) The ID of the ICO for the token.
    *   `amount`: (Integer) Amount of tokens to sell (base units).
    *   `price`: (Float) Price per token in SOL.
    *   `owner`: (String) Public key of the seller.
*   **`cancel_order`:** Cancels an existing order.
    *   `ico_id`: (String) The ID of the ICO.
    *   `order_id`: (String) The unique ID of the order to cancel.
    *   `owner`: (String) Public key of the seller (must match order).
*   **`execute_order`:** Executes a sell order (buyer buys from seller).
    *   `ico_id`: (String) The ID of the ICO.
    *   `order_id`: (String) The ID of the order to buy from.
    *   `buyer`: (String) Public key of the buyer.
    *   `amount`: (Integer) Amount of tokens to buy (base units).
    *   `seller_token_transfer_tx`: (String) Signature of the pre-signed tx: seller tokens -> buyer.
    *   `buyer_sol_payment_tx`: (String) Signature of the pre-signed tx: buyer SOL -> seller.
    *   `token_mint_address`: (String) Mint address of the token.
    *   `token_decimals`: (Integer) Decimals of the token.
*   **`get_orders`:** Retrieves the current sell orders for an ICO.
    *   `ico_id`: (String) The ID of the ICO.
    *   `limit`: (Integer, optional) Max orders to return (default 100).

## Testing

This project uses `pytest` for integration testing. The tests run the server as a subprocess and interact with it via its standard input/output, simulating an MCP client.

1.  **Install Development Dependencies:**
    Make sure you have the main dependencies installed, then install the development dependencies which include `pytest` and `pytest-asyncio`:

    ```bash
    # Navigate to the project root directory (where pyproject.toml is)
    poetry install --with dev
    ```

2.  **Run Tests:**
    Execute `pytest` from the project root directory:

    ```bash
    poetry run pytest
    ```

    Pytest will automatically discover and run the tests located in the `tests/` directory.


## Future Considerations

*   **Atomic Swaps:** Implement secure, atomic order execution using Solana programs or established protocols.
*   **Database Persistence:** Replace file storage with a database (e.g., SQLite, PostgreSQL) for better scalability and reliability.
*   **Buy Orders:** Add support for creating and matching buy orders.
*   **Error Handling:** Improve validation and error handling.
*   **Testing:** Add comprehensive unit and integration tests.