#!/bin/bash
# MCP Orchestrator Launcher
# Save as: ~/Projects/local-llm-mcp/orchestrate.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
MCP_SERVER="${MCP_SERVER:-http://localhost:8000}"
MCP_KEY_DIR="${HOME}/.ssh/mcp"
MCP_KEY_FILE="${MCP_KEY_DIR}/id_rsa_mcp"
BROWSER="${BROWSER:-}"

# Functions
print_header() {
    echo -e "${BLUE}╔════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║       MCP Orchestrator Launcher v1.0       ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════════╝${NC}"
    echo
}

check_server() {
    echo -n "🔍 Checking MCP server at ${MCP_SERVER}... "
    if curl -s "${MCP_SERVER}/health" > /dev/null 2>&1; then
        echo -e "${GREEN}✓${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        echo -e "${YELLOW}⚠️  Server not responding. Make sure it's running:${NC}"
        echo "   inv run  # or docker run ..."
        return 1
    fi
}

check_keys() {
    echo -n "🔑 Checking for MCP keys... "
    if [ -f "${MCP_KEY_FILE}" ]; then
        echo -e "${GREEN}✓${NC}"
        # Check permissions
        perms=$(stat -c %a "${MCP_KEY_FILE}" 2>/dev/null || stat -f %A "${MCP_KEY_FILE}" 2>/dev/null)
        if [ "$perms" != "600" ]; then
            echo -e "${YELLOW}⚠️  Warning: Key permissions are ${perms}, should be 600${NC}"
            echo -n "   Fixing permissions... "
            chmod 600 "${MCP_KEY_FILE}"
            echo -e "${GREEN}✓${NC}"
        fi
        return 0
    else
        echo -e "${RED}✗${NC}"
        echo -e "${YELLOW}⚠️  No keys found at ${MCP_KEY_FILE}${NC}"
        echo
        read -p "Would you like to generate new keys? (y/n) " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            generate_keys
        else
            return 1
        fi
    fi
}

generate_keys() {
    echo "🔐 Generating new MCP keys..."
    read -p "Enter your name: " name

    # Use mcp_keys.py if available
    if [ -f "mcp_keys.py" ]; then
        python3 mcp_keys.py init --server "${MCP_SERVER}" --name "${name}"
    else
        # Fallback to direct API call
        response=$(curl -s -X POST "${MCP_SERVER}/api/orchestrator/generate-keys" \
            -H "Content-Type: application/json" \
            -d "{\"client_name\": \"${name}\"}")

        if [ $? -eq 0 ]; then
            mkdir -p "${MCP_KEY_DIR}"
            chmod 700 "${MCP_KEY_DIR}"

            echo "$response" | python3 -c "
import sys, json
data = json.load(sys.stdin)
with open('${MCP_KEY_FILE}', 'w') as f:
    f.write(data['private_key'])
with open('${MCP_KEY_FILE}.pub', 'w') as f:
    f.write(data['public_key'])
"
            chmod 600 "${MCP_KEY_FILE}"
            chmod 644 "${MCP_KEY_FILE}.pub"

            echo -e "${GREEN}✓ Keys generated successfully${NC}"
        else
            echo -e "${RED}✗ Failed to generate keys${NC}"
            return 1
        fi
    fi
}

test_auth() {
    echo -n "🎫 Testing authentication... "

    if [ ! -f "${MCP_KEY_FILE}" ]; then
        echo -e "${RED}✗ No key found${NC}"
        return 1
    fi

    # Read key and escape for JSON
    private_key=$(cat "${MCP_KEY_FILE}" | python3 -c "import sys, json; print(json.dumps(sys.stdin.read()))")

    response=$(curl -s -X POST "${MCP_SERVER}/api/orchestrator/authenticate" \
        -H "Content-Type: application/json" \
        -d "{\"private_key\": ${private_key}}")

    if echo "$response" | grep -q "session_token"; then
        echo -e "${GREEN}✓${NC}"
        session_token=$(echo "$response" | python3 -c "import sys, json; print(json.load(sys.stdin)['session_token'])")
        echo -e "   Session: ${GREEN}${session_token:0:20}...${NC}"
        return 0
    else
        echo -e "${RED}✗${NC}"
        echo "   Error: $response"
        return 1
    fi
}

copy_key_to_clipboard() {
    echo -n "📋 Copying private key to clipboard... "

    if [ ! -f "${MCP_KEY_FILE}" ]; then
        echo -e "${RED}✗ No key found${NC}"
        return 1
    fi

    # Detect OS and copy accordingly
    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        cat "${MCP_KEY_FILE}" | pbcopy
        echo -e "${GREEN}✓ (macOS)${NC}"
    elif [[ "$OSTYPE" == "linux-gnu"* ]]; then
        # Linux
        if command -v xclip > /dev/null; then
            cat "${MCP_KEY_FILE}" | xclip -selection clipboard
            echo -e "${GREEN}✓ (xclip)${NC}"
        elif command -v xsel > /dev/null; then
            cat "${MCP_KEY_FILE}" | xsel --clipboard --input
            echo -e "${GREEN}✓ (xsel)${NC}"
        else
            echo -e "${YELLOW}✗ No clipboard utility found${NC}"
            echo "   Install with: sudo apt-get install xclip"
            return 1
        fi
    elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "cygwin" ]]; then
        # Windows
        cat "${MCP_KEY_FILE}" | clip
        echo -e "${GREEN}✓ (Windows)${NC}"
    else
        echo -e "${YELLOW}✗ Unsupported OS${NC}"
        return 1
    fi

    echo -e "   ${GREEN}Ready to paste in the orchestrator!${NC}"
}

open_browser() {
    url="${MCP_SERVER}/orchestrator"
    echo -n "🌐 Opening orchestrator at ${url}... "

    # Try different methods to open browser
    if [ -n "$BROWSER" ]; then
        $BROWSER "$url" 2>/dev/null &
        echo -e "${GREEN}✓${NC}"
    elif command -v xdg-open > /dev/null; then
        xdg-open "$url" 2>/dev/null &
        echo -e "${GREEN}✓${NC}"
    elif command -v open > /dev/null; then
        open "$url" 2>/dev/null &
        echo -e "${GREEN}✓${NC}"
    elif command -v start > /dev/null; then
        start "$url" 2>/dev/null &
        echo -e "${GREEN}✓${NC}"
    else
        echo -e "${YELLOW}✗${NC}"
        echo "   Please open manually: $url"
    fi
}

show_instructions() {
    echo
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo -e "${GREEN}🚀 Orchestrator Ready!${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
    echo
    echo "📝 Quick Start:"
    echo "   1. The orchestrator is now open in your browser"
    echo "   2. Your private key is in your clipboard"
    echo "   3. Paste it in the authentication box"
    echo "   4. Click 'Authenticate' to begin"
    echo
    echo "🛠️  Workflow:"
    echo "   1. Create and develop agents normally"
    echo "   2. Select agents in the orchestrator"
    echo "   3. Run tests (requires 100% coverage)"
    echo "   4. Deploy to your repository"
    echo
    echo "📁 Your key location: ${MCP_KEY_FILE}"
    echo "🔗 Orchestrator URL: ${MCP_SERVER}/orchestrator"
    echo
}

show_menu() {
    echo
    echo "📋 Additional Options:"
    echo "   1) Copy key to clipboard again"
    echo "   2) Test authentication"
    echo "   3) Generate new keys"
    echo "   4) Show key information"
    echo "   5) Open orchestrator again"
    echo "   6) Exit"
    echo
    read -p "Select option (1-6): " choice

    case $choice in
        1)
            copy_key_to_clipboard
            show_menu
            ;;
        2)
            test_auth
            show_menu
            ;;
        3)
            generate_keys
            show_menu
            ;;
        4)
            if [ -f "mcp_keys.py" ]; then
                python3 mcp_keys.py show
            else
                echo "Private key location: ${MCP_KEY_FILE}"
                echo "Public key location: ${MCP_KEY_FILE}.pub"
                ls -la "${MCP_KEY_DIR}/"
            fi
            show_menu
            ;;
        5)
            open_browser
            show_menu
            ;;
        6)
            echo -e "${GREEN}Goodbye!${NC}"
            exit 0
            ;;
        *)
            echo -e "${RED}Invalid option${NC}"
            show_menu
            ;;
    esac
}

# Main execution
main() {
    print_header

    # Run checks
    if ! check_server; then
        exit 1
    fi

    if ! check_keys; then
        echo -e "${RED}Cannot proceed without keys${NC}"
        exit 1
    fi

    if ! test_auth; then
        echo -e "${YELLOW}⚠️  Authentication test failed, but continuing...${NC}"
    fi

    # Copy key and open browser
    copy_key_to_clipboard
    open_browser

    # Show instructions
    show_instructions

    # Interactive menu
    show_menu
}

# Handle Ctrl+C gracefully
trap 'echo -e "\n${YELLOW}Interrupted${NC}"; exit 130' INT

# Run main function
main
