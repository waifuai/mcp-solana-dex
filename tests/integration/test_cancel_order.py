"""
Integration Tests for cancel_order Functionality

This module contains integration tests for the cancel_order MCP tool functionality.
The tests validate that the order cancellation process works correctly and includes
proper authorization checks and error handling.

Test Coverage:
- Successful order cancellation with valid owner
- Error handling for non-existent orders
- Authorization verification (owner-only cancellation)
- Error handling for invalid owner public key formats
- Order removal from JSON file after cancellation
- Proper handling of ICO IDs with no existing orders
- Verification that unauthorized users cannot cancel orders

The tests use the patched server module fixture to ensure clean state and
temporary file storage for each test, providing reliable and isolated testing.
"""

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

# --- Test Cases for cancel_order ---

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