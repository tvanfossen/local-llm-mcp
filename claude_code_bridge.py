#!/usr/bin/env python3

"""Claude Code MCP Bridge
File: ~/Projects/local-llm-mcp/claude_code_bridge.py

This bridge connects Claude Code to the local LLM MCP server via HTTP.
It implements the MCP protocol over stdio and forwards requests to the HTTP server.
"""

import asyncio
import json
import os
import sys
from typing import Any, Dict, List, Optional
import urllib.request
import urllib.parse
import urllib.error
import argparse


class ClaudeCodeBridge:
    """MCP Bridge for Claude Code integration"""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url.rstrip('/')
        self.session_token: Optional[str] = None

    async def run(self):
        """Main bridge loop - implements MCP protocol over stdio"""
        # Try to authenticate on startup
        await self._authenticate()

        while True:
            try:
                # Read MCP request from stdin
                line = sys.stdin.readline()
                if not line:
                    break

                request = json.loads(line.strip())

                # Process the request
                response = await self._handle_request(request)

                # Send response to stdout
                print(json.dumps(response), flush=True)

            except Exception as e:
                # Send error response
                error_response = {
                    "jsonrpc": "2.0",
                    "id": request.get("id") if 'request' in locals() else None,
                    "error": {
                        "code": -32603,
                        "message": f"Internal error: {str(e)}"
                    }
                }
                print(json.dumps(error_response), flush=True)

    async def _authenticate(self) -> bool:
        """Authenticate with the server using orchestrator auth"""
        try:
            auth_data = json.dumps({"client_type": "claude_code_bridge"}).encode('utf-8')
            req = urllib.request.Request(
                f"{self.server_url}/api/orchestrator/authenticate",
                data=auth_data,
                headers={'Content-Type': 'application/json'}
            )

            with urllib.request.urlopen(req, timeout=10) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    self.session_token = data.get("session_token")
                    return True
                else:
                    print(f"Auth failed: {response.status}", file=sys.stderr)
                    return False
        except Exception as e:
            print(f"Auth error: {e}", file=sys.stderr)
            return False

    async def _handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP request"""
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id")

        if method == "initialize":
            return await self._handle_initialize(request_id, params)
        elif method == "tools/list":
            return await self._handle_tools_list(request_id)
        elif method == "tools/call":
            return await self._handle_tools_call(request_id, params)
        else:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Method not found: {method}"
                }
            }

    async def _handle_initialize(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle MCP initialize"""
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {
                    "tools": {}
                },
                "serverInfo": {
                    "name": "local-llm-agents",
                    "version": "1.0.0"
                }
            }
        }

    async def _handle_tools_list(self, request_id: Any) -> Dict[str, Any]:
        """Get tools list from server"""
        try:
            request_data = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }).encode('utf-8')

            headers = {'Content-Type': 'application/json'}
            if self.session_token:
                headers["Authorization"] = f"Bearer {self.session_token}"

            req = urllib.request.Request(
                f"{self.server_url}/mcp",
                data=request_data,
                headers=headers
            )

            with urllib.request.urlopen(req, timeout=30) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": data.get("result", {"tools": []})
                    }
                else:
                    raise Exception(f"Server returned {response.status}")

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Failed to get tools: {str(e)}"
                }
            }

    async def _handle_tools_call(self, request_id: Any, params: Dict[str, Any]) -> Dict[str, Any]:
        """Forward tool call to server"""
        try:
            request_data = json.dumps({
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/call",
                "params": params
            }).encode('utf-8')

            headers = {'Content-Type': 'application/json'}
            if self.session_token:
                headers["Authorization"] = f"Bearer {self.session_token}"

            req = urllib.request.Request(
                f"{self.server_url}/mcp",
                data=request_data,
                headers=headers
            )

            with urllib.request.urlopen(req, timeout=120) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode('utf-8'))
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": data.get("result", {})
                    }
                else:
                    error_text = response.read().decode('utf-8')
                    raise Exception(f"Server returned {response.status}: {error_text}")

        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32603,
                    "message": f"Tool call failed: {str(e)}"
                }
            }


async def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(description="Claude Code MCP Bridge")
    parser.add_argument(
        "--server-url",
        default=os.environ.get("SERVER_URL", "http://localhost:8000"),
        help="MCP server URL"
    )
    args = parser.parse_args()

    bridge = ClaudeCodeBridge(args.server_url)
    await bridge.run()


if __name__ == "__main__":
    asyncio.run(main())