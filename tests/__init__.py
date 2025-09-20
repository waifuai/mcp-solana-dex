"""
Test Package for MCP Solana DEX

This package contains the test suite for the MCP Solana DEX server. It includes
integration tests that validate the core functionality of the DEX server including
order creation, cancellation, execution, and retrieval.

The tests are designed to run against the actual server implementation to ensure
all MCP tools work correctly and handle various edge cases and error conditions
properly.

Test Structure:
- integration/: Comprehensive integration tests for all MCP tools
- conftest.py: Pytest fixtures and configuration for testing
"""

# Test package for mcp-solana-dex