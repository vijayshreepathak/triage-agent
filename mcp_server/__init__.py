"""Standalone MCP medical-search server.

Run with:  python -m mcp_server.server
Then set:  SEARCH_PROVIDER=mcp  MCP_SERVER_URL=http://127.0.0.1:8765/mcp

The triage graph consumes it through the same ``SearchTool`` interface as
every other provider — proving the MCP swap requires zero graph changes.
"""
