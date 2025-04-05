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

# --- Test Cases for get_orders ---

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