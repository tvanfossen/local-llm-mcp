"""Base operation class for file metadata operations"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Tuple
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class BaseMetadataOperation(ABC):
    """Base class for all metadata operations with common functionality"""

    def __init__(self, workspace_root: str = "/workspace"):
        """Initialize with workspace root path"""
        self.workspace_root = Path(workspace_root)

    def _load_or_create_metadata(self, path: str) -> Tuple[Dict[str, Any], Path]:
        """Load existing metadata or create new structure

        Returns:
            Tuple of (metadata_dict, meta_file_path)
        """
        if path.startswith('/'):
            path = path[1:]

        meta_dir = self.workspace_root / ".meta"
        meta_file = meta_dir / f"{path}.json"

        # Ensure parent directories exist
        meta_file.parent.mkdir(parents=True, exist_ok=True)

        if meta_file.exists():
            try:
                with open(meta_file, 'r', encoding='utf-8') as f:
                    metadata = json.load(f)
                logger.info(f"📖 Loaded existing metadata: {meta_file}")
                return metadata, meta_file
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load existing metadata {meta_file}: {e}")
                # Fall through to create new metadata

        # Create new metadata structure
        metadata = self._create_base_metadata_structure(path)
        logger.info(f"📝 Creating new metadata structure: {meta_file}")
        return metadata, meta_file

    def _create_base_metadata_structure(self, path: str) -> Dict[str, Any]:
        """Create base metadata structure for new files"""
        return {
            "file_info": {
                "name": Path(path).name,
                "description": "",
                "author": "Local LLM Agent",
                "version": "1.0.0"
            },
            "imports": [],
            "classes": [],
            "functions": [],
            "constants": [],
            "variables": [],
            "metadata": {
                "file_type": "python_module",
                "complexity": "low",
                "test_coverage_target": 80,
                "linting_rules": ["flake8", "pylint"],
                "dependencies": []
            }
        }

    def _save_metadata(self, metadata: Dict[str, Any], meta_file: Path) -> Dict[str, Any]:
        """Save metadata to file with validation"""
        try:
            # Add/update metadata header
            metadata["_metadata"] = {
                "generated_for": meta_file.name[:-5],  # Remove .json extension
                "format": "json",
                "description": f"Generated JSON metadata for {meta_file.name[:-5]}"
            }

            # Write formatted JSON
            final_json = json.dumps(metadata, indent=2, ensure_ascii=False)

            with open(meta_file, 'w', encoding='utf-8') as f:
                f.write(final_json)

            return {
                "success": True,
                "message": f"Metadata updated: {meta_file}",
                "path": str(meta_file),
                "size": len(final_json)
            }

        except Exception as e:
            logger.error(f"Failed to save metadata {meta_file}: {e}")
            return {
                "success": False,
                "error": f"Failed to save metadata: {str(e)}"
            }

    def _validate_required_args(self, arguments: Dict[str, Any], required_args: list) -> Tuple[bool, str]:
        """Validate that required arguments are present

        Returns:
            Tuple of (is_valid, error_message)
        """
        for arg in required_args:
            if arg not in arguments or arguments[arg] is None:
                return False, f"Required argument '{arg}' missing"
        return True, ""

    @abstractmethod
    async def execute(self, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the operation - must be implemented by subclasses"""
        pass