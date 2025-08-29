#!/usr/bin/env python3

"""
File: ~/Projects/local-llm-mcp/test.py
Test Script for Standardized Agent-Based LLM Server

Tests the HTTP server endpoints and agent functionality
"""

import asyncio
import httpx
import json
import sys
from pathlib import Path

async def test_server():
    """Test the HTTP server functionality"""
    print("🧪 Testing Standardized Agent-Based LLM HTTP Server...")
    print("📋 JSON Schema validation enabled")
    print("🌐 Testing HTTP endpoints")
    
    base_url = "http://localhost:8000"
    
    async with httpx.AsyncClient() as client:
        try:
            # Test health endpoint
            print("\n🏥 Testing health endpoint...")
            response = await client.get(f"{base_url}/health")
            if response.status_code == 200:
                health_data = response.json()
                print(f"✅ Health check passed: {health_data['status']}")
                print(f"   Model loaded: {health_data['model']['loaded']}")
                print(f"   Active agents: {health_data['agents']['total']}")
            else:
                print(f"❌ Health check failed: {response.status_code}")
                return False
            
            # Test server info
            print("\n📊 Testing server info...")
            response = await client.get(f"{base_url}/")
            if response.status_code == 200:
                info = response.json()
                print(f"✅ Server info: {info['service']} v{info['version']}")
                print(f"   Features: {', '.join(info['features'])}")
            else:
                print(f"❌ Server info failed: {response.status_code}")
                return False
            
            # Test agent creation via API
            print("\n🤖 Testing agent creation...")
            agent_data = {
                "name": "Test Database Agent",
                "description": "Manages database schema for testing",
                "system_prompt": "You are a database specialist. Always respond with valid JSON.",
                "managed_file": "test_schema.sql",
                "initial_context": "Ready to design test database schema."
            }
            
            response = await client.post(f"{base_url}/api/agents", json=agent_data)
            if response.status_code == 201:
                agent_info = response.json()
                agent_id = agent_info["agent"]["id"]
                print(f"✅ Agent created: {agent_info['agent']['name']} (ID: {agent_id})")
                print(f"   Manages file: {agent_info['agent']['managed_file']}")
            else:
                print(f"❌ Agent creation failed: {response.status_code}")
                print(f"   Error: {response.json()}")
                return False
            
            # Test file conflict prevention
            print("\n🚫 Testing file conflict prevention...")
            conflict_agent_data = {
                "name": "Conflicting Agent",
                "description": "Tries to manage same file",
                "system_prompt": "Another agent",
                "managed_file": "test_schema.sql"  # Same file!
            }
            
            response = await client.post(f"{base_url}/api/agents", json=conflict_agent_data)
            if response.status_code == 409:
                print("✅ File conflict correctly prevented")
                print(f"   Error message: {response.json()['error']}")
            else:
                print(f"❌ File conflict prevention failed: {response.status_code}")
                return False
            
            # Test agent listing
            print("\n📋 Testing agent listing...")
            response = await client.get(f"{base_url}/api/agents")
            if response.status_code == 200:
                agents_data = response.json()
                print(f"✅ Agent listing works: {agents_data['statistics']['total_agents']} agents")
                print(f"   File ownership: {agents_data['file_ownership']}")
            else:
                print(f"❌ Agent listing failed: {response.status_code}")
                return False
            
            # Test MCP endpoint structure
            print("\n📡 Testing MCP endpoint...")
            mcp_request = {
                "method": "list_tools",
                "params": {}
            }
            
            response = await client.post(f"{base_url}/mcp", json=mcp_request)
            if response.status_code == 200:
                tools = response.json()
                tool_names = [tool["name"] for tool in tools.get("tools", [])]
                print(f"✅ MCP endpoint works: {len(tool_names)} tools available")
                print(f"   Tools: {', '.join(tool_names)}")
            else:
                print(f"❌ MCP endpoint failed: {response.status_code}")
                return False
            
            print("\n🎉 All tests passed!")
            print("📊 Test Summary:")
            print("   ✅ HTTP server accessible")
            print("   ✅ Health checks working")
            print("   ✅ Agent creation with JSON schemas")
            print("   ✅ File conflict prevention enforced")
            print("   ✅ Agent listing and file ownership tracking")
            print("   ✅ MCP endpoint ready for Claude Code")
            print("")
            print("🔧 Ready for Claude Code integration!")
            print("   The server is running and the /mcp endpoint is available")
            print("   Claude Code should automatically detect the MCP server")
            
            return True
            
        except httpx.RequestError as e:
            print(f"❌ Connection error: {e}")
            print("💡 Make sure the server is running: uv run local_llm_mcp_server.py")
            return False
        except Exception as e:
            print(f"❌ Test error: {e}")
            return False

if __name__ == "__main__":
    success = asyncio.run(test_server())
    sys.exit(0 if success else 1)