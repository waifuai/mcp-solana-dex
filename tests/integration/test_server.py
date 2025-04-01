import asyncio
import json
import uuid
import types # For type hinting the module fixture
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock # For mock context type hint

import pytest
import pytest_asyncio
from solders.keypair import Keypair # For generating test owner keys

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# --- Helper Functions for MCP Interaction (REMOVED) ---
# No longer needed as we call functions directly

# --- Test Cases ---

async def test_create_order_success(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path
):
    """Tests successfully creating a new order."""
    server = patched_server_module # Get the reloaded server module
    owner_kp = Keypair()
    owner_pubkey_str = str(owner_kp.pubkey())
    ico_id = "TEST_ICO_CREATE"
    amount = 1000
    price = 0.5

    # Call the tool function directly
    result = await server.create_order(
        context=mock_context,
        ico_id=ico_id,
        amount=amount,
        price=price,
        owner=owner_pubkey_str,
    )

    # Assert the return value
    assert isinstance(result, str)
    assert "created successfully" in result
    assert ico_id in result
    assert str(amount) in result
    assert str(price) in result
    order_id_from_result = result.split(" ")[1] # Extract order_id (assuming format "Order X created...")

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
    assert saved_order["order_id"] == order_id_from_result # Check ID matches

async def test_create_order_invalid_owner(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
):
    """Tests creating an order with an invalid owner pubkey format."""
    server = patched_server_module
    invalid_owner = "this-is-not-a-valid-pubkey"
    ico_id = "TEST_ICO_INVALID"
    amount = 500
    price = 0.1

    # Call the tool function directly
    result = await server.create_order(
        context=mock_context,
        ico_id=ico_id,
        amount=amount,
        price=price,
        owner=invalid_owner,
    )

    # Expecting a result containing an error message from the tool itself
    assert isinstance(result, str)
    assert "Invalid owner public key format" in result


async def test_cancel_order_success(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path
):
    """Tests successfully cancelling an existing order."""
    server = patched_server_module
    owner_kp = Keypair()
    owner_pubkey_str = str(owner_kp.pubkey())
    ico_id = "TEST_ICO_CANCEL"
    amount = 2000
    price = 0.25

    # 1. Create an order first
    create_result = await server.create_order(
        context=mock_context,
        ico_id=ico_id,
        amount=amount,
        price=price,
        owner=owner_pubkey_str,
    )
    assert "created successfully" in create_result
    order_id = create_result.split(" ")[1] # Extract order_id

    # 2. Cancel the order
    cancel_result = await server.cancel_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        owner=owner_pubkey_str,
    )

    assert isinstance(cancel_result, str)
    assert "cancelled successfully" in cancel_result
    assert order_id in cancel_result

    # 3. Verify the order is removed from the file
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_cancel = json.load(f)
    assert ico_id not in saved_data_after_cancel or not saved_data_after_cancel[ico_id]

async def test_cancel_order_not_found(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
):
    """Tests cancelling an order that does not exist."""
    server = patched_server_module
    owner_kp = Keypair()
    owner_pubkey_str = str(owner_kp.pubkey())
    ico_id = "TEST_ICO_CANCEL_NF"
    non_existent_order_id = str(uuid.uuid4())

    # Call the tool function directly
    result = await server.cancel_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=non_existent_order_id,
        owner=owner_pubkey_str,
    )

    assert isinstance(result, str)
    # Check for either 'no orders found for ICO' or 'order not found'
    assert (
        f"No orders found for ICO {ico_id}" in result or
        f"Order {non_existent_order_id} not found" in result
    )

async def test_cancel_order_wrong_owner(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path
):
    """Tests cancelling an order with the wrong owner public key."""
    server = patched_server_module
    owner_kp = Keypair()
    owner_pubkey_str = str(owner_kp.pubkey())
    attacker_kp = Keypair()
    attacker_pubkey_str = str(attacker_kp.pubkey())
    ico_id = "TEST_ICO_CANCEL_WRONG"

    # 1. Create an order
    create_result = await server.create_order(
        context=mock_context, ico_id=ico_id, amount=100, price=1.0, owner=owner_pubkey_str
    )
    order_id = create_result.split(" ")[1]

    # 2. Attempt to cancel with wrong owner
    cancel_result = await server.cancel_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        owner=attacker_pubkey_str, # Attacker tries to cancel
    )

    assert isinstance(cancel_result, str)
    assert f"Error: You ({attacker_pubkey_str}) are not the owner" in cancel_result

    # 3. Verify order still exists
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_fail = json.load(f)
    assert ico_id in saved_data_after_fail
    assert len(saved_data_after_fail[ico_id]) == 1
    assert saved_data_after_fail[ico_id][0]["order_id"] == order_id

async def test_get_orders_success_and_sorting(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path # Needed to verify creation happened
):
    """Tests retrieving orders for an ICO, verifying sorting by price."""
    server = patched_server_module
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
        await server.create_order(context=mock_context, **params)

    # 2. Get orders for the target ICO
    get_result_str = await server.get_orders(context=mock_context, ico_id=ico_id)
    result_data = json.loads(get_result_str)

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
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path # Needed to verify creation happened
):
    """Tests the limit parameter for get_orders."""
    server = patched_server_module
    owner_kp = Keypair()
    ico_id = "TEST_ICO_LIMIT"

    # 1. Create multiple orders
    for i in range(5):
        params = {"ico_id": ico_id, "amount": 100 + i, "price": 0.1 * (i + 1), "owner": str(owner_kp.pubkey())}
        await server.create_order(context=mock_context, **params)

    # 2. Get orders with limit=2
    get_result_str = await server.get_orders(context=mock_context, ico_id=ico_id, limit=2)
    result_data = json.loads(get_result_str)

    assert len(result_data["orders"]) == 2

    # Verify sorting is still applied before limiting
    assert result_data["orders"][0]["price"] == 0.1
    assert result_data["orders"][1]["price"] == 0.2

async def test_get_orders_no_orders(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
):
    """Tests retrieving orders for an ICO ID that has no orders."""
    server = patched_server_module
    ico_id_no_orders = "TEST_ICO_NO_ORDERS"

    get_result_str = await server.get_orders(context=mock_context, ico_id=ico_id_no_orders)
    result_data = json.loads(get_result_str)

    assert result_data["ico_id"] == ico_id_no_orders
    assert "orders" in result_data
    assert len(result_data["orders"]) == 0


async def test_execute_order_full_success(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path
):
    """Tests successfully executing an entire order."""
    server = patched_server_module
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
    create_result = await server.create_order(
        context=mock_context, ico_id=ico_id, amount=amount, price=price, owner=seller_pubkey_str
    )
    order_id = create_result.split(" ")[1]

    # 2. Execute the full order
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        buyer=buyer_pubkey_str,
        amount=amount, # Buy the full amount
        seller_token_transfer_tx="dummy_sig_token_transfer",
        buyer_sol_payment_tx="dummy_sig_sol_payment",
        token_mint_address=token_mint,
        token_decimals=token_decimals,
    )

    assert isinstance(exec_result, str)
    assert "Successfully executed order" in exec_result
    assert f"Bought {amount / (10**token_decimals)} tokens" in exec_result
    assert order_id in exec_result

    # 3. Verify order is removed from the file
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_exec = json.load(f)
    assert ico_id not in saved_data_after_exec or not saved_data_after_exec[ico_id]

async def test_execute_order_partial_success(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path
):
    """Tests successfully executing part of an order."""
    server = patched_server_module
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
    create_result = await server.create_order(
        context=mock_context, ico_id=ico_id, amount=initial_amount, price=price, owner=seller_pubkey_str
    )
    order_id = create_result.split(" ")[1]

    # 2. Execute part of the order
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        buyer=buyer_pubkey_str,
        amount=buy_amount,
        seller_token_transfer_tx="dummy_sig_token_transfer_partial",
        buyer_sol_payment_tx="dummy_sig_sol_payment_partial",
        token_mint_address=token_mint,
        token_decimals=token_decimals,
    )

    assert isinstance(exec_result, str)
    assert "Successfully executed order" in exec_result
    assert f"Bought {buy_amount / (10**token_decimals)} tokens" in exec_result

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
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path
):
    """Tests attempting to buy more tokens than available in an order."""
    server = patched_server_module
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
    create_result = await server.create_order(
        context=mock_context, ico_id=ico_id, amount=available_amount, price=price, owner=seller_pubkey_str
    )
    order_id = create_result.split(" ")[1]

    # 2. Attempt to execute with excessive amount
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        buyer=buyer_pubkey_str,
        amount=buy_amount,
        seller_token_transfer_tx="dummy_sig_token_transfer_insuff",
        buyer_sol_payment_tx="dummy_sig_sol_payment_insuff",
        token_mint_address=token_mint,
        token_decimals=token_decimals,
    )

    assert isinstance(exec_result, str)
    assert f"Error: Not enough tokens available in order {order_id}" in exec_result
    assert f"Available: {available_amount}" in exec_result
    assert f"Requested: {buy_amount}" in exec_result

    # 3. Verify order is unchanged
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_fail = json.load(f)
    assert saved_data_after_fail[ico_id][0]["amount"] == available_amount

async def test_execute_order_not_found(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
):
    """Tests attempting to execute an order that does not exist."""
    server = patched_server_module
    buyer_kp = Keypair()
    buyer_pubkey_str = str(buyer_kp.pubkey())
    ico_id = "TEST_ICO_EXEC_NF"
    non_existent_order_id = str(uuid.uuid4())

    exec_result = await server.execute_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=non_existent_order_id,
        buyer=buyer_pubkey_str,
        amount=100,
        seller_token_transfer_tx="dummy_sig_token_transfer_nf",
        buyer_sol_payment_tx="dummy_sig_sol_payment_nf",
        token_mint_address=str(Keypair().pubkey()),
        token_decimals=6,
    )

    assert isinstance(exec_result, str)
    assert (
        f"No orders found for ICO {ico_id}" in exec_result or
        f"Order {non_existent_order_id} not found" in exec_result
    )

async def test_execute_order_invalid_buyer_key(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
):
    """Tests execute_order with an invalid buyer public key format."""
    server = patched_server_module
    # Don't even need to create an order for this check
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id="TEST_ICO_EXEC_INV_BUYER",
        order_id=str(uuid.uuid4()),
        buyer="invalid-buyer-key",
        amount=1,
        seller_token_transfer_tx="dummy",
        buyer_sol_payment_tx="dummy",
        token_mint_address=str(Keypair().pubkey()),
        token_decimals=0,
    )

    assert isinstance(exec_result, str)
    assert "Invalid public key or mint address format" in exec_result


async def test_cancel_order_invalid_owner_format(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
):
    """Tests cancelling an order with an invalid owner pubkey format."""
    server = patched_server_module
    invalid_owner = "not-a-key"
    ico_id = "TEST_ICO_CANCEL_INV_OWNER"
    order_id = str(uuid.uuid4()) # Doesn't matter if it exists

    result = await server.cancel_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        owner=invalid_owner,
    )

    assert isinstance(result, str)
    assert "Invalid owner public key format" in result