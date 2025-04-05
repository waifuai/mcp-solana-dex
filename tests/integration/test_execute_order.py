import asyncio
import json
import uuid
import types # For type hinting the module fixture
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch, AsyncMock, PropertyMock # Added for mocking RPC calls

import pytest
import pytest_asyncio
from solders.keypair import Keypair # For generating test owner keys
from solders.pubkey import Pubkey # For ATA mocking
from solders.rpc.responses import GetBalanceResp, GetTokenAccountBalanceResp # For mock response types
# Removed problematic import for TokenAccountBalance
from solana.rpc.core import RPCException # For mocking RPC errors

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# --- Mock response structures helper ---
def create_mock_balance_resp(lamports: int) -> MagicMock:
    mock_resp = MagicMock(spec=GetBalanceResp)
    mock_resp.value = lamports
    return mock_resp

def create_mock_token_balance_resp(amount: int, decimals: int) -> MagicMock:
    mock_resp = MagicMock(spec=GetTokenAccountBalanceResp)
    # Create a generic MagicMock for the 'value' attribute, no spec needed here
    mock_value = MagicMock()
    mock_value.amount = str(amount)
    mock_value.decimals = decimals
    mock_value.ui_amount_string = str(amount / (10**decimals))
    mock_resp.value = mock_value
    return mock_resp

# --- Test Cases for execute_order ---

@patch('mcp_solana_dex.server.get_associated_token_address', return_value=Pubkey.new_unique()) # Mock ATA globally for execute tests
@patch('mcp_solana_dex.server.AsyncClient') # Mock the client class
async def test_execute_order_full_success(
    MockAsyncClient: MagicMock, # Comes from @patch
    mock_get_ata: MagicMock, # Comes from @patch
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path
):
    """Tests successfully passing pre-checks for executing an entire order."""
    server = patched_server_module
    seller_kp = Keypair()
    buyer_kp = Keypair()
    seller_pubkey_str = str(seller_kp.pubkey())
    buyer_pubkey_str = str(buyer_kp.pubkey())
    ico_id = "TEST_ICO_EXEC_FULL"
    amount = 5000 # Example amount
    price = 0.1 # Example price
    token_mint = str(Keypair().pubkey()) # Example mint
    token_decimals = 6 # Dummy decimals
    required_sol_lamports = int((amount / (10**token_decimals)) * price * server.LAMPORTS_PER_SOL)

    # Configure Mock AsyncClient instance
    mock_client_instance = AsyncMock()
    mock_client_instance.is_connected.return_value = True
    # Simulate sufficient balances
    mock_client_instance.get_balance.return_value = create_mock_balance_resp(required_sol_lamports + 1000) # Buyer has enough SOL
    mock_client_instance.get_token_account_balance.return_value = create_mock_token_balance_resp(amount + 50, token_decimals) # Seller has enough tokens
    # Make the AsyncClient constructor return our mock instance
    MockAsyncClient.return_value.__aenter__.return_value = mock_client_instance

    # 1. Create the order
    create_result = await server.create_order(
        context=mock_context, ico_id=ico_id, amount=amount, price=price, owner=seller_pubkey_str
    )
    order_id = create_result.split(" ")[1]

    # 2. Execute the pre-checks (full order amount)
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        buyer=buyer_pubkey_str,
        amount=amount, # Buy the full amount
        # Removed tx signature params
        token_mint_address=token_mint,
        token_decimals=token_decimals,
    )

    # Assert pre-checks passed and message is correct
    assert isinstance(exec_result, str)
    assert "Pre-conditions met for order" in exec_result
    assert "Client should now submit the atomic swap transaction" in exec_result
    assert order_id in exec_result

    # Verify RPC calls were made (optional but good practice)
    mock_client_instance.is_connected.assert_awaited_once()
    mock_client_instance.get_balance.assert_awaited_once()
    mock_client_instance.get_token_account_balance.assert_awaited_once()
    mock_get_ata.assert_called_once() # Verify ATA lookup happened

    # 3. Verify order is removed from the file (since it was fully executed)
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_exec = json.load(f)
    assert ico_id not in saved_data_after_exec or not saved_data_after_exec[ico_id]

@patch('mcp_solana_dex.server.get_associated_token_address', return_value=Pubkey.new_unique())
@patch('mcp_solana_dex.server.AsyncClient')
async def test_execute_order_partial_success(
    MockAsyncClient: MagicMock,
    mock_get_ata: MagicMock,
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path
):
    """Tests successfully passing pre-checks for executing part of an order."""
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
    required_sol_lamports = int((buy_amount / (10**token_decimals)) * price * server.LAMPORTS_PER_SOL)

    # Configure Mock AsyncClient instance
    mock_client_instance = AsyncMock()
    mock_client_instance.is_connected.return_value = True
    # Simulate sufficient balances
    mock_client_instance.get_balance.return_value = create_mock_balance_resp(required_sol_lamports + 1000)
    mock_client_instance.get_token_account_balance.return_value = create_mock_token_balance_resp(initial_amount + 50, token_decimals) # Seller has enough
    MockAsyncClient.return_value.__aenter__.return_value = mock_client_instance

    # 1. Create the order
    create_result = await server.create_order(
        context=mock_context, ico_id=ico_id, amount=initial_amount, price=price, owner=seller_pubkey_str
    )
    order_id = create_result.split(" ")[1]

    # 2. Execute pre-checks for part of the order
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        buyer=buyer_pubkey_str,
        amount=buy_amount,
        # Removed tx signature params
        token_mint_address=token_mint,
        token_decimals=token_decimals,
    )

    # Assert pre-checks passed
    assert isinstance(exec_result, str)
    assert "Pre-conditions met for order" in exec_result
    assert "Client should now submit the atomic swap transaction" in exec_result

    # 3. Verify order amount is reduced in the file
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_exec = json.load(f)
    assert ico_id in saved_data_after_exec
    assert len(saved_data_after_exec[ico_id]) == 1
    updated_order = saved_data_after_exec[ico_id][0]
    assert updated_order["order_id"] == order_id
    assert updated_order["amount"] == remaining_amount # Check remaining amount
    assert updated_order["price"] == price
    assert updated_order["owner"] == seller_pubkey_str

async def test_execute_order_buy_more_than_available(
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path
):
    """Tests attempting to buy more tokens than available in the specific order."""
    server = patched_server_module
    seller_kp = Keypair()
    buyer_kp = Keypair()
    seller_pubkey_str = str(seller_kp.pubkey())
    buyer_pubkey_str = str(buyer_kp.pubkey())
    ico_id = "TEST_ICO_EXEC_INSUFFICIENT_ORDER"
    available_amount = 100
    buy_amount = 101 # Try to buy more than available in this order
    price = 1.0
    token_mint = str(Keypair().pubkey())
    token_decimals = 2

    # 1. Create the order
    create_result = await server.create_order(
        context=mock_context, ico_id=ico_id, amount=available_amount, price=price, owner=seller_pubkey_str
    )
    order_id = create_result.split(" ")[1]

    # 2. Attempt to execute pre-checks with excessive amount
    # No need to mock RPC here, as the check happens before RPC calls
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        buyer=buyer_pubkey_str,
        amount=buy_amount,
        token_mint_address=token_mint,
        token_decimals=token_decimals,
    )

    # Assert the error is caught before RPC checks
    assert isinstance(exec_result, str)
    assert f"Error: Not enough tokens available in order {order_id}" in exec_result
    assert f"Available: {available_amount}" in exec_result
    assert f"Requested: {buy_amount}" in exec_result

    # 3. Verify order is unchanged in the file
    with open(temp_order_book_path, 'r') as f:
        saved_data_after_fail = json.load(f)
    assert ico_id in saved_data_after_fail
    assert len(saved_data_after_fail[ico_id]) == 1
    assert saved_data_after_fail[ico_id][0]["amount"] == available_amount

@patch('mcp_solana_dex.server.AsyncClient') # Still patch client to avoid real connection attempt
async def test_execute_order_not_found(
    MockAsyncClient: MagicMock, # Comes from @patch
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
):
    """Tests attempting to execute pre-checks for an order that does not exist."""
    server = patched_server_module
    buyer_kp = Keypair()
    buyer_pubkey_str = str(buyer_kp.pubkey())
    ico_id = "TEST_ICO_EXEC_NF"
    non_existent_order_id = str(uuid.uuid4())

    # No need to configure mock client instance as the error should occur before connection
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=non_existent_order_id,
        buyer=buyer_pubkey_str,
        amount=100,
        token_mint_address=str(Keypair().pubkey()),
        token_decimals=6,
    )

    # Assert the error is caught before RPC checks
    assert isinstance(exec_result, str)
    assert (
        f"No orders found for ICO {ico_id}" in exec_result or
        f"Order {non_existent_order_id} not found" in exec_result
    )
    # Ensure no RPC connection was attempted
    MockAsyncClient.assert_not_called()

@patch('mcp_solana_dex.server.AsyncClient') # Still patch client
async def test_execute_order_invalid_buyer_key(
    MockAsyncClient: MagicMock,
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
):
    """Tests execute_order pre-checks with an invalid buyer public key format."""
    server = patched_server_module
    # Don't need to create an order or configure mock client
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id="TEST_ICO_EXEC_INV_BUYER",
        order_id=str(uuid.uuid4()),
        buyer="invalid-buyer-key", # Invalid key
        amount=1,
        token_mint_address=str(Keypair().pubkey()),
        token_decimals=0,
    )

    # Assert the error is caught before RPC checks
    assert isinstance(exec_result, str)
    assert "Invalid public key or mint address format" in exec_result
    MockAsyncClient.assert_not_called()

# --- New Tests for Pre-Check Failures ---

@patch('mcp_solana_dex.server.get_associated_token_address', return_value=Pubkey.new_unique())
@patch('mcp_solana_dex.server.AsyncClient')
async def test_execute_order_insufficient_sol(
    MockAsyncClient: MagicMock,
    mock_get_ata: MagicMock,
    patched_server_module: types.ModuleType,
    mock_context: MagicMock,
    temp_order_book_path: Path # To verify order is NOT changed
):
    """Tests execute_order pre-checks failing due to insufficient buyer SOL."""
    server = patched_server_module
    seller_kp = Keypair()
    buyer_kp = Keypair()
    seller_pubkey_str = str(seller_kp.pubkey())
    buyer_pubkey_str = str(buyer_kp.pubkey())
    ico_id = "TEST_ICO_EXEC_NO_SOL"
    amount = 1000
    price = 0.5
    token_mint = str(Keypair().pubkey())
    token_decimals = 6
    required_sol_lamports = int((amount / (10**token_decimals)) * price * server.LAMPORTS_PER_SOL)

    # Configure Mock AsyncClient instance
    mock_client_instance = AsyncMock()
    mock_client_instance.is_connected.return_value = True
    # Simulate INSUFFICIENT SOL balance
    mock_client_instance.get_balance.return_value = create_mock_balance_resp(required_sol_lamports - 1)
    # Seller token balance doesn't matter here, but mock it anyway
    mock_client_instance.get_token_account_balance.return_value = create_mock_token_balance_resp(amount + 50, token_decimals)
    MockAsyncClient.return_value.__aenter__.return_value = mock_client_instance

    # 1. Create the order
    create_result = await server.create_order(
        context=mock_context, ico_id=ico_id, amount=amount, price=price, owner=seller_pubkey_str
    )
    order_id = create_result.split(" ")[1]

    # 2. Execute pre-checks
    exec_result = await server.execute_order(
        context=mock_context,
        ico_id=ico_id,
        order_id=order_id,
        buyer=buyer_pubkey_str,
        amount=amount,
        token_mint_address=token_mint,
        token_decimals=token_decimals,
    )

    # Assert pre-checks failed with correct error
    assert isinstance(exec_result, str)
    assert "Error: Insufficient SOL balance for buyer" in exec_result
    assert f"Required: {required_sol_lamports} lamports" in exec_result

    # Verify RPC calls were made up to the point of failure
