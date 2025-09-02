"""Invoke tasks for local-llm-mcp project
Handles Docker build and run operations with persistent agent storage
"""

import os

from invoke import task


@task
def build(ctx):
    """Build the Docker container with CUDA support"""
    print("Building local-llm-mcp Docker container...")
    ctx.run("docker build -t local-llm-mcp .", pty=True)
    print("Build complete!")


@task
def run(ctx, port=8000, models_path=None, state_path=None, workspaces_path=None, project_path=None):
    """Run the local-llm-mcp container with persistent agent storage

    Args:
        port: Port to expose (default: 8000)
        models_path: Path to models directory (default: ~/models)
        state_path: Path to state directory (default: ./state)
        workspaces_path: Path to workspaces directory (default: ./workspaces)
    """
    if models_path is None:
        models_path = os.path.expanduser("~/models")

    if state_path is None:
        state_path = os.path.abspath("./state")

    if workspaces_path is None:
        workspaces_path = os.path.abspath("./workspaces")

    # Ensure all directories exist
    os.makedirs(models_path, exist_ok=True)
    os.makedirs(state_path, exist_ok=True)
    os.makedirs(workspaces_path, exist_ok=True)

    print("Starting local-llm-mcp server...")
    print(f"Port: {port}")
    print(f"Models: {models_path}")
    print(f"State: {state_path}")
    print(f"Workspaces: {workspaces_path}")
    print("GPU: Enabled")

    # Mount models, state, and workspaces directories
    cmd = (
        f"docker run --gpus all "
        f"-p {port}:8000 "
        f"-v {models_path}:/app/models "
        f"-v {state_path}:/app/state "
        f"-v {workspaces_path}:/app/workspaces "
        f"-v ~/{project_path}:/host/repo:rw "
        f"local-llm-mcp"
    )

    ctx.run(cmd, pty=True)


@task
def logs(ctx, follow=False):
    """View container logs"""
    follow_flag = "-f" if follow else ""
    ctx.run(f"docker logs {follow_flag} $(docker ps -q --filter ancestor=local-llm-mcp)", pty=True)


@task
def stop(ctx):
    """Stop running containers"""
    print("Stopping local-llm-mcp containers...")
    ctx.run("docker stop $(docker ps -q --filter ancestor=local-llm-mcp)", pty=True)


@task
def shell(ctx):
    """Open shell in running container"""
    ctx.run("docker exec -it $(docker ps -q --filter ancestor=local-llm-mcp) /bin/bash", pty=True)


@task
def clean(ctx):
    """Clean up Docker images and containers"""
    print("Cleaning up Docker resources...")
    # Stop containers
    ctx.run("docker stop $(docker ps -q --filter ancestor=local-llm-mcp) 2>/dev/null || true", pty=True)
    # Remove containers
    ctx.run("docker rm $(docker ps -aq --filter ancestor=local-llm-mcp) 2>/dev/null || true", pty=True)
    # Remove image
    ctx.run("docker rmi local-llm-mcp 2>/dev/null || true", pty=True)
    print("Cleanup complete!")


@task
def test(ctx):
    """Run a quick test of the containerized server"""
    print("Testing server health...")
    ctx.run("curl -s http://localhost:8000/health | python3 -m json.tool", pty=True)


@task
def dev(ctx):
    """Development mode - build and run with immediate feedback"""
    build(ctx)
    run(ctx)


@task
def backup_agents(ctx):
    """Backup agent state and workspaces"""
    import datetime

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backups/agents_{timestamp}"

    print(f"Creating backup: {backup_dir}")
    ctx.run(f"mkdir -p {backup_dir}")

    if os.path.exists("./state"):
        ctx.run(f"cp -r ./state {backup_dir}/")
        print("✅ State backed up")

    if os.path.exists("./workspaces"):
        ctx.run(f"cp -r ./workspaces {backup_dir}/")
        print("✅ Workspaces backed up")

    print(f"Backup complete: {backup_dir}")


@task
def restore_agents(ctx, backup_dir):
    """Restore agent state from backup"""
    if not os.path.exists(backup_dir):
        print(f"❌ Backup directory not found: {backup_dir}")
        return

    # Stop container if running
    ctx.run("docker stop $(docker ps -q --filter ancestor=local-llm-mcp) 2>/dev/null || true", pty=True)

    state_backup = os.path.join(backup_dir, "state")
    workspaces_backup = os.path.join(backup_dir, "workspaces")

    if os.path.exists(state_backup):
        ctx.run(f"rm -rf ./state && cp -r {state_backup} ./state")
        print("✅ State restored")

    if os.path.exists(workspaces_backup):
        ctx.run(f"rm -rf ./workspaces && cp -r {workspaces_backup} ./workspaces")
        print("✅ Workspaces restored")

    print("Restore complete! Start server with 'inv run'")


@task
def status(ctx):
    """Show agent persistence status"""
    print("📊 Agent Persistence Status")
    print("=" * 40)

    # Check directory existence
    directory_status = _check_directories()
    _print_directory_status(directory_status)

    # Check agent data if available
    if directory_status["state_exists"]:
        agent_info = _get_agent_information()
        _print_agent_information(agent_info)

    if directory_status["workspaces_exists"]:
        workspace_info = _get_workspace_information()
        _print_workspace_information(workspace_info)


def _check_directories():
    """Check if required directories exist"""
    return {"state_exists": os.path.exists("./state"), "workspaces_exists": os.path.exists("./workspaces")}


def _print_directory_status(directory_status):
    """Print directory existence status"""
    state_status = "✅ Exists" if directory_status["state_exists"] else "❌ Missing"
    workspaces_status = "✅ Exists" if directory_status["workspaces_exists"] else "❌ Missing"

    print(f"State directory: {state_status}")
    print(f"Workspaces directory: {workspaces_status}")


def _get_agent_information():
    """Get information about saved agents"""
    agents_file = "./state/agents.json"
    if not os.path.exists(agents_file):
        return {"count": "No agents.json file", "error": True}

    try:
        import json

        with open(agents_file) as f:
            data = json.load(f)
        agent_count = len(data.get("agents", []))
        return {"count": agent_count, "error": False}
    except Exception:
        return {"count": "Error reading file", "error": True}


def _print_agent_information(agent_info):
    """Print agent information"""
    print(f"Saved agents: {agent_info['count']}")


def _get_workspace_information():
    """Get information about workspace directories"""
    try:
        workspace_dirs = [d for d in os.listdir("./workspaces") if os.path.isdir(f"./workspaces/{d}")]
        return {"dirs": workspace_dirs, "count": len(workspace_dirs)}
    except Exception:
        return {"dirs": [], "count": 0}


def _print_workspace_information(workspace_info):
    """Print workspace information"""
    count = workspace_info["count"]
    dirs = workspace_info["dirs"]

    print(f"Agent workspaces: {count}")
    if dirs:
        displayed_dirs = dirs[:5]
        suffix = "..." if len(dirs) > 5 else ""
        print("Workspace IDs:", ", ".join(displayed_dirs) + suffix)
