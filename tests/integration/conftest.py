import asyncio
import json
import os
import sys
import importlib # Needed for reloading
from pathlib import Path
from typing import AsyncGenerator, Tuple, Generator
from unittest.mock import MagicMock # For mocking Context

import pytest
import pytest_asyncio
from pytest import MonkeyPatch

# Ensure the server module can be imported
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# Import the module type for type hinting
import types
import mcp_solana_dex.server as server_module_for_hinting # Alias for clarity

# --- Test Data Fixture ---

@pytest.fixture(scope="function") # Keep function scope for temp path
def temp_order_book_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Creates a temporary directory and path for the order book JSON file."""
    temp_dir = tmp_path_factory.mktemp("dex_data")
    file_path = temp_dir / "test_order_book.json"
    # Ensure the directory exists and the file is clean before each test
    # Note: tmp_path_factory handles directory creation and cleanup
    file_path.parent.mkdir(parents=True, exist_ok=True)
    if file_path.exists():
        file_path.unlink()
    print(f"\nUsing temp order book: {file_path}")
    return file_path

# --- Mock Context Fixture ---
@pytest.fixture(scope="function")
def mock_context() -> MagicMock:
    """Provides a mock MCP Context object."""
    return MagicMock()

# --- Patched Server Module Fixture ---
@pytest.fixture(scope="function")
def patched_server_module(
    monkeypatch: MonkeyPatch, temp_order_book_path: Path
) -> Generator[types.ModuleType, None, None]:
    """
    Patches the ORDER_BOOK_FILE path and provides the reloaded server module.
    Ensures a clean state (including global order_book dict) for each test.
    """
    # 1. Patch the ORDER_BOOK_FILE constant *before* importing/reloading
    # Use setenv so the reloaded module picks it up via os.getenv
    monkeypatch.setenv("ORDER_BOOK_FILE", str(temp_order_book_path))
    print(f"Set ORDER_BOOK_FILE env var to: {temp_order_book_path}")

    # 2. Reload the server module to pick up the patched path and reset global state
    # Important: Need to handle potential import errors if module structure changes
    try:
        # Ensure the module is loaded initially if not already
        import mcp_solana_dex.server
        # Reload the module
        reloaded_server = importlib.reload(mcp_solana_dex.server)
        print("Reloaded mcp_solana_dex.server module.")
        # Explicitly clear the global order_book *after* reload
        if hasattr(reloaded_server, 'order_book') and isinstance(reloaded_server.order_book, dict):
            reloaded_server.order_book.clear()
            print(f"Cleared global order_book dictionary after reload. ID: {id(reloaded_server.order_book)}, Content: {reloaded_server.order_book}") # Added logging
        else:
            print("Warning: Could not find or clear order_book dictionary after reload.")
    except Exception as e:
        pytest.fail(f"Failed to reload or clear order_book in mcp_solana_dex.server: {e}")

    # 3. Yield the reloaded module to the test
    yield reloaded_server

    # 4. Cleanup (optional, could reset state further if needed)
    print("Finished test using patched server module.")

# --- Server Process Fixture (REMOVED) ---
# The dex_server_process fixture is no longer needed as we test functions directly.