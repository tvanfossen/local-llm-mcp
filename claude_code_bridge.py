#!/usr/bin/env python3
"""MCP Bridge for Claude Code
Bridges stdio MCP protocol to HTTP server
Save as: ~/Projects/local-llm-mcp/claude_code_bridge.py
"""

import asyncio
import json
import logging
import sys
from typing import Any

import httpx

# Configure logging to stderr (stdout is used for MCP communication)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


class ClaudeCodeMCPBridge:
    """Bridge between Claude Code (stdio) and HTTP MCP server"""

    def __init__(self, server_url: str = "http://localhost:8000"):
        self.server_url = server_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.initialized = False

    async def handle_request(self, request: dict[str, Any]) -> dict[str, Any] | None:
        """Handle MCP request from Claude Code"""
        try:
            method = request.get("method", "")
            params = request.get("params", {})
            request_id = request.get("id")

            logger.info(f"Handling request: {method}")

            # Build JSON-RPC request for HTTP server
            jsonrpc_request = {
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            }

            # Add ID if this is a request (not notification)
            if request_id is not None:
                jsonrpc_request["id"] = request_id

            # Send to HTTP server
            response = await self.client.post(
                f"{self.server_url}/mcp",
                json=jsonrpc_request,
                headers={"Content-Type": "application/json"},
            )

            if response.status_code == 200:
                response_data = response.json()

                # Handle initialization response
                if method == "initialize" and not self.initialized:
                    self.initialized = True
                    logger.info("MCP bridge initialized successfully")

                return response_data

            if response.status_code == 204:
                # No content for notifications
                return None

            logger.error(f"HTTP error {response.status_code}: {response.text}")
            if request_id is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "error": {
                        "code": -32603,
                        "message": f"HTTP error {response.status_code}",
                        "data": response.text,
                    },
                }
            return None

        except httpx.RequestError as e:
            logger.error(f"Connection error: {type(e).__name__}: {e}")
            if request.get("id") is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Cannot connect to server at {self.server_url}",
                        "data": str(e),
                    },
                }
            return None

        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            if request.get("id") is not None:
                return {
                    "jsonrpc": "2.0",
                    "id": request.get("id"),
                    "error": {
                        "code": -32603,
                        "message": f"Bridge error: {e!s}",
                    },
                }
            return None

    async def run(self):
        """Main stdio loop"""
        logger.info(f"Starting Claude Code MCP bridge to {self.server_url}")

        try:
            while True:
                # Read line from stdin
                line = sys.stdin.readline()
                if not line:
                    logger.info("EOF received, shutting down")
                    break

                line = line.strip()
                if not line:
                    continue

                try:
                    # Parse JSON-RPC request
                    request = json.loads(line)
                    logger.info(f"Received: {request.get('method', 'unknown')}")

                    # Handle request
                    response = await self.handle_request(request)

                    # Send response if needed
                    if response is not None:
                        response_line = json.dumps(response)
                        print(response_line, flush=True)
                        logger.info(f"Sent response for {request.get('method', 'unknown')}")

                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    error_response = {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {
                            "code": -32700,
                            "message": "Parse error",
                            "data": str(e),
                        },
                    }
                    print(json.dumps(error_response), flush=True)

                except Exception as e:
                    logger.error(f"Request handling error: {e}")

        except KeyboardInterrupt:
            logger.info("Keyboard interrupt received")

        finally:
            await self.client.aclose()
            logger.info("Bridge shutdown complete")


async def main():
    """Main entry point"""
    import os

    server_url = os.getenv("SERVER_URL", "http://localhost:8000")

    bridge = ClaudeCodeMCPBridge(server_url)
    await bridge.run()


if __name__ == "__main__":
    asyncio.run(main())
