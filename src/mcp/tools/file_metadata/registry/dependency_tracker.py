"""Dependency tracker for file metadata - merged interface registry functionality"""

import logging
import yaml
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

logger = logging.getLogger(__name__)


class DependencyTracker:
    """Track dependencies and exports for metadata files"""

    def __init__(self, workspace_root: str = "/workspace"):
        """Initialize dependency tracker"""
        self.workspace_root = Path(workspace_root)
        self.registry_file = self.workspace_root / ".meta" / "registry.yaml"

    def _load_registry(self) -> Dict[str, Any]:
        """Load registry from file or create empty structure"""
        if not self.registry_file.exists():
            return {"modules": {}, "exports": {}, "dependencies": {}}

        try:
            with open(self.registry_file, 'r', encoding='utf-8') as f:
                return yaml.safe_load(f) or {"modules": {}, "exports": {}, "dependencies": {}}
        except Exception as e:
            logger.warning(f"Failed to load registry: {e}")
            return {"modules": {}, "exports": {}, "dependencies": {}}

    def _save_registry(self, registry: Dict[str, Any]) -> bool:
        """Save registry to file"""
        try:
            # Ensure directory exists
            self.registry_file.parent.mkdir(parents=True, exist_ok=True)

            with open(self.registry_file, 'w', encoding='utf-8') as f:
                yaml.dump(registry, f, default_flow_style=False, indent=2)
            return True
        except Exception as e:
            logger.error(f"Failed to save registry: {e}")
            return False

    def update_from_metadata(self, path: str, metadata: Dict[str, Any]) -> bool:
        """Update registry from metadata file"""
        try:
            registry = self._load_registry()

            # Extract dependencies from imports
            dependencies = []
            for import_def in metadata.get("imports", []):
                module = import_def.get("module", "")
                if module:
                    dependencies.append(module)

            # Extract exports from classes and functions
            exports = {"classes": [], "functions": []}

            for cls in metadata.get("classes", []):
                exports["classes"].append({
                    "name": cls.get("name", ""),
                    "description": cls.get("description", "")
                })

            for func in metadata.get("functions", []):
                exports["functions"].append({
                    "name": func.get("name", ""),
                    "description": func.get("description", "")
                })

            # Update registry
            registry["modules"][path] = {
                "dependencies": dependencies,
                "exports": exports,
                "description": metadata.get("file_info", {}).get("description", ""),
                "last_updated": "auto-generated"
            }

            return self._save_registry(registry)

        except Exception as e:
            logger.error(f"Failed to update registry for {path}: {e}")
            return False

    def get_dependencies(self, path: str) -> List[str]:
        """Get dependencies for a module"""
        registry = self._load_registry()
        module_info = registry.get("modules", {}).get(path, {})
        return module_info.get("dependencies", [])

    def get_exports(self, path: str) -> Dict[str, List]:
        """Get exports for a module"""
        registry = self._load_registry()
        module_info = registry.get("modules", {}).get(path, {})
        return module_info.get("exports", {"classes": [], "functions": []})

    def get_build_order(self) -> List[str]:
        """Get build order for all modules based on dependencies"""
        registry = self._load_registry()
        modules = registry.get("modules", {})

        # Simple topological sort
        visited = set()
        temp_visited = set()
        result = []

        def visit(module: str):
            if module in temp_visited:
                # Circular dependency detected
                return
            if module in visited:
                return

            temp_visited.add(module)

            # Visit dependencies first
            for dep in modules.get(module, {}).get("dependencies", []):
                if dep in modules:  # Only consider internal dependencies
                    visit(dep)

            temp_visited.remove(module)
            visited.add(module)
            result.append(module)

        for module in modules:
            if module not in visited:
                visit(module)

        return result

    def has_circular_dependencies(self) -> Tuple[bool, List[str]]:
        """Check for circular dependencies"""
        registry = self._load_registry()
        modules = registry.get("modules", {})

        visited = set()
        rec_stack = set()
        circular_modules = []

        def has_cycle(module: str) -> bool:
            visited.add(module)
            rec_stack.add(module)

            for dep in modules.get(module, {}).get("dependencies", []):
                if dep in modules:  # Only check internal dependencies
                    if dep not in visited:
                        if has_cycle(dep):
                            return True
                    elif dep in rec_stack:
                        circular_modules.append(dep)
                        return True

            rec_stack.remove(module)
            return False

        for module in modules:
            if module not in visited:
                if has_cycle(module):
                    return True, circular_modules

        return False, []

    def get_available_classes(self, exclude_modules: List[str] = None) -> Dict[str, List]:
        """Get all available classes from registry"""
        if exclude_modules is None:
            exclude_modules = []

        registry = self._load_registry()
        modules = registry.get("modules", {})

        all_classes = {}
        for module_path, module_info in modules.items():
            if module_path not in exclude_modules:
                classes = module_info.get("exports", {}).get("classes", [])
                if classes:
                    all_classes[module_path] = classes

        return all_classes

    def get_available_functions(self, exclude_modules: List[str] = None) -> Dict[str, List]:
        """Get all available functions from registry"""
        if exclude_modules is None:
            exclude_modules = []

        registry = self._load_registry()
        modules = registry.get("modules", {})

        all_functions = {}
        for module_path, module_info in modules.items():
            if module_path not in exclude_modules:
                functions = module_info.get("exports", {}).get("functions", [])
                if functions:
                    all_functions[module_path] = functions

        return all_functions