"""
MCP Solana DEX Package

This package provides the core functionality for a Solana-based decentralized exchange
(DEX) server that operates as an MCP (Model Context Protocol) service. The package
includes the main server implementation with tools for managing token orders, persistence
layer for order book management, and integration with Solana RPC for blockchain operations.

The package is designed to work with ICO tokens and provides a safe way to validate
transactions before they are submitted to the blockchain, reducing failed transaction
costs for users.

Main components:
- server.py: Main server implementation with MCP tools
- Order data models and persistence
- Solana RPC integration for balance validation
- JSON-based order book storage
"""

# MCP Solana DEX