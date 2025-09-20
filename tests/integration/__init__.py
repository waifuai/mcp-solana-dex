"""
Integration Tests for MCP Solana DEX

This package contains integration tests for the MCP Solana DEX server. These tests
validate the complete functionality of all MCP tools by testing them against the
actual server implementation.

The integration tests cover:
- Order lifecycle management (create, cancel, execute, get)
- Error handling for invalid inputs and edge cases
- Balance validation and RPC integration
- Order book persistence and retrieval
- Security checks (owner verification, authorization)

Test files:
- conftest.py: Pytest fixtures and test configuration
- test_create_order.py: Tests for order creation functionality
- test_cancel_order.py: Tests for order cancellation functionality
- test_execute_order.py: Tests for order execution pre-checks
- test_get_orders.py: Tests for order retrieval and sorting

All tests use mocked Solana RPC calls and temporary file storage to ensure
reliable and isolated testing without requiring actual blockchain interaction.
"""

# Integration tests for mcp-solana-dex