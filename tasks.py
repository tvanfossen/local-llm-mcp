"""Invoke tasks for local-llm-mcp project
Handles Docker build and run operations with direct repository integration
Workspace: Container /workspace -> Host repository (direct mount)
"""

from pathlib import Path

from invoke import task


@task
def build(ctx):
    """Build the Docker container with CUDA support"""
    print("Building local-llm-mcp Docker container...")
    ctx.run("docker build -t local-llm-mcp .", pty=True)
    print("Build complete!")


@task
def run(ctx, port=8000, models_path=None, state_path=None, repo=None):
    """Run the local-llm-mcp container with direct repository integration

    Args:
        port: Port to expose (default: 8000)
        models_path: Path to models directory (default: ~/models)
        state_path: Path to state directory (default: ./state)
        repo: Path to target repository (required for direct file access)
    """
    # Validate repository path
    if repo is None:
        print("❌ Error: --repo parameter is required")
        print("Example: inv run --repo=/home/user/my-project")
        print("         inv run --repo=~/Projects/my-app")
        return

    # Resolve and validate paths
    paths = _resolve_container_paths(models_path, state_path, repo)
    if not _validate_paths(paths):
        return

    # Prepare repository for MCP agent integration
    _prepare_repository(paths["repo"])

    # Start container
    _start_container(ctx, port, paths)


def _resolve_container_paths(models_path, state_path, repo):
    """Resolve all required paths for container mounting"""
    return {
        "models": Path(models_path or "~/models").expanduser().resolve(),
        "state": Path(state_path or "./state").resolve(),
        "repo": Path(repo).expanduser().resolve(),
    }


def _validate_paths(paths):
    """Validate all paths exist or can be created"""
    for path_type, path in paths.items():
        if path_type == "repo":
            if not _validate_repository_path(path):
                return False
        else:
            _ensure_directory_exists(path)
    return True


def _validate_repository_path(repo_path):
    """Validate repository path exists and is a directory"""
    if not repo_path.exists():
        print(f"❌ Repository path does not exist: {repo_path}")
        return False

    if not repo_path.is_dir():
        print(f"❌ Repository path is not a directory: {repo_path}")
        return False

    return True


def _ensure_directory_exists(path):
    """Create directory if it doesn't exist"""
    path.mkdir(parents=True, exist_ok=True)


def _prepare_repository(repo_path):
    """Prepare repository for MCP agent integration"""
    mcp_agents_dir = repo_path / ".mcp-agents"
    mcp_agents_dir.mkdir(exist_ok=True)

    # Create .gitignore entry for MCP agents directory
    gitignore_path = repo_path / ".gitignore"
    gitignore_entry = ".mcp-agents/"

    _ensure_gitignore_entry(gitignore_path, gitignore_entry)

    print(f"📁 Repository prepared: {repo_path}")
    print(f"🤖 Agent metadata: {mcp_agents_dir}")


def _ensure_gitignore_entry(gitignore_path, entry):
    """Ensure .gitignore contains the MCP agents directory"""
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if entry not in content:
            _append_gitignore_entry(gitignore_path, entry)
    else:
        _create_gitignore_with_entry(gitignore_path, entry)


def _append_gitignore_entry(gitignore_path, entry):
    """Append entry to existing .gitignore"""
    with open(gitignore_path, "a") as f:
        f.write(f"\n# MCP Agent metadata\n{entry}\n")
    print(f"✅ Added {entry} to .gitignore")


def _create_gitignore_with_entry(gitignore_path, entry):
    """Create new .gitignore with MCP entry"""
    gitignore_path.write_text(f"# MCP Agent metadata\n{entry}\n")
    print(f"✅ Created .gitignore with {entry}")


def _start_container(ctx, port, paths):
    """Start the Docker container with proper volume mounts"""
    print("Starting local-llm-mcp server...")
    print(f"Port: {port}")
    print(f"Models: {paths['models']}")
    print(f"State: {paths['state']}")
    print(f"Repository: {paths['repo']}")
    print("GPU: Enabled")

    # Build Docker command with proper volume mounts
    cmd = _build_docker_command(port, paths)
    ctx.run(cmd, pty=True)


def _build_docker_command(port, paths):
    """Build the Docker run command with all volume mounts"""
    return (
        f"docker run --gpus all "
        f"-p {port}:8000 "
        f"-v {paths['models']}:/app/models "
        f"-v {paths['state']}:/app/state "
        f"-v {paths['repo']}:/workspace "
        f"local-llm-mcp"
    )


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
def dev(ctx, repo=None):
    """Development mode - build and run with immediate feedback"""
    if repo is None:
        print("❌ Error: --repo parameter is required for dev mode")
        return

    build(ctx)
    run(ctx, repo=repo)


@task
def backup_agents(ctx, repo=None):
    """Backup agent state from repository .mcp-agents directory"""
    import datetime

    if repo is None:
        print("❌ Error: --repo parameter is required")
        return

    repo_path = Path(repo).expanduser().resolve()
    mcp_agents_dir = repo_path / ".mcp-agents"

    if not mcp_agents_dir.exists():
        print(f"❌ No .mcp-agents directory found in {repo_path}")
        return

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir = f"backups/agents_{timestamp}"

    print(f"Creating backup: {backup_dir}")
    ctx.run(f"mkdir -p {backup_dir}")

    # Backup MCP agents directory from repository
    ctx.run(f"cp -r {mcp_agents_dir} {backup_dir}/mcp-agents")
    print("✅ Agent metadata backed up")

    # Backup local state if it exists
    if Path("./state").exists():
        ctx.run(f"cp -r ./state {backup_dir}/")
        print("✅ Local state backed up")

    print(f"Backup complete: {backup_dir}")


@task
def restore_agents(ctx, backup_dir, repo=None):
    """Restore agent state to repository .mcp-agents directory"""
    if repo is None:
        print("❌ Error: --repo parameter is required")
        return

    backup_path = Path(backup_dir)
    if not backup_path.exists():
        print(f"❌ Backup directory not found: {backup_dir}")
        return

    repo_path = Path(repo).expanduser().resolve()

    # Stop container if running
    ctx.run("docker stop $(docker ps -q --filter ancestor=local-llm-mcp) 2>/dev/null || true", pty=True)

    # Restore MCP agents to repository
    agents_backup = backup_path / "mcp-agents"
    if agents_backup.exists():
        mcp_agents_dir = repo_path / ".mcp-agents"
        ctx.run(f"rm -rf {mcp_agents_dir} && cp -r {agents_backup} {mcp_agents_dir}")
        print("✅ Agent metadata restored to repository")

    # Restore local state
    state_backup = backup_path / "state"
    if state_backup.exists():
        ctx.run(f"rm -rf ./state && cp -r {state_backup} ./state")
        print("✅ Local state restored")

    print("Restore complete! Start server with 'inv run --repo=<path>'")


@task
def status(ctx, repo=None):
    """Show agent persistence status for repository"""
    print("📊 Agent Persistence Status")
    print("=" * 40)

    if repo:
        _show_repository_status(repo)
    else:
        print("❌ No repository specified")
        print("Usage: inv status --repo=/path/to/repo")

    # Show local state status
    _show_local_status()


def _show_repository_status(repo):
    """Show status of repository MCP integration"""
    repo_path = Path(repo).expanduser().resolve()

    if not repo_path.exists():
        print(f"❌ Repository not found: {repo_path}")
        return

    mcp_agents_dir = repo_path / ".mcp-agents"
    print(f"Repository: {repo_path}")
    print(f"MCP Agents Directory: {'✅ Exists' if mcp_agents_dir.exists() else '❌ Missing'}")

    if mcp_agents_dir.exists():
        agent_info = _get_repository_agent_info(mcp_agents_dir)
        print(f"Agent Workspaces: {agent_info['count']}")

        # Show registry status
        registry_file = mcp_agents_dir / "registry.json"
        if registry_file.exists():
            registry_info = _get_registry_info(registry_file)
            print(f"Registry: ✅ {registry_info['agent_count']} agents registered")
        else:
            print("Registry: ❌ No registry.json found")


def _show_local_status():
    """Show local state directory status"""
    print("\nLocal State:")
    state_dir = Path("./state")
    print(f"State Directory: {'✅ Exists' if state_dir.exists() else '❌ Missing'}")

    if state_dir.exists():
        agents_file = state_dir / "agents.json"
        if agents_file.exists():
            local_info = _get_local_agent_info(agents_file)
            print(f"Local Registry: {local_info['count']}")


def _get_repository_agent_info(mcp_agents_dir):
    """Get agent information from repository"""
    try:
        workspace_dirs = [d for d in mcp_agents_dir.iterdir() if d.is_dir() and d.name != "registry.json"]
        return {"count": len(workspace_dirs)}
    except Exception:
        return {"count": "Error reading directory"}


def _get_registry_info(registry_file):
    """Get information from registry.json"""
    try:
        import json

        with open(registry_file) as f:
            data = json.load(f)
        return {"agent_count": len(data.get("agents", []))}
    except Exception:
        return {"agent_count": "Error reading registry"}


def _get_local_agent_info(agents_file):
    """Get local agent information"""
    try:
        import json

        with open(agents_file) as f:
            data = json.load(f)
        return {"count": len(data.get("agents", []))}
    except Exception:
        return {"count": "Error reading file"}
