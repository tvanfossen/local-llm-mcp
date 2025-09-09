"""Delete File MCP Tool

Responsibilities:
- Delete files and directories with workspace safety checks
- Support both single files and batch operations
- Provide confirmation for destructive operations
- Return standardized MCP response format
"""

import logging
import shutil
from pathlib import Path
from typing import Any

from src.core.config.manager.manager import ConfigManager

logger = logging.getLogger(__name__)


def _create_success(text: str) -> dict[str, Any]:
    """Create success response format"""
    return {"content": [{"type": "text", "text": text}], "isError": False}


def _create_error(title: str, message: str) -> dict[str, Any]:
    """Create error response format"""
    return {"content": [{"type": "text", "text": f"❌ **{title}:** {message}"}], "isError": True}


def _handle_exception(e: Exception, context: str) -> dict[str, Any]:
    """Handle exceptions with consistent error format"""
    return {"content": [{"type": "text", "text": f"❌ **{context} Error:** {str(e)}"}], "isError": True}


async def delete_file(args: dict[str, Any]) -> dict[str, Any]:
    """Delete a file with workspace safety checks"""
    try:
        file_path = args.get("file_path")
        force = args.get("force", False)
        
        if not file_path:
            return _create_error("Missing Parameter", "File path is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Resolve and validate path
        resolved_path = _resolve_and_validate_path(file_path, workspace_root)
        if isinstance(resolved_path, dict):  # Error response
            return resolved_path
        
        # Check if file exists
        if not resolved_path.exists():
            return _create_error("File Not Found", f"File does not exist: {file_path}")
        
        # Safety check for important files
        if not force and _is_important_file(resolved_path):
            return _create_error(
                "Safety Check", 
                f"File appears to be important: {file_path}. Use 'force: true' to confirm deletion."
            )
        
        # Get file info before deletion
        file_info = _get_file_deletion_info(resolved_path)
        
        # Perform deletion
        try:
            if resolved_path.is_file():
                resolved_path.unlink()
            elif resolved_path.is_dir():
                shutil.rmtree(resolved_path)
            else:
                return _create_error("Unknown File Type", f"Cannot determine file type: {file_path}")
        except Exception as e:
            return _create_error("Deletion Failed", f"Cannot delete file: {str(e)}")
        
        # Format success response
        success_msg = _format_deletion_success(file_info, "deleted")
        return _create_success(success_msg)
        
    except Exception as e:
        logger.error(f"Failed to delete file: {e}")
        return _handle_exception(e, "Delete File")


async def delete_multiple_files(args: dict[str, Any]) -> dict[str, Any]:
    """Delete multiple files with workspace safety checks"""
    try:
        file_paths = args.get("file_paths", [])
        force = args.get("force", False)
        continue_on_error = args.get("continue_on_error", True)
        
        if not file_paths:
            return _create_error("Missing Parameter", "File paths list is required")
        
        if not isinstance(file_paths, list):
            return _create_error("Invalid Parameter", "File paths must be a list")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        deletion_results = {
            "successful": [],
            "failed": [],
            "skipped": [],
            "total_size": 0
        }
        
        # Process each file
        for file_path in file_paths:
            try:
                # Resolve and validate path
                resolved_path = _resolve_and_validate_path(file_path, workspace_root)
                if isinstance(resolved_path, dict):  # Error response
                    deletion_results["failed"].append({
                        "path": file_path,
                        "error": resolved_path["content"][0]["text"]
                    })
                    if not continue_on_error:
                        break
                    continue
                
                # Check if file exists
                if not resolved_path.exists():
                    deletion_results["skipped"].append({
                        "path": file_path,
                        "reason": "File does not exist"
                    })
                    continue
                
                # Safety check
                if not force and _is_important_file(resolved_path):
                    deletion_results["skipped"].append({
                        "path": file_path,
                        "reason": "Important file (use force=true)"
                    })
                    continue
                
                # Get file info and delete
                file_info = _get_file_deletion_info(resolved_path)
                
                if resolved_path.is_file():
                    resolved_path.unlink()
                elif resolved_path.is_dir():
                    shutil.rmtree(resolved_path)
                
                deletion_results["successful"].append({
                    "path": file_path,
                    "info": file_info
                })
                deletion_results["total_size"] += file_info["size"]
                
            except Exception as e:
                deletion_results["failed"].append({
                    "path": file_path,
                    "error": str(e)
                })
                if not continue_on_error:
                    break
        
        # Format results
        result_msg = _format_batch_deletion_results(deletion_results)
        return _create_success(result_msg)
        
    except Exception as e:
        logger.error(f"Failed to delete multiple files: {e}")
        return _handle_exception(e, "Delete Multiple Files")


async def delete_directory(args: dict[str, Any]) -> dict[str, Any]:
    """Delete a directory and all its contents"""
    try:
        directory_path = args.get("directory_path")
        force = args.get("force", False)
        recursive = args.get("recursive", False)
        
        if not directory_path:
            return _create_error("Missing Parameter", "Directory path is required")
        
        config_manager = ConfigManager()
        workspace_root = config_manager.system.get_workspace_root()
        
        # Resolve and validate path
        resolved_path = _resolve_and_validate_path(directory_path, workspace_root)
        if isinstance(resolved_path, dict):  # Error response
            return resolved_path
        
        # Check if directory exists
        if not resolved_path.exists():
            return _create_error("Directory Not Found", f"Directory does not exist: {directory_path}")
        
        if not resolved_path.is_dir():
            return _create_error("Not a Directory", f"Path is not a directory: {directory_path}")
        
        # Check if directory is empty
        try:
            contents = list(resolved_path.iterdir())
            is_empty = len(contents) == 0
        except Exception:
            contents = []
            is_empty = True
        
        if not is_empty and not recursive:
            return _create_error(
                "Directory Not Empty", 
                f"Directory contains {len(contents)} items. Use 'recursive: true' to delete all contents."
            )
        
        # Safety check for important directories
        if not force and _is_important_directory(resolved_path):
            return _create_error(
                "Safety Check", 
                f"Directory appears to be important: {directory_path}. Use 'force: true' to confirm deletion."
            )
        
        # Get directory info before deletion
        dir_info = _get_directory_deletion_info(resolved_path)
        
        # Perform deletion
        try:
            shutil.rmtree(resolved_path)
        except Exception as e:
            return _create_error("Deletion Failed", f"Cannot delete directory: {str(e)}")
        
        # Format success response
        success_msg = _format_directory_deletion_success(dir_info)
        return _create_success(success_msg)
        
    except Exception as e:
        logger.error(f"Failed to delete directory: {e}")
        return _handle_exception(e, "Delete Directory")


def _resolve_and_validate_path(file_path: str, workspace_root: Path) -> Path | dict[str, Any]:
    """Resolve path and validate it's within workspace"""
    try:
        path = Path(file_path)
        
        # Convert relative paths to absolute within workspace
        if not path.is_absolute():
            path = workspace_root / path
        
        # Resolve to handle . and .. components
        resolved_path = path.resolve()
        workspace_resolved = workspace_root.resolve()
        
        # Security check: ensure path is within workspace
        try:
            resolved_path.relative_to(workspace_resolved)
        except ValueError:
            return _create_error(
                "Security Error", 
                f"File access denied: {file_path} is outside workspace ({workspace_root})"
            )
        
        return resolved_path
        
    except Exception as e:
        return _create_error("Path Error", f"Invalid file path: {file_path} - {str(e)}")


def _is_important_file(path: Path) -> bool:
    """Check if file appears to be important and should require force deletion"""
    important_patterns = {
        # Configuration files
        ".env", ".env.local", ".env.production", 
        "config.json", "config.yaml", "config.yml",
        "pyproject.toml", "package.json", "Cargo.toml",
        "requirements.txt", "poetry.lock", "Pipfile.lock",
        
        # Documentation
        "README.md", "README.txt", "LICENSE", "CHANGELOG.md",
        
        # Build/deployment files
        "Dockerfile", "docker-compose.yml", "Makefile",
        ".gitignore", ".gitattributes",
        
        # Database files
        "*.db", "*.sqlite", "*.sqlite3"
    }
    
    filename = path.name.lower()
    
    # Check exact matches
    if filename in [p.lower() for p in important_patterns]:
        return True
    
    # Check pattern matches
    import fnmatch
    for pattern in important_patterns:
        if fnmatch.fnmatch(filename, pattern.lower()):
            return True
    
    return False


def _is_important_directory(path: Path) -> bool:
    """Check if directory appears to be important"""
    important_dirs = {
        ".git", ".github", ".vscode", ".idea",
        "node_modules", "venv", ".env", "__pycache__",
        "dist", "build", "target", ".next", ".nuxt"
    }
    
    return path.name.lower() in [d.lower() for d in important_dirs]


def _get_file_deletion_info(path: Path) -> dict:
    """Get information about file being deleted"""
    try:
        stat = path.stat()
        return {
            "name": path.name,
            "path": str(path),
            "size": stat.st_size,
            "is_directory": path.is_dir(),
            "modified": stat.st_mtime
        }
    except Exception:
        return {
            "name": path.name,
            "path": str(path),
            "size": 0,
            "is_directory": path.is_dir(),
            "modified": 0
        }


def _get_directory_deletion_info(path: Path) -> dict:
    """Get information about directory being deleted"""
    try:
        total_size = 0
        file_count = 0
        dir_count = 0
        
        for item in path.rglob("*"):
            if item.is_file():
                file_count += 1
                try:
                    total_size += item.stat().st_size
                except Exception:
                    pass
            elif item.is_dir():
                dir_count += 1
        
        return {
            "name": path.name,
            "path": str(path),
            "total_size": total_size,
            "file_count": file_count,
            "dir_count": dir_count
        }
    except Exception:
        return {
            "name": path.name,
            "path": str(path),
            "total_size": 0,
            "file_count": 0,
            "dir_count": 0
        }


def _format_deletion_success(file_info: dict, action: str) -> str:
    """Format success message for file deletion"""
    import datetime
    
    modified_time = datetime.datetime.fromtimestamp(file_info["modified"])
    time_str = modified_time.strftime("%Y-%m-%d %H:%M:%S")
    
    file_type = "directory" if file_info["is_directory"] else "file"
    size_str = _format_file_size(file_info["size"])
    
    return (
        f"🗑️ **File {action.title()} Successfully**\n\n"
        f"📄 **Name:** `{file_info['name']}`\n"
        f"📁 **Path:** `{file_info['path']}`\n"
        f"📋 **Type:** {file_type}\n"
        f"📊 **Size:** {size_str}\n"
        f"📅 **Last Modified:** {time_str}"
    )


def _format_directory_deletion_success(dir_info: dict) -> str:
    """Format success message for directory deletion"""
    total_items = dir_info["file_count"] + dir_info["dir_count"]
    size_str = _format_file_size(dir_info["total_size"])
    
    return (
        f"🗑️ **Directory Deleted Successfully**\n\n"
        f"📁 **Name:** `{dir_info['name']}`\n"
        f"📍 **Path:** `{dir_info['path']}`\n"
        f"📊 **Contents:** {dir_info['file_count']} files, {dir_info['dir_count']} directories ({total_items} total)\n"
        f"💾 **Total Size:** {size_str}"
    )


def _format_batch_deletion_results(results: dict) -> str:
    """Format results for batch deletion"""
    successful_count = len(results["successful"])
    failed_count = len(results["failed"])
    skipped_count = len(results["skipped"])
    total_size = results["total_size"]
    
    summary = (
        f"🗑️ **Batch Deletion Complete**\n\n"
        f"📊 **Summary:**\n"
        f"   ✅ Successfully deleted: {successful_count}\n"
        f"   ❌ Failed: {failed_count}\n"
        f"   ⏭️ Skipped: {skipped_count}\n"
        f"   💾 Total size deleted: {_format_file_size(total_size)}"
    )
    
    # Add details for failed deletions
    if results["failed"]:
        summary += "\n\n❌ **Failed Deletions:**"
        for item in results["failed"][:5]:  # Limit to first 5
            summary += f"\n   • `{item['path']}`: {item['error']}"
        if len(results["failed"]) > 5:
            summary += f"\n   • ... and {len(results['failed']) - 5} more"
    
    # Add details for skipped files
    if results["skipped"]:
        summary += "\n\n⏭️ **Skipped Files:**"
        for item in results["skipped"][:5]:  # Limit to first 5
            summary += f"\n   • `{item['path']}`: {item['reason']}"
        if len(results["skipped"]) > 5:
            summary += f"\n   • ... and {len(results['skipped']) - 5} more"
    
    return summary


def _format_file_size(size_bytes: int) -> str:
    """Format file size in human readable format"""
    if size_bytes == 0:
        return "0 bytes"
    
    size_names = ["bytes", "KB", "MB", "GB", "TB"]
    import math
    i = int(math.floor(math.log(size_bytes, 1024)))
    p = math.pow(1024, i)
    s = round(size_bytes / p, 2)
    
    if s.is_integer():
        s = int(s)
    
    return f"{s} {size_names[i]}"