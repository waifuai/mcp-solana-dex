import asyncio
import json
import uuid
from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pytest
import pytest_asyncio
from solders.keypair import Keypair # For generating test owner keys

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# --- Helper Functions for MCP Interaction ---

async def send_mcp_request(
    writer: asyncio.StreamWriter,
    method: str,
    params: Dict[str, Any],
    request_id: Optional[str] = None,
) -> str:
    """Formats and sends a JSON-RPC request to the server via stdin."""
    if request_id is None:
        request_id = str(uuid.uuid4())
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "params": params,
        "id": request_id,
    }
    request_str = json.dumps(request) + "\n"
    print(f"\n[TEST SEND ->]: {request_str.strip()}") # Log sent request
    writer.write(request_str.encode('utf-8'))
    await writer.drain()
    return request_id

async def read_mcp_response(
    reader: asyncio.StreamReader,
    expected_id: str,
    timeout: float = 5.0 # seconds
) -> Dict[str, Any]:
    """Reads and parses a JSON-RPC response from the server via stdout."""
    response_str = ""
    try:
        while True:
            line_bytes = await asyncio.wait_for(reader.readline(), timeout=timeout)
            if not line_bytes: # EOF
                raise asyncio.TimeoutError("Server process closed connection unexpectedly.")
            line = line_bytes.decode('utf-8').strip()
            print(f"[TEST RECV <-]: {line}") # Log received line
            if line: # Ignore empty lines
                try:
                    response = json.loads(line)
                    if response.get("id") == expected_id:
                        return response
                    else:
                        # Log unexpected messages but keep waiting
                        print(f"[TEST WARN]: Received message with unexpected ID: {response.get('id')}")
                except json.JSONDecodeError:
                    print(f"[TEST WARN]: Received non-JSON line: {line}")
                    # Continue reading in case it's partial output or logging
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError(
            f"Timeout waiting for response with ID {expected_id}. Last partial line: '{response_str}'"
        )
    except Exception as e:
        print(f"[TEST ERROR]: Exception while reading response: {e}")
        raise

# --- Test Cases ---

async def test_create_order_success(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader],
    temp_order_book_path: Path
):
    """Tests successfully creating a new order."""
    _process, writer, reader = dex_server_process
    owner_kp = Keypair()
    owner_pubkey_str = str(owner_kp.pubkey())
    ico_id = "TEST_ICO_CREATE"
    amount = 1000
    price = 0.5

    params = {
        "ico_id": ico_id,
        "amount": amount,
        "price": price,
        "owner": owner_pubkey_str,
    }

    request_id = await send_mcp_request(writer, "create_order", params)
    response = await read_mcp_response(reader, request_id)

    assert "error" not in response, f"Server returned error: {response.get('error')}"
    assert "result" in response
    assert isinstance(response["result"], str)
    assert "created successfully" in response["result"]
    assert ico_id in response["result"]
    assert str(amount) in response["result"]
    assert str(price) in response["result"]

    # Verify the order was saved to the file
    assert temp_order_book_path.exists(), "Order book file was not created"
    with open(temp_order_book_path, 'r') as f:
        saved_data = json.load(f)

    assert ico_id in saved_data
    assert isinstance(saved_data[ico_id], list)
    assert len(saved_data[ico_id]) == 1
    saved_order = saved_data[ico_id][0]
    assert saved_order["ico_id"] == ico_id
    assert saved_order["amount"] == amount
    assert saved_order["price"] == price
    assert saved_order["owner"] == owner_pubkey_str
    assert "order_id" in saved_order

async def test_create_order_invalid_owner(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader]
):
    """Tests creating an order with an invalid owner pubkey format."""
    _process, writer, reader = dex_server_process
    invalid_owner = "this-is-not-a-valid-pubkey"
    ico_id = "TEST_ICO_INVALID"
    amount = 500
    price = 0.1

    params = {
        "ico_id": ico_id,
        "amount": amount,
        "price": price,

async def test_cancel_order_success(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader],
    temp_order_book_path: Path
):
    """Tests successfully cancelling an existing order."""
    _process, writer, reader = dex_server_process
    owner_kp = Keypair()
    owner_pubkey_str = str(owner_kp.pubkey())
    ico_id = "TEST_ICO_CANCEL"
    amount = 2000
    price = 0.25

    # 1. Create an order first
    create_params = {
        "ico_id": ico_id,
        "amount": amount,
        "price": price,
        "owner": owner_pubkey_str,
    }
    create_req_id = await send_mcp_request(writer, "create_order", create_params)
    create_response = await read_mcp_response(reader, create_req_id)
    assert "result" in create_response and "created successfully" in create_response["result"]

    # Extract the order_id from the saved file (simplest way for now)
    with open(temp_order_book_path, 'r') as f:
        saved_data = json.load(f)
    order_id = saved_data[ico_id][0]["order_id"]

    # 2. Cancel the order
    cancel_params = {
        "ico_id": ico_id,
        "order_id": order_id,
        "owner": owner_pubkey_str,
    }
    cancel_req_id = await send_mcp_request(writer, "cancel_order", cancel_params)
    cancel_response = await read_mcp_response(reader, cancel_req_id)

    assert "error" not in cancel_response
    assert "result" in cancel_response
    assert isinstance(cancel_response["result"], str)
    assert "cancelled successfully" in cancel_response["result"]
    assert order_id in cancel_response["result"]

    # 3. Verify the order is removed from the file
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_cancel = json.load(f)
    assert ico_id not in saved_data_after_cancel or not saved_data_after_cancel[ico_id]

async def test_cancel_order_not_found(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader]
):
    """Tests cancelling an order that does not exist."""
    _process, writer, reader = dex_server_process
    owner_kp = Keypair()
    owner_pubkey_str = str(owner_kp.pubkey())
    ico_id = "TEST_ICO_CANCEL_NF"
    non_existent_order_id = str(uuid.uuid4())

    params = {
        "ico_id": ico_id,
        "order_id": non_existent_order_id,
        "owner": owner_pubkey_str,
    }

    request_id = await send_mcp_request(writer, "cancel_order", params)
    response = await read_mcp_response(reader, request_id)

    assert "error" not in response
    assert "result" in response
    assert isinstance(response["result"], str)
    # Check for either 'no orders found for ICO' or 'order not found'
    assert (
        f"No orders found for ICO {ico_id}" in response["result"] or
        f"Order {non_existent_order_id} not found" in response["result"]
    )

async def test_cancel_order_wrong_owner(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader],
    temp_order_book_path: Path
):
    """Tests cancelling an order with the wrong owner public key."""
    _process, writer, reader = dex_server_process
    owner_kp = Keypair()
    owner_pubkey_str = str(owner_kp.pubkey())
    attacker_kp = Keypair()
    attacker_pubkey_str = str(attacker_kp.pubkey())
    ico_id = "TEST_ICO_CANCEL_WRONG"

    # 1. Create an order
    create_params = {"ico_id": ico_id, "amount": 100, "price": 1.0, "owner": owner_pubkey_str}
    create_req_id = await send_mcp_request(writer, "create_order", create_params)
    await read_mcp_response(reader, create_req_id) # Consume response
    with open(temp_order_book_path, 'r') as f:
        order_id = json.load(f)[ico_id][0]["order_id"]

    # 2. Attempt to cancel with wrong owner
    cancel_params = {
        "ico_id": ico_id,
        "order_id": order_id,
        "owner": attacker_pubkey_str, # Attacker tries to cancel
    }
    cancel_req_id = await send_mcp_request(writer, "cancel_order", cancel_params)
    cancel_response = await read_mcp_response(reader, cancel_req_id)

    assert "error" not in cancel_response
    assert "result" in cancel_response
    assert isinstance(cancel_response["result"], str)
    assert f"Error: You ({attacker_pubkey_str}) are not the owner" in cancel_response["result"]

    # 3. Verify order still exists
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_fail = json.load(f)
    assert ico_id in saved_data_after_fail
    assert len(saved_data_after_fail[ico_id]) == 1
    assert saved_data_after_fail[ico_id][0]["order_id"] == order_id

async def test_get_orders_success_and_sorting(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader],
    temp_order_book_path: Path
):
    """Tests retrieving orders for an ICO, verifying sorting by price."""
    _process, writer, reader = dex_server_process
    owner1_kp = Keypair()
    owner2_kp = Keypair()
    ico_id = "TEST_ICO_GET"

    # 1. Create orders with different prices (out of order)
    orders_to_create = [
        {"ico_id": ico_id, "amount": 100, "price": 0.5, "owner": str(owner1_kp.pubkey())},
        {"ico_id": ico_id, "amount": 200, "price": 0.3, "owner": str(owner2_kp.pubkey())},
        {"ico_id": ico_id, "amount": 150, "price": 0.7, "owner": str(owner1_kp.pubkey())},
        {"ico_id": "OTHER_ICO", "amount": 50, "price": 1.0, "owner": str(owner1_kp.pubkey())}, # Different ICO
    ]

    for params in orders_to_create:
        req_id = await send_mcp_request(writer, "create_order", params)
        await read_mcp_response(reader, req_id) # Consume response

    # 2. Get orders for the target ICO
    get_params = {"ico_id": ico_id}
    get_req_id = await send_mcp_request(writer, "get_orders", get_params)
    get_response = await read_mcp_response(reader, get_req_id)

    assert "error" not in get_response
    assert "result" in get_response
    result_data = json.loads(get_response["result"])

    assert result_data["ico_id"] == ico_id
    assert "orders" in result_data
    retrieved_orders = result_data["orders"]
    assert len(retrieved_orders) == 3 # Should only get orders for TEST_ICO_GET

    # 3. Verify sorting by price (ascending)
    assert retrieved_orders[0]["price"] == 0.3
    assert retrieved_orders[1]["price"] == 0.5
    assert retrieved_orders[2]["price"] == 0.7

    # Verify other details match
    assert retrieved_orders[0]["amount"] == 200
    assert retrieved_orders[1]["owner"] == str(owner1_kp.pubkey())

async def test_get_orders_limit(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader],
    temp_order_book_path: Path
):
    """Tests the limit parameter for get_orders."""
    _process, writer, reader = dex_server_process
    owner_kp = Keypair()
    ico_id = "TEST_ICO_LIMIT"

    # 1. Create multiple orders
    for i in range(5):
        params = {"ico_id": ico_id, "amount": 100 + i, "price": 0.1 * (i + 1), "owner": str(owner_kp.pubkey())}
        req_id = await send_mcp_request(writer, "create_order", params)
        await read_mcp_response(reader, req_id)

    # 2. Get orders with limit=2
    get_params = {"ico_id": ico_id, "limit": 2}
    get_req_id = await send_mcp_request(writer, "get_orders", get_params)
    get_response = await read_mcp_response(reader, get_req_id)

    assert "result" in get_response
    result_data = json.loads(get_response["result"])
    assert len(result_data["orders"]) == 2

    # Verify sorting is still applied before limiting
    assert result_data["orders"][0]["price"] == 0.1
    assert result_data["orders"][1]["price"] == 0.2

async def test_get_orders_no_orders(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader]
):
    """Tests retrieving orders for an ICO ID that has no orders."""
    _process, writer, reader = dex_server_process
    ico_id_no_orders = "TEST_ICO_NO_ORDERS"

async def test_execute_order_full_success(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader],
    temp_order_book_path: Path
):
    """Tests successfully executing an entire order."""
    _process, writer, reader = dex_server_process
    seller_kp = Keypair()
    buyer_kp = Keypair()
    seller_pubkey_str = str(seller_kp.pubkey())
    buyer_pubkey_str = str(buyer_kp.pubkey())
    ico_id = "TEST_ICO_EXEC_FULL"
    amount = 5000 # Base units
    price = 0.1 # SOL per token
    token_mint = str(Keypair().pubkey()) # Dummy mint
    token_decimals = 6 # Dummy decimals

    # 1. Create the order
    create_params = {"ico_id": ico_id, "amount": amount, "price": price, "owner": seller_pubkey_str}
    create_req_id = await send_mcp_request(writer, "create_order", create_params)
    await read_mcp_response(reader, create_req_id)
    with open(temp_order_book_path, 'r') as f:
        order_id = json.load(f)[ico_id][0]["order_id"]

    # 2. Execute the full order
    execute_params = {
        "ico_id": ico_id,
        "order_id": order_id,
        "buyer": buyer_pubkey_str,
        "amount": amount, # Buy the full amount
        "seller_token_transfer_tx": "dummy_sig_token_transfer",
        "buyer_sol_payment_tx": "dummy_sig_sol_payment",
        "token_mint_address": token_mint,
        "token_decimals": token_decimals,
    }
    exec_req_id = await send_mcp_request(writer, "execute_order", execute_params)
    exec_response = await read_mcp_response(reader, exec_req_id)

    assert "error" not in exec_response
    assert "result" in exec_response
    assert "Successfully executed order" in exec_response["result"]
    assert f"Bought {amount / (10**token_decimals)} tokens" in exec_response["result"]
    assert order_id in exec_response["result"]

    # 3. Verify order is removed from the file
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_exec = json.load(f)
    assert ico_id not in saved_data_after_exec or not saved_data_after_exec[ico_id]

async def test_execute_order_partial_success(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader],
    temp_order_book_path: Path
):
    """Tests successfully executing part of an order."""
    _process, writer, reader = dex_server_process
    seller_kp = Keypair()
    buyer_kp = Keypair()
    seller_pubkey_str = str(seller_kp.pubkey())
    buyer_pubkey_str = str(buyer_kp.pubkey())
    ico_id = "TEST_ICO_EXEC_PARTIAL"
    initial_amount = 10000
    buy_amount = 4000
    remaining_amount = initial_amount - buy_amount
    price = 0.05
    token_mint = str(Keypair().pubkey())
    token_decimals = 9

    # 1. Create the order
    create_params = {"ico_id": ico_id, "amount": initial_amount, "price": price, "owner": seller_pubkey_str}
    create_req_id = await send_mcp_request(writer, "create_order", create_params)
    await read_mcp_response(reader, create_req_id)
    with open(temp_order_book_path, 'r') as f:
        order_id = json.load(f)[ico_id][0]["order_id"]

    # 2. Execute part of the order
    execute_params = {
        "ico_id": ico_id,
        "order_id": order_id,
        "buyer": buyer_pubkey_str,
        "amount": buy_amount,
        "seller_token_transfer_tx": "dummy_sig_token_transfer_partial",
        "buyer_sol_payment_tx": "dummy_sig_sol_payment_partial",
        "token_mint_address": token_mint,
        "token_decimals": token_decimals,
    }
    exec_req_id = await send_mcp_request(writer, "execute_order", execute_params)
    exec_response = await read_mcp_response(reader, exec_req_id)

    assert "error" not in exec_response
    assert "result" in exec_response
    assert "Successfully executed order" in exec_response["result"]
    assert f"Bought {buy_amount / (10**token_decimals)} tokens" in exec_response["result"]

    # 3. Verify order amount is reduced in the file
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_exec = json.load(f)
    assert ico_id in saved_data_after_exec
    assert len(saved_data_after_exec[ico_id]) == 1
    updated_order = saved_data_after_exec[ico_id][0]
    assert updated_order["order_id"] == order_id
    assert updated_order["amount"] == remaining_amount
    assert updated_order["price"] == price # Price shouldn't change
    assert updated_order["owner"] == seller_pubkey_str # Owner shouldn't change

async def test_execute_order_insufficient_amount(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader],
    temp_order_book_path: Path
):
    """Tests attempting to buy more tokens than available in an order."""
    _process, writer, reader = dex_server_process
    seller_kp = Keypair()
    buyer_kp = Keypair()
    seller_pubkey_str = str(seller_kp.pubkey())
    buyer_pubkey_str = str(buyer_kp.pubkey())
    ico_id = "TEST_ICO_EXEC_INSUFFICIENT"
    available_amount = 100
    buy_amount = 101 # Try to buy more than available
    price = 1.0
    token_mint = str(Keypair().pubkey())
    token_decimals = 2

    # 1. Create the order
    create_params = {"ico_id": ico_id, "amount": available_amount, "price": price, "owner": seller_pubkey_str}
    create_req_id = await send_mcp_request(writer, "create_order", create_params)
    await read_mcp_response(reader, create_req_id)
    with open(temp_order_book_path, 'r') as f:
        order_id = json.load(f)[ico_id][0]["order_id"]

    # 2. Attempt to execute with excessive amount
    execute_params = {
        "ico_id": ico_id,
        "order_id": order_id,
        "buyer": buyer_pubkey_str,
        "amount": buy_amount,
        "seller_token_transfer_tx": "dummy_sig_token_transfer_insuff",
        "buyer_sol_payment_tx": "dummy_sig_sol_payment_insuff",
        "token_mint_address": token_mint,
        "token_decimals": token_decimals,
    }
    exec_req_id = await send_mcp_request(writer, "execute_order", execute_params)
    exec_response = await read_mcp_response(reader, exec_req_id)

    assert "error" not in exec_response
    assert "result" in exec_response
    assert isinstance(exec_response["result"], str)
    assert f"Error: Not enough tokens available in order {order_id}" in exec_response["result"]
    assert f"Available: {available_amount}" in exec_response["result"]
    assert f"Requested: {buy_amount}" in exec_response["result"]

    # 3. Verify order is unchanged
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_fail = json.load(f)
    assert saved_data_after_fail[ico_id][0]["amount"] == available_amount

async def test_execute_order_not_found(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader]
):
    """Tests attempting to execute an order that does not exist."""
    _process, writer, reader = dex_server_process
    buyer_kp = Keypair()
    buyer_pubkey_str = str(buyer_kp.pubkey())
    ico_id = "TEST_ICO_EXEC_NF"
    non_existent_order_id = str(uuid.uuid4())

    execute_params = {
        "ico_id": ico_id,
        "order_id": non_existent_order_id,
        "buyer": buyer_pubkey_str,
        "amount": 100,
        "seller_token_transfer_tx": "dummy_sig_token_transfer_nf",
        "buyer_sol_payment_tx": "dummy_sig_sol_payment_nf",
        "token_mint_address": str(Keypair().pubkey()),
        "token_decimals": 6,
    }
    exec_req_id = await send_mcp_request(writer, "execute_order", execute_params)
    exec_response = await read_mcp_response(reader, exec_req_id)

    assert "error" not in exec_response
    assert "result" in exec_response
    assert isinstance(exec_response["result"], str)
    assert (
        f"No orders found for ICO {ico_id}" in exec_response["result"] or
        f"Order {non_existent_order_id} not found" in exec_response["result"]
    )

async def test_execute_order_invalid_buyer_key(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader]
):
    """Tests execute_order with an invalid buyer public key format."""
    _process, writer, reader = dex_server_process
    # Don't even need to create an order for this check
    execute_params = {
        "ico_id": "TEST_ICO_EXEC_INV_BUYER",
        "order_id": str(uuid.uuid4()),
        "buyer": "invalid-buyer-key",
        "amount": 1,
        "seller_token_transfer_tx": "dummy",
        "buyer_sol_payment_tx": "dummy",
        "token_mint_address": str(Keypair().pubkey()),
        "token_decimals": 0,
    }
    exec_req_id = await send_mcp_request(writer, "execute_order", execute_params)
    exec_response = await read_mcp_response(reader, exec_req_id)

    assert "error" not in exec_response
    assert "result" in exec_response
    assert isinstance(exec_response["result"], str)
    assert "Invalid public key or mint address format" in exec_response["result"]


    get_params = {"ico_id": ico_id_no_orders}
    get_req_id = await send_mcp_request(writer, "get_orders", get_params)
    get_response = await read_mcp_response(reader, get_req_id)

    assert "error" not in get_response
    assert "result" in get_response
    result_data = json.loads(get_response["result"])

    assert result_data["ico_id"] == ico_id_no_orders
    assert "orders" in result_data
    assert len(result_data["orders"]) == 0


async def test_cancel_order_invalid_owner_format(
    dex_server_process: Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader]
):
    """Tests cancelling an order with an invalid owner pubkey format."""
    _process, writer, reader = dex_server_process
    invalid_owner = "not-a-key"
    ico_id = "TEST_ICO_CANCEL_INV_OWNER"
    order_id = str(uuid.uuid4()) # Doesn't matter if it exists

    params = {
        "ico_id": ico_id,
        "order_id": order_id,
        "owner": invalid_owner,
    }

    request_id = await send_mcp_request(writer, "cancel_order", params)
    response = await read_mcp_response(reader, request_id)

    assert "error" not in response
    assert "result" in response
    assert isinstance(response["result"], str)
    assert "Invalid owner public key format" in response["result"]

        "owner": invalid_owner,
    }

    request_id = await send_mcp_request(writer, "create_order", params)
    response = await read_mcp_response(reader, request_id)

    # Expecting a result containing an error message from the tool itself
    assert "error" not in response # JSON-RPC call itself succeeded
    assert "result" in response
    assert isinstance(response["result"], str)
    assert "Invalid owner public key format" in response["result"]


# --- Test Cases (To be added next) ---

# Example structure:
# async def test_example(dex_server_process, temp_order_book_path):
#     process, writer, reader = dex_server_process
#     # ... use helpers to send/receive ...
#     # ... assert results ...
#     # ... check temp_order_book_path content ...