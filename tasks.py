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
def run(ctx, host="127.0.0.1", port=8000, repo=None):
    """Start the MCP server"""
    print(f"🚀 Starting server on {host}:{port}")

    # Set repository path if provided
    env_vars = {}
    if repo:
        env_vars["REPO_PATH"] = repo
        print(f"   Repository: {repo}")

    # Run server
    cmd = [sys.executable, "local_llm_mcp_server.py", "--host", host, "--port", str(port)]
    ctx.run(" ".join(cmd), env=env_vars, pty=True)


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
def validate(ctx):
    """Run schema validation"""
    print("✅ Running schema validation...")

    validator_path = SCRIPTS_DIR / "schema_validator.py"
    if not validator_path.exists():
        print(f"❌ Schema validator not found: {validator_path}")
        return

    ctx.run(f"python3 {validator_path}")


@task
def template(ctx, function_path):
    """Generate new function from Jinja2 templates (will become MCP tool)"""
    print(f"📝 Generating function template using Jinja2: {function_path}")
    print("   NOTE: This will become an MCP tool for local agent workflow")

    # Use the new template generator script
    template_generator = SCRIPTS_DIR / "template_generator.py"
    if not template_generator.exists():
        print(f"❌ Template generator not found: {template_generator}")
        return

    ctx.run(f"python3 {template_generator} {function_path}")


@task
def hook_install(ctx):
    """Install pre-commit hooks"""
    print("🪝 Installing pre-commit hooks...")

    # Create pre-commit hook
    hooks_dir = PROJECT_ROOT / ".git" / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    pre_commit_hook = hooks_dir / "pre-commit"
    hook_content = """#!/bin/bash
# Schema validation pre-commit hook

echo "Running schema validation..."
python3 scripts/schema_validator.py

if [ $? -ne 0 ]; then
    echo "❌ Schema validation failed. Commit aborted."
    exit 1
fi

echo "✅ Schema validation passed"
exit 0
"""

    pre_commit_hook.write_text(hook_content)
    pre_commit_hook.chmod(0o755)

    print(f"✅ Pre-commit hook installed: {pre_commit_hook}")


@task
def docker_build(ctx):
    """Build the Docker container with CUDA support"""
    print("🐳 Building local-llm-mcp Docker container...")
    ctx.run("docker build -t local-llm-mcp .", pty=True)


@task
def docker_run(ctx, port=8000, repo=None):
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

    cmd = f"""docker run --gpus all \
        -p {port}:8000 \
        -v {repo}:/workspace:rw \
        -v ~/models:/app/models:ro \
        -e WORKSPACE_PATH=/workspace \
        --name local-llm-mcp-server \
        --rm \
        -d local-llm-mcp"""

    result = ctx.run(cmd, hide=True)
    container_id = result.stdout.strip()[:12] if result.stdout else "unknown"

    print(f"✅ Container started: {container_id}")
    print(f"   MCP Server: http://localhost:{port}")
    print(f"   Workspace: {repo}")

    # import time
    # time.sleep(10)
    # # Verify mount
    # print(f"\n🔍 Verifying workspace mount...")
    # verify_cmd = f"docker exec {container_id} ls -la /workspace | head -5"
    # ctx.run(verify_cmd, pty=True)


@task
def docker_logs(ctx, follow=False):
    """View MCP server container logs"""
    follow_flag = "-f" if follow else ""
    ctx.run(f"docker logs {follow_flag} $(docker ps -q --filter ancestor=local-llm-mcp)")


@task
def docker_stop(ctx):
    """Stop MCP server containers"""
    print("🛑 Stopping MCP server containers...")
    ctx.run("docker stop $(docker ps -q --filter ancestor=local-llm-mcp) 2>/dev/null || true")


@task
def mcp_test(ctx, endpoint="http://localhost:8000"):
    """Test MCP server health"""
    print(f"🔍 Testing MCP server at {endpoint}")
    try:
        ctx.run(f"curl -s {endpoint}/health | python3 -m json.tool", pty=True)
        print("✅ MCP server is healthy")
    except Exception:
        print("❌ MCP server not responding")


@task
def measure_tokens(ctx, task_description="test task"):
    """Measure token usage for MCP operations"""
    import json
    import time

    import requests

    print(f"📊 Measuring tokens for: {task_description}")

    # Record start time and get baseline
    start_time = time.time()

    try:
        # Try to get token usage from MCP server
        response = requests.get("http://localhost:8000/stats", timeout=5)
        if response.status_code == 200:
            stats = response.json()
            tokens_used = stats.get("tokens_used", 0)
            print(f"   Current token count: {tokens_used}")

            # Store measurement
            measurement = {
                "task": task_description,
                "timestamp": time.time(),
                "tokens_used": tokens_used,
                "duration": time.time() - start_time,
            }

            # Append to measurements file
            measurements_file = PROJECT_ROOT / "token_measurements.json"
            measurements = []

            if measurements_file.exists():
                with open(measurements_file) as f:
                    measurements = json.load(f)

            measurements.append(measurement)

            with open(measurements_file, "w") as f:
                json.dump(measurements, f, indent=2)

            print("   Measurement saved to token_measurements.json")
        else:
            print("❌ Could not get token stats from MCP server")
    except Exception as e:
        print(f"❌ Token measurement failed: {e}")


@task
def precommit_check(ctx):
    """Check all linting without fixes"""
    print("🔍 Running all linting checks...")
    ctx.run("pre-commit run --all-files")


@task
def clean(ctx):
    """Clean up generated files and caches"""
    print("🧹 Cleaning up...")

    patterns = [
        "**/__pycache__",
        "**/*.pyc",
        "**/*.pyo",
        ".coverage",
        ".pytest_cache",
        "*.egg-info",
    ]

    for pattern in patterns:
        ctx.run(f"find . -name '{pattern}' -exec rm -rf {{}} + 2>/dev/null || true")

    # Also clean Docker containers
    ctx.run("docker stop $(docker ps -q --filter ancestor=local-llm-mcp) 2>/dev/null || true")

    print("✅ Cleanup complete")
