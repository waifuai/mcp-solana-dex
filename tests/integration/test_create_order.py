"""
Integration Tests for create_order Functionality

This module contains integration tests for the create_order MCP tool functionality.
The tests validate that the order creation process works correctly and handles
various edge cases and error conditions.

Test Coverage:
- Successful order creation with valid parameters
- Error handling for invalid owner public key formats
- Order persistence to JSON file
- Order book initialization for new ICO IDs
- UUID generation and assignment for orders
- Input validation for public key formats

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

# --- Test Cases for create_order ---

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