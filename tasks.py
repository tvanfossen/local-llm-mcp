"""Invoke tasks for Local LLM MCP Server development workflow

Responsibilities:
- Development server management (run, reload, test)
- Schema validation and template generation
- Self-maintenance automation
- Integration testing and deployment
"""

import sys
from pathlib import Path

from invoke import task

# Project paths
PROJECT_ROOT = Path(__file__).parent
SRC_DIR = PROJECT_ROOT / "src"
SCRIPTS_DIR = PROJECT_ROOT / "scripts"





@task
def test(ctx, coverage=True, verbose=False):
    """Run tests with optional coverage"""
    print("🧪 Running tests...")

    cmd = ["python3", "-m", "pytest", "src/"]

    if coverage:
        cmd.extend(["--cov=src", "--cov-report=term-missing"])

    if verbose:
        cmd.append("-v")
    else:
        cmd.append("--tb=short")

    ctx.run(" ".join(cmd))



@task
def build(ctx):
    """Build the Docker container with CUDA support"""
    print("🐳 Building local-llm-mcp Docker container...")
    #TODO add a --clean argument that ensures no cache is used
    ctx.run("docker build -t local-llm-mcp .", pty=True)


@task
def run(ctx, port=8000, repo=None):
    """Run the MCP server in Docker with workspace mount"""
    import os

    if repo is None:
        repo = str(PROJECT_ROOT)
        print(f"Using current directory as repo: {repo}")
    else:
        # Ensure repo path is absolute
        repo = os.path.abspath(os.path.expanduser(repo))
        if not os.path.exists(repo):
            print(f"❌ Repository path does not exist: {repo}")
            return

    print(f"🚀 Starting MCP server in Docker on port {port}")
    print(f"   Workspace mount: {repo} -> /workspace")

    # Stop any existing containers
    ctx.run("docker stop $(docker ps -q --filter ancestor=local-llm-mcp) 2>/dev/null || true")

    # Run container with GPU and workspace mount
    # CRITICAL: Ensure repo is mounted at /workspace with read-write permissions
    # TEMPORARILY REMOVING --user flag to test if that's causing startup issues
    # uid = os.getuid()
    # gid = os.getgid()

    # Stop and remove any existing containers with the same name
    ctx.run("docker stop local-llm-mcp-server 2>/dev/null || true")
    ctx.run("docker rm local-llm-mcp-server 2>/dev/null || true")

    cmd = f"""docker run --gpus all \
        -p {port}:8000 \
        -v {repo}:/workspace:rw \
        -v ~/models:/app/models:ro \
        -e WORKSPACE_PATH=/workspace \
        --name local-llm-mcp-server \
        -d local-llm-mcp"""

    result = ctx.run(cmd, hide=True)
    container_id = result.stdout.strip()[:12] if result.stdout else "unknown"

    print(f"✅ Container started: {container_id}")
    print(f"   MCP Server: http://localhost:{port}")
    print(f"   Workspace: {repo}")

    # Wait a moment and check if container is still running
    import time
    time.sleep(2)

    # Check container status
    status_result = ctx.run(f"docker ps -q --filter name=local-llm-mcp-server", hide=True)
    if not status_result.stdout.strip():
        print("⚠️  Container appears to have stopped. Use 'inv docker-logs' to check logs.")
    else:
        print("✅ Container is running successfully")

    # import time
    # time.sleep(10)
    # # Verify mount
    # print(f"\n🔍 Verifying workspace mount...")
    # verify_cmd = f"docker exec {container_id} ls -la /workspace | head -5"
    # ctx.run(verify_cmd, pty=True)


@task
def logs(ctx, follow=False, tail=None, all_logs=True):
    """View MCP server container logs - defaults to ALL logs unless tail specified"""
    follow_flag = "-f" if follow else ""

    # Only use tail if explicitly specified and not requesting all logs
    if tail and not all_logs:
        tail_flag = f"--tail {tail}"
    else:
        tail_flag = ""  # Get ALL logs by default
        print("📜 Retrieving ALL container logs...")

    # Try to get logs from named container first
    try:
        ctx.run(f"docker logs {follow_flag} {tail_flag} local-llm-mcp-server")
    except Exception:
        # Fallback to finding by image
        print("Named container not found, trying to find by image...")
        try:
            result = ctx.run("docker ps -aq --filter ancestor=local-llm-mcp | head -1", hide=True)
            if result.stdout.strip():
                container_id = result.stdout.strip()
                print(f"Found container: {container_id}")
                ctx.run(f"docker logs {follow_flag} {tail_flag} {container_id}")
            else:
                # Check stopped containers
                result = ctx.run("docker ps -aq --filter ancestor=local-llm-mcp --filter status=exited | head -1", hide=True)
                if result.stdout.strip():
                    container_id = result.stdout.strip()
                    print(f"Found stopped container: {container_id}")
                    ctx.run(f"docker logs {follow_flag} {tail_flag} {container_id}")
                else:
                    print("❌ No local-llm-mcp containers found")
        except Exception as e:
            print(f"❌ Error retrieving logs: {e}")


@task
def stop(ctx):
    """Stop MCP server containers"""
    print("🛑 Stopping MCP server containers...")
    # Stop by name first
    ctx.run("docker stop local-llm-mcp-server 2>/dev/null || true")
    # Fallback to stop by image
    ctx.run("docker stop $(docker ps -q --filter ancestor=local-llm-mcp) 2>/dev/null || true")
    # Clean up stopped containers
    ctx.run("docker rm local-llm-mcp-server 2>/dev/null || true")


@task
def mcp_test(ctx, endpoint="http://localhost:8000"):
    """Test MCP server health"""
    print(f"🔍 Testing MCP server at {endpoint}")
    try:
        ctx.run(f"curl -s {endpoint}/health | python3 -m json.tool", pty=True)
        print("✅ MCP server is healthy")
    except Exception:
        print("❌ MCP server not responding")

