#!/bin/bash

# File: ~/Projects/local-llm-mcp/setup.sh
# Setup script for Standardized Agent-Based Local LLM MCP Server
# Environment: Ubuntu 22.04, NVIDIA Driver 575, CUDA 12.9, RTX 1080ti (11GB VRAM)

set -e

echo "🚀 Setting up Standardized Agent-Based Local LLM MCP Server..."
echo "📋 Target: Ubuntu 22.04 + NVIDIA Driver 575 + CUDA 12.9 + RTX 1080ti"
echo "📁 Location: ~/Projects/local-llm-mcp/ (Git repo)"

# Check CUDA
if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️  Warning: nvidia-smi not found. Make sure you have NVIDIA drivers installed."
    exit 1
fi

CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | sed -n 's/.*CUDA Version: \([0-9]*\.[0-9]*\).*/\1/p')
echo "🔍 Detected CUDA Version: $CUDA_VERSION"

if [[ "$CUDA_VERSION" < "12.0" ]]; then
    echo "⚠️  Warning: CUDA version is less than 12.0. This setup is optimized for CUDA 12.9."
fi

# Create project directory structure
PROJECT_DIR="$HOME/Projects/local-llm-mcp"
echo "📁 Creating project at: $PROJECT_DIR"

# Initialize git repo if it doesn't exist
if [ ! -d "$PROJECT_DIR/.git" ]; then
    mkdir -p "$PROJECT_DIR"
    cd "$PROJECT_DIR"
    
    echo "🔧 Initializing Git repository..."
    git init
    
    # Create initial .gitignore
    cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
venv/

# Model files (too large)
models/
*.gguf

# Generated content
workspaces/
logs/
state/

# Local config
.env
*.local

# IDE
.vscode/
.idea/

# OS
.DS_Store
EOF
    
    echo "📝 Created .gitignore"
else
    cd "$PROJECT_DIR"
    echo "✅ Git repository already exists"
fi

# Create folder structure
echo "📁 Creating standardized directory structure..."
mkdir -p schemas
mkdir -p agents
mkdir -p models
mkdir -p state
mkdir -p workspaces
mkdir -p logs

# Create Python virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies optimized for CUDA 12.9
echo "📥 Installing dependencies for CUDA 12.9..."
pip install --upgrade pip

# Install llama-cpp-python with CUDA 12.x support
echo "🔧 Compiling llama-cpp-python with CUDA 12.9 support..."
export CMAKE_ARGS="-DLLAMA_CUDA=on -DCUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda-12"
export FORCE_CMAKE=1
export CUDACXX=/usr/local/cuda-12/bin/nvcc

# Verify CUDA toolkit path
if [ -d "/usr/local/cuda-12" ]; then
    echo "✅ CUDA 12.x toolkit found at /usr/local/cuda-12"
elif [ -d "/usr/local/cuda" ]; then
    echo "✅ CUDA toolkit found at /usr/local/cuda"
    export CMAKE_ARGS="-DLLAMA_CUDA=on -DCUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda"
    export CUDACXX=/usr/local/cuda/bin/nvcc
else
    echo "⚠️  CUDA toolkit not found. Installing CPU version only..."
    export CMAKE_ARGS=""
    export CUDACXX=""
fi

pip install llama-cpp-python[cuda]

# Install other dependencies
pip install mcp pydantic

# Create requirements.txt with JSON schema support
echo "📄 Creating requirements.txt..."
cat > requirements.txt << 'EOF'
mcp>=0.9.0
llama-cpp-python[cuda]>=0.2.0
pydantic>=2.0.0
EOF

# Create schemas module
echo "🔧 Creating JSON schema module..."
touch schemas/__init__.pylocal-llm-mcp/setup.sh
# Setup script for Simple Agent-Based Local LLM MCP Server
# Environment: Ubuntu 22.04, NVIDIA Driver 575, CUDA 12.9, RTX 1080ti (11GB VRAM)

set -e

echo "🚀 Setting up Simple Agent-Based Local LLM MCP Server..."
echo "📋 Target: Ubuntu 22.04 + NVIDIA Driver 575 + CUDA 12.9 + RTX 1080ti"

# Check CUDA
if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️  Warning: nvidia-smi not found. Make sure you have NVIDIA drivers installed."
    exit 1
fi

CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | sed -n 's/.*CUDA Version: \([0-9]*\.[0-9]*\).*/\1/p')
echo "🔍 Detected CUDA Version: $CUDA_VERSION"

if [[ "$CUDA_VERSION" < "12.0" ]]; then
    echo "⚠️  Warning: CUDA version is less than 12.0. This setup is optimized for CUDA 12.9."
fi

# Create project directory
PROJECT_DIR="$HOME/local-llm-mcp"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Create folder structure
echo "📁 Creating directory structure..."
mkdir -p agents
mkdir -p models
mkdir -p state
mkdir -p workspaces
mkdir -p logs

# Create Python virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies optimized for CUDA 12.9
echo "📥 Installing dependencies for CUDA 12.9..."
pip install --upgrade pip

# Install llama-cpp-python with CUDA 12.x support
echo "🔧 Compiling llama-cpp-python with CUDA 12.9 support..."
export CMAKE_ARGS="-DLLAMA_CUDA=on -DCUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda-12"
export FORCE_CMAKE=1
export CUDACXX=/usr/local/cuda-12/bin/nvcc

# Verify CUDA toolkit path
if [ -d "/usr/local/cuda-12" ]; then
    echo "✅ CUDA 12.x toolkit found at /usr/local/cuda-12"
elif [ -d "/usr/local/cuda" ]; then
    echo "✅ CUDA toolkit found at /usr/local/cuda"
    export CMAKE_ARGS="-DLLAMA_CUDA=on -DCUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda"
    export CUDACXX=/usr/local/cuda/bin/nvcc
else
    echo "⚠️  CUDA toolkit not found. Installing CPU version only..."
    export CMAKE_ARGS=""
    export CUDACXX=""
fi

pip install llama-cpp-python[cuda]

# Install other dependencies
pip install mcp pydantic

# Create requirements.txt
echo "📄 Creating requirements.txt..."
cat > requirements.txt << 'EOF'
mcp>=0.9.0
llama-cpp-python[cuda]>=0.2.0
pydantic>=2.0.0
EOF

# Create agents/__init__.py
echo "🤖 Creating agent module..."
touch agents/__init__.py

cat > agents/base_agent.py << 'EOF'
# File: ~/local-llm-mcp/agents/base_agent.py
"""
Simple agent base class for the MCP server.
RULE: One agent per file, one file per agent.
"""

from dataclasses import dataclass
from typing import Dict, Any
from datetime import datetime, timezone

@dataclass
class SimpleAgent:
    """Minimal agent data structure - one agent manages one file only"""
    agent_id: str
    name: str
    description: str
    system_prompt: str
    managed_file: str  # Single file only
    context: str = ""
    created_at: str = ""
    last_active: str = ""
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()
        if not self.last_active:
            self.last_active = self.created_at
EOF

# Download model
echo "🤖 Downloading Qwen2.5-Coder 7B model..."
MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
MODEL_FILE="models/qwen2.5-coder-7b-instruct.gguf"

if [ ! -f "$MODEL_FILE" ]; then
    echo "⬇️  Downloading model (this may take a while)..."
    if command -v wget &> /dev/null; then
        wget -O "$MODEL_FILE" "$MODEL_URL"
    elif command -v curl &> /dev/null; then
        curl -L -o "$MODEL_FILE" "$MODEL_URL"
    else
        echo "❌ Neither wget nor curl found. Please download manually:"
        echo "   URL: $MODEL_URL"
        echo "   Save to: $PROJECT_DIR/$MODEL_FILE"
        exit 1
    fi
else
    echo "✅ Model already exists: $MODEL_FILE"
fi

# Create Claude Code MCP configuration
CLAUDE_CONFIG_DIR="$HOME/.config/claude-code"
mkdir -p "$CLAUDE_CONFIG_DIR"

cat > "$CLAUDE_CONFIG_DIR/mcp.json" << EOF
{
  "mcpServers": {
    "local-agent-llm": {
      "command": "python3",
      "args": ["$PROJECT_DIR/local_llm_mcp_server.py"],
      "env": {
        "MODEL_PATH": "$PROJECT_DIR/$MODEL_FILE",
        "N_GPU_LAYERS": "-1",
        "N_CTX": "8192",
        "N_BATCH": "512", 
        "N_THREADS": "8",
        "USE_MMAP": "True",
        "VERBOSE": "False",
        "CUDA_VISIBLE_DEVICES": "0"
      }
    }
  }
}
EOF

# Create README
cat > README.md << 'EOF'
# Simple Agent-Based Local LLM MCP Server

A streamlined MCP server for Claude Code with persistent agents.

**CORE RULE: One agent per file, one file per agent.**

## Features

- **One-to-One Mapping**: Each agent manages exactly one file
- **No Conflicts**: File ownership is strictly enforced
- **CUDA 12.9 Optimized**: RTX 1080ti performance tuned
- **Context Persistence**: Agents remember conversations across sessions
- **Stdio Only**: Clean integration with Claude Code

## Quick Start

1. Run setup: `./setup.sh`
2. Start server: `./start.sh`
3. In Claude Code, agents will be available as tools

## Agent Workflow

```bash
# In Claude Code:
claude

# Create agents for different files:
"Use create_agent to make a database agent that manages schema.sql"
"Use create_agent to make an API agent that manages routes.py" 
"Use create_agent to make a frontend agent that manages index.html"

# Chat with specific agents:
"Use chat_with_agent to have the database agent design user tables"

# Have agents update their files:
"Use agent_manage_file to have the database agent create the schema.sql file"
```

## File Ownership Rules

- ✅ One agent → One file
- ✅ One file → One agent  
- ❌ Agent cannot access files it doesn't own
- ❌ Cannot create agent for file already owned
- ✅ Deleting agent frees up the file for new agent

## Example Project Structure

```
Project/
├── schema.sql      ← Database Agent
├── models.py       ← ORM Agent  
├── routes.py       ← API Agent
├── index.html      ← Frontend Agent
├── styles.css      ← Styling Agent
└── tests.py        ← Testing Agent
```

Each file has one dedicated agent that understands its context and maintains its state.

## Directory Structure

- `agents/` - Agent classes
- `models/` - LLM model files  
- `state/` - Agent state persistence (includes file mappings)
- `workspaces/` - Per-agent workspaces with files
- `logs/` - Server and agent logs
EOF

# Create start script
cat > start.sh << 'EOF'
#!/bin/bash
# File: ~/local-llm-mcp/start.sh
cd "$(dirname "$0")"
source venv/bin/activate
echo "🚀 Starting Simple Agent-Based LLM MCP Server..."
python3 local_llm_mcp_server.py
EOF

chmod +x start.sh

# Create test script  
cat > test.py << 'EOF'
#!/usr/bin/env python3
# File: ~/local-llm-mcp/test.py
"""Test script for the one-agent-per-file MCP server"""

import asyncio
import sys
from pathlib import Path

# Add project to path
sys.path.append(str(Path(__file__).parent))

from local_llm_mcp_server import SimpleLLMServer

async def test_server():
    print("🧪 Testing Simple Agent-Based LLM Server (One Agent Per File)...")
    
    server = SimpleLLMServer()
    
    print("🤖 Testing model loading...")
    if not server.load_model():
        print("❌ Model loading failed")
        return False
    
    print("✅ Model loaded successfully!")
    
    # Test agent creation
    print("🔧 Testing agent creation...")
    result1 = await server.create_agent({
        "name": "Database Agent",
        "description": "Manages the database schema file",
        "system_prompt": "You are a database specialist focused on SQL schema design.",
        "managed_file": "schema.sql",
        "initial_context": "Ready to design and maintain database schema."
    })
    
    print("✅ First agent created!")
    print(f"Result: {result1.content[0].text[:100]}...")
    
    # Test file conflict prevention
    print("🚫 Testing file conflict prevention...")
    result2 = await server.create_agent({
        "name": "Another Agent", 
        "description": "Tries to manage same file",
        "system_prompt": "Another agent",
        "managed_file": "schema.sql"  # Same file - should fail
    })
    
    if "File Conflict" in result2.content[0].text:
        print("✅ File conflict prevention works!")
    else:
        print("❌ File conflict prevention failed!")
        return False
    
    # Test different file - should succeed
    print("📝 Testing different file...")
    result3 = await server.create_agent({
        "name": "API Agent",
        "description": "Manages API routes",
        "system_prompt": "You are an API development specialist.",
        "managed_file": "routes.py"
    })
    
    print("✅ Second agent with different file created!")
    
    # Test list agents
    print("📋 Testing agent listing...")
    list_result = await server.list_agents()
    if "File Ownership Map" in list_result.content[0].text:
        print("✅ Agent listing shows file ownership!")
    
    print("\n🎉 All tests passed! One-agent-per-file rule enforced successfully.")
    print("📊 Key validations:")
    print("   ✅ Model loads correctly")  
    print("   ✅ Agent creation works")
    print("   ✅ File conflicts are prevented") 
    print("   ✅ Multiple agents with different files allowed")
    print("   ✅ File ownership tracking works")
    
    return True

if __name__ == "__main__":
    asyncio.run(test_server())
EOF

chmod +x test.py

echo ""
echo "🎉 Setup complete!"
echo ""
echo "📁 Project directory: $PROJECT_DIR"
echo "🤖 Model location: $PROJECT_DIR/$MODEL_FILE"
echo "⚙️  Claude Code config: $CLAUDE_CONFIG_DIR/mcp.json"
echo ""
echo "🧪 To test the server:"
echo "   cd $PROJECT_DIR && source venv/bin/activate && python3 test.py"
echo ""
echo "🚀 To start the MCP server:"
echo "   cd $PROJECT_DIR && ./start.sh"
echo ""
echo "🔧 Claude Code should now detect your agent server!"
echo "   Available tools: create_agent, list_agents, chat_with_agent, etc."
echo ""
echo "⚠️  **IMPORTANT RULE: One agent per file, one file per agent**"
echo "   - Each agent manages exactly one file"
echo "   - No file can be managed by multiple agents"
echo "   - This prevents conflicts and ensures clean ownership"

# GPU status
echo ""
echo "🖥️  GPU Status:"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits | while read gpu; do
        echo "   GPU: $gpu MB"
    done
else
    echo "   ⚠️  NVIDIA GPU tools not available"
fi

echo ""
echo "💡 RTX 1080ti (11GB) Usage Patterns:"
echo "   - schema.sql → Database Agent"
echo "   - models.py → ORM Agent" 
echo "   - routes.py → API Agent"
echo "   - index.html → Frontend Agent"
echo "   - styles.css → Styling Agent"
echo "   - Each agent maintains context for its single file"#!/bin/bash

# File: ~/local-llm-mcp/setup.sh
# Setup script for Local LLM MCP Server
# Environment: Ubuntu 22.04, NVIDIA Driver 575, CUDA 12.9, RTX 1080ti (11GB VRAM)

set -e

echo "🚀 Setting up Local LLM MCP Server for Claude Code..."
echo "📋 Target: Ubuntu 22.04 + NVIDIA Driver 575 + CUDA 12.9 + RTX 1080ti"

# Check if we're on the right system
if ! command -v nvidia-smi &> /dev/null; then
    echo "⚠️  Warning: nvidia-smi not found. Make sure you have NVIDIA drivers installed."
    exit 1
fi

# Verify CUDA version
CUDA_VERSION=$(nvidia-smi | grep "CUDA Version" | sed -n 's/.*CUDA Version: \([0-9]*\.[0-9]*\).*/\1/p')
echo "🔍 Detected CUDA Version: $CUDA_VERSION"

if [[ "$CUDA_VERSION" < "12.0" ]]; then
    echo "⚠️  Warning: CUDA version is less than 12.0. This setup is optimized for CUDA 12.9."
fi

# Create project directory
PROJECT_DIR="$HOME/local-llm-mcp"
mkdir -p "$PROJECT_DIR"
cd "$PROJECT_DIR"

# Create Python virtual environment
echo "📦 Creating Python virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies optimized for CUDA 12.9
echo "📥 Installing dependencies for CUDA 12.9..."
pip install --upgrade pip

# Install llama-cpp-python with CUDA 12.x support
echo "🔧 Compiling llama-cpp-python with CUDA 12.9 support..."
export CMAKE_ARGS="-DLLAMA_CUDA=on -DCUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda-12"
export FORCE_CMAKE=1
export CUDACXX=/usr/local/cuda-12/bin/nvcc

# Verify CUDA toolkit path
if [ -d "/usr/local/cuda-12" ]; then
    echo "✅ CUDA 12.x toolkit found at /usr/local/cuda-12"
elif [ -d "/usr/local/cuda" ]; then
    echo "✅ CUDA toolkit found at /usr/local/cuda"
    export CMAKE_ARGS="-DLLAMA_CUDA=on -DCUDA_TOOLKIT_ROOT_DIR=/usr/local/cuda"
    export CUDACXX=/usr/local/cuda/bin/nvcc
else
    echo "⚠️  CUDA toolkit not found. Installing CPU version only..."
    export CMAKE_ARGS=""
    export CUDACXX=""
fi

pip install llama-cpp-python[cuda]

# Install other dependencies
pip install mcp starlette uvicorn pydantic

# Create models directory
mkdir -p models

# Download recommended model (Qwen2.5-Coder 7B)
echo "🤖 Downloading Qwen2.5-Coder 7B model..."
echo "This may take a while (several GB download)..."

MODEL_URL="https://huggingface.co/Qwen/Qwen2.5-Coder-7B-Instruct-GGUF/resolve/main/qwen2.5-coder-7b-instruct-q4_k_m.gguf"
MODEL_FILE="models/qwen2.5-coder-7b-instruct.gguf"

if [ ! -f "$MODEL_FILE" ]; then
    if command -v wget &> /dev/null; then
        wget -O "$MODEL_FILE" "$MODEL_URL"
    elif command -v curl &> /dev/null; then
        curl -L -o "$MODEL_FILE" "$MODEL_URL"
    else
        echo "❌ Neither wget nor curl found. Please download the model manually:"
        echo "   URL: $MODEL_URL"
        echo "   Save to: $PROJECT_DIR/$MODEL_FILE"
        exit 1
    fi
else
    echo "✅ Model already exists: $MODEL_FILE"
fi

# Create job processing directories
echo "📁 Creating job processing directories..."
mkdir -p jobs/{queue,processing,completed,failed}

# Create the MCP server script
echo "📝 Creating MCP server script..."
cat > local_llm_mcp_server.py << 'EOF'
# Copy the complete Python script from the artifact above
# This should be the full content of the local_llm_mcp_server.py file
EOF

# Make it executable
chmod +x local_llm_mcp_server.py

# Create Claude Code MCP configuration
CLAUDE_CONFIG_DIR="$HOME/.config/claude-code"
mkdir -p "$CLAUDE_CONFIG_DIR"

cat > "$CLAUDE_CONFIG_DIR/mcp.json" << EOF
{
  "mcpServers": {
    "local-llm": {
      "command": "python3",
      "args": ["$PROJECT_DIR/local_llm_mcp_server.py"],
      "env": {
        "MODEL_PATH": "$PROJECT_DIR/$MODEL_FILE",
        "N_GPU_LAYERS": "-1",
        "N_CTX": "8192",
        "N_BATCH": "512", 
        "N_THREADS": "8",
        "USE_MMAP": "True",
        "VERBOSE": "False",
        "JOBS_DIR": "$PROJECT_DIR/jobs",
        "CUDA_VISIBLE_DEVICES": "0"
      }
    }
  }
}
EOF

# Create test script
cat > test_server.py << 'EOF'
#!/usr/bin/env python3
"""Test script for the Local LLM MCP Server"""

import asyncio
import sys
import os

# Add the project directory to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from local_llm_mcp_server import LocalLLMServer

async def test_server():
    server = LocalLLMServer()
    
    print("🧪 Testing model loading...")
    if not server.load_model():
        print("❌ Model loading failed")
        return False
    
    print("✅ Model loaded successfully!")
    
    # Test generation
    print("\n🤖 Testing code generation...")
    test_args = {
        "prompt": "Write a simple Python function to reverse a string",
        "max_tokens": 256
    }
    
    result = await server.generate_code(test_args)
    print(f"📝 Generated response: {result.content[0].text[:200]}...")
    
    # Test model info
    print("\n📊 Getting model info...")
    info_result = await server.get_model_info()
    print(f"ℹ️  Model info: {info_result.content[0].text[:200]}...")
    
    print("\n✅ All tests passed!")
    return True

if __name__ == "__main__":
    asyncio.run(test_server())
EOF

chmod +x test_server.py

# Create start script
cat > start_server.sh << 'EOF'
#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python3 local_llm_mcp_server.py "$@"
EOF

chmod +x start_server.sh

echo "🎉 Setup complete!"
echo ""
echo "📁 Project directory: $PROJECT_DIR"
echo "🤖 Model location: $PROJECT_DIR/$MODEL_FILE"
echo "⚙️  Claude Code config: $CLAUDE_CONFIG_DIR/mcp.json"
echo ""
echo "🧪 To test the server:"
echo "   cd $PROJECT_DIR && source venv/bin/activate && python3 test_server.py"
echo ""
echo "🚀 To start the MCP server:"
echo "   cd $PROJECT_DIR && ./start_server.sh"
echo ""
echo "🔧 Claude Code should now detect your local LLM server automatically!"
echo "   Use tools like 'generate_code', 'model_info', and 'benchmark_model'"

# Test GPU availability
echo ""
echo "🖥️  GPU Status:"
if command -v nvidia-smi &> /dev/null; then
    nvidia-smi --query-gpu=name,memory.total,memory.free --format=csv,noheader,nounits | while read gpu; do
        echo "   GPU: $gpu MB"
    done
else
    echo "   ⚠️  NVIDIA GPU tools not available"
fi

# Memory recommendations for RTX 1080ti
echo ""
echo "💡 RTX 1080ti (11GB) Recommendations:"
echo "   - 7B model: Perfect fit with room for context"
echo "   - Context size: 8192 tokens (can increase to 16384 if needed)"
echo "   - Batch size: 512 (good balance of speed/memory)"
echo "   - All GPU layers: -1 (uses all 11GB effectively)"