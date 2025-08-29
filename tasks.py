"""
Invoke tasks for local-llm-mcp project
Handles Docker build and run operations
"""

from invoke import task
import os


@task
def build(ctx):
    """Build the Docker container with CUDA support"""
    print("Building local-llm-mcp Docker container...")
    ctx.run("docker build -t local-llm-mcp .", pty=True)
    print("Build complete!")


@task
def run(ctx, port=8000, models_path=None):
    """
    Run the local-llm-mcp container
    
    Args:
        port: Port to expose (default: 8000)
        models_path: Path to models directory (default: ~/models)
    """
    if models_path is None:
        models_path = os.path.expanduser("~/models")
    
    # Ensure models directory exists
    os.makedirs(models_path, exist_ok=True)
    
    print(f"Starting local-llm-mcp server...")
    print(f"Port: {port}")
    print(f"Models: {models_path}")
    print(f"GPU: Enabled")
    
    cmd = f"docker run --gpus all -p {port}:8000 -v {models_path}:/app/models local-llm-mcp"
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