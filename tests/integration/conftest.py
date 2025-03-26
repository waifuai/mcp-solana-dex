import asyncio
import json
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Tuple

import pytest
import pytest_asyncio
from pytest import MonkeyPatch

# Ensure the server module can be imported
ROOT_DIR = Path(__file__).parent.parent.parent
sys.path.insert(0, str(ROOT_DIR))

# --- Test Data Fixture ---

@pytest.fixture(scope="module")
def temp_order_book_path(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Creates a temporary directory and path for the order book JSON file."""
    temp_dir = tmp_path_factory.mktemp("dex_data")
    return temp_dir / "test_order_book.json"

@pytest.fixture(scope="module", autouse=True)
def patch_order_book_path(
    monkeypatch: MonkeyPatch, temp_order_book_path: Path
):
    """
    Patches the ORDER_BOOK_FILE path in the server module to use the
    temporary path for the duration of the test module.
    Also ensures the data directory exists before the server tries to write.
    """
    # Ensure the parent directory for the temp file exists
    temp_order_book_path.parent.mkdir(parents=True, exist_ok=True)

    # Patch the variable in the server module
    monkeypatch.setattr(
        "mcp_solana_dex.server.ORDER_BOOK_FILE", temp_order_book_path, raising=True
    )
    # Optionally, patch the environment variable if the server reloads it dynamically
    # monkeypatch.setenv("ORDER_BOOK_FILE", str(temp_order_book_path))

    print(f"Patched ORDER_BOOK_FILE to: {temp_order_book_path}") # For debugging test setup

    # Clean up the file before the module starts (optional, tmp_path should be clean)
    if temp_order_book_path.exists():
        temp_order_book_path.unlink()

    yield # Run tests

    # Clean up after tests in the module (optional, tmp_path handles dir removal)
    # if temp_order_book_path.exists():
    #     try:
    #         temp_order_book_path.unlink()
    #     except OSError:
    #         pass # Ignore errors during cleanup

# --- Server Process Fixture ---

@pytest_asyncio.fixture(scope="module")
async def dex_server_process() -> AsyncGenerator[Tuple[asyncio.subprocess.Process, asyncio.StreamWriter, asyncio.StreamReader], None]:
    """
    Starts the mcp_solana_dex/server.py as a subprocess for integration tests.

    Yields:
        A tuple containing the process object, stdin writer, and stdout reader.
    """
    server_path = ROOT_DIR / "mcp_solana_dex" / "server.py"
    process = await asyncio.create_subprocess_exec(
        sys.executable, # Use the same python interpreter running pytest
        str(server_path),
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE, # Capture stderr for debugging
        cwd=ROOT_DIR # Run from project root
    )

    # Give the server a moment to start up
    await asyncio.sleep(1.5) # Adjust if needed

    # Check if the process started successfully
    if process.returncode is not None:
        stdout, stderr = await process.communicate()
        pytest.fail(
            f"Server process failed to start (return code: {process.returncode}).\n"
            f"Stderr:\n{stderr.decode(errors='ignore')}\n"
            f"Stdout:\n{stdout.decode(errors='ignore')}"
        )

    print(f"\nStarted DEX server process (PID: {process.pid})")

    # Type assertion for clarity, as PIPE guarantees these are not None
    stdin_writer = process.stdin
    stdout_reader = process.stdout
    assert isinstance(stdin_writer, asyncio.StreamWriter)
    assert isinstance(stdout_reader, asyncio.StreamReader)

    yield process, stdin_writer, stdout_reader

    # --- Cleanup ---
    print(f"\nTerminating DEX server process (PID: {process.pid})...")
    if process.returncode is None: # Only terminate if still running
        stdin_writer.close() # Close stdin first
        try:
            await stdin_writer.wait_closed()
        except ConnectionResetError:
            pass # Ignore if server already closed connection

        process.terminate()
        try:
            # Wait with a timeout
            await asyncio.wait_for(process.wait(), timeout=5.0)
            print(f"Server process {process.pid} terminated gracefully.")
        except asyncio.TimeoutError:
            print(f"Server process {process.pid} did not terminate gracefully, killing...")
            process.kill()
            await process.wait() # Ensure it's killed
        except ProcessLookupError:
            print(f"Server process {process.pid} already exited.") # Handle race condition

    # Drain stderr to avoid warnings and capture final output
    if process.stderr:
        try:
            stderr_output = await process.stderr.read()
            if stderr_output:
                print(f"--- Server Stderr (PID: {process.pid}) ---\n"
                      f"{stderr_output.decode(errors='ignore')}\n"
                      f"---------------------------------------")
        except Exception as e:
            print(f"Error reading stderr from server process {process.pid}: {e}")