"""Interface registry for dependency-aware agent orchestration."""

import yaml
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, asdict
from collections import defaultdict, deque

@dataclass
class MethodSignature:
    """Method signature definition."""
    name: str
    parameters: List[Dict[str, Any]]
    returns: Optional[Dict[str, str]] = None
    docstring: Optional[str] = None

@dataclass
class ClassInterface:
    """Class interface definition."""
    name: str
    methods: List[MethodSignature]
    base_class: Optional[str] = None
    docstring: Optional[str] = None

@dataclass
class ModuleInterface:
    """Module interface definition."""
    path: str
    exports: List[Dict[str, Any]]
    dependencies: List[str]
    template_preference: Optional[str] = None
    description: Optional[str] = None

class InterfaceRegistry:
    """Central registry for module interfaces and dependencies."""

    def __init__(self, registry_path: Optional[str] = None):
        workspace_root = Path(os.environ.get("WORKSPACE_ROOT", "/workspace"))
        if registry_path:
            self.registry_path = Path(registry_path)
        else:
            self.registry_path = workspace_root / "project_interfaces.yaml"
        self.interfaces: Dict[str, ModuleInterface] = {}
        self._dependency_graph: Dict[str, Set[str]] = defaultdict(set)
        self.load_registry()

    def load_registry(self) -> None:
        """Load interface registry from YAML file."""
        if self.registry_path.exists():
            with open(self.registry_path, 'r') as f:
                data = yaml.safe_load(f)
                if data and 'modules' in data:
                    for path, module_data in data['modules'].items():
                        interface = ModuleInterface(
                            path=path,
                            exports=module_data.get('exports', []),
                            dependencies=module_data.get('dependencies', []),
                            template_preference=module_data.get('template_preference'),
                            description=module_data.get('description')
                        )
                        self.interfaces[path] = interface
                        self._dependency_graph[path] = set(module_data.get('dependencies', []))

    def save_registry(self) -> None:
        """Save interface registry to YAML file."""
        data = {
            'modules': {
                path: {
                    'exports': interface.exports,
                    'dependencies': interface.dependencies,
                    'template_preference': interface.template_preference,
                    'description': interface.description
                }
                for path, interface in self.interfaces.items()
            }
        }
        with open(self.registry_path, 'w') as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=True)

    def register_module(self, path: str, exports: List[Dict],
                       dependencies: List[str], template_preference: str = None,
                       description: str = None) -> None:
        """Register a module interface."""
        interface = ModuleInterface(
            path=path,
            exports=exports,
            dependencies=dependencies,
            template_preference=template_preference,
            description=description
        )
        self.interfaces[path] = interface
        self._dependency_graph[path] = set(dependencies)
        self.save_registry()

    def get_dependencies(self, module_path: str) -> List[str]:
        """Get dependencies for a module."""
        return self.interfaces.get(module_path, ModuleInterface(module_path, [], [])).dependencies

    def get_interface(self, module_path: str) -> Optional[ModuleInterface]:
        """Get interface for a module."""
        return self.interfaces.get(module_path)

    def get_exports(self, module_path: str) -> List[Dict]:
        """Get exports for a module."""
        interface = self.interfaces.get(module_path)
        return interface.exports if interface else []

    def get_available_classes(self, exclude_modules: List[str] = None) -> Dict[str, str]:
        """Get all available classes from registered modules."""
        exclude_modules = exclude_modules or []
        available = {}

        for path, interface in self.interfaces.items():
            if path not in exclude_modules:
                for export in interface.exports:
                    if export.get('type') == 'class':
                        available[export['name']] = path

        return available

    def get_available_functions(self, exclude_modules: List[str] = None) -> Dict[str, str]:
        """Get all available functions from registered modules."""
        exclude_modules = exclude_modules or []
        available = {}

        for path, interface in self.interfaces.items():
            if path not in exclude_modules:
                for export in interface.exports:
                    if export.get('type') == 'function':
                        available[export['name']] = path

        return available

    def validate_dependencies(self, module_path: str) -> Tuple[bool, List[str]]:
        """Validate that all dependencies are available."""
        errors = []
        dependencies = self.get_dependencies(module_path)

        for dep in dependencies:
            if dep not in self.interfaces:
                errors.append(f"Missing dependency: {dep}")

        return len(errors) == 0, errors

    def get_build_order(self) -> List[List[str]]:
        """Get build order using topological sort."""
        # Kahn's algorithm for topological sorting
        in_degree = defaultdict(int)
        graph = defaultdict(list)

        # Build graph and calculate in-degrees
        all_modules = set(self.interfaces.keys())
        for module in all_modules:
            in_degree[module] = 0

        for module, deps in self._dependency_graph.items():
            for dep in deps:
                if dep in all_modules:  # Only consider registered modules
                    graph[dep].append(module)
                    in_degree[module] += 1

        # Topological sort with levels
        levels = []
        queue = deque([module for module in all_modules if in_degree[module] == 0])

        while queue:
            current_level = []
            level_size = len(queue)

            for _ in range(level_size):
                module = queue.popleft()
                current_level.append(module)

                for dependent in graph[module]:
                    in_degree[dependent] -= 1
                    if in_degree[dependent] == 0:
                        queue.append(dependent)

            if current_level:
                levels.append(current_level)

        return levels

    def has_circular_dependencies(self) -> Tuple[bool, List[str]]:
        """Check for circular dependencies."""
        try:
            build_order = self.get_build_order()
            built_modules = {module for level in build_order for module in level}
            missing_modules = set(self.interfaces.keys()) - built_modules
            return len(missing_modules) > 0, list(missing_modules)
        except Exception:
            return True, list(self.interfaces.keys())

    def get_module_context(self, module_path: str, context_type: str = "standard") -> Dict[str, Any]:
        """Get context for a module based on its dependencies."""
        context = {
            "module_path": module_path,
            "dependencies": {},
            "available_classes": {},
            "available_functions": {},
            "template_hint": None
        }

        dependencies = self.get_dependencies(module_path)

        # Get dependency interfaces
        for dep in dependencies:
            dep_interface = self.get_interface(dep)
            if dep_interface:
                context["dependencies"][dep] = {
                    "exports": dep_interface.exports,
                    "description": dep_interface.description
                }

        # Get available classes and functions (excluding current module)
        context["available_classes"] = self.get_available_classes([module_path])
        context["available_functions"] = self.get_available_functions([module_path])

        # Template recommendation
        interface = self.get_interface(module_path)
        if interface and interface.template_preference:
            context["template_hint"] = interface.template_preference

        # Context size optimization
        if context_type == "minimal":
            context = {
                "dependencies": [dep for dep in dependencies],
                "template_hint": context.get("template_hint")
            }
        elif context_type == "compact":
            context["dependencies"] = {
                dep: f"{len(self.get_exports(dep))} exports"
                for dep in dependencies
            }

        return context

    def recommend_template(self, requirements: str, dependencies: List[str] = None) -> str:
        """Recommend template based on requirements analysis."""
        requirements_lower = requirements.lower()
        dependencies = dependencies or []

        # Simple heuristic-based recommendation (order matters!)
        if "main" in requirements_lower or "entry point" in requirements_lower:
            return "main_module"
        elif "test" in requirements_lower:
            return "test_module"
        elif "algorithm" in requirements_lower or "minimax" in requirements_lower or "ai" in requirements_lower:
            return "algorithm_module"
        elif "class" in requirements_lower and "method" in requirements_lower:
            return "class_module"
        elif "function" in requirements_lower and "utility" in requirements_lower:
            return "function_module"
        elif "class" in requirements_lower and "function" in requirements_lower:
            return "mixed_module"
        else:
            return "mixed_module"  # Default fallback