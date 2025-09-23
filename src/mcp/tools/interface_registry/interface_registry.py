"""MCP tool for interface registry operations."""

from typing import Dict, Any, List, Optional
from .registry import InterfaceRegistry

# Global registry instance
_registry = None

def get_registry() -> InterfaceRegistry:
    """Get or create global interface registry."""
    global _registry
    if _registry is None:
        _registry = InterfaceRegistry()
    return _registry

async def interface_registry_tool(args: Dict[str, Any]) -> Dict[str, Any]:
    """
    MCP tool for interface registry operations.

    Operations:
    - register_module: Register a module interface
    - get_dependencies: Get dependencies for a module
    - get_interface: Get interface for a module
    - get_context: Get context for a module
    - validate_dependencies: Validate module dependencies
    - get_build_order: Get build order for all modules
    - recommend_template: Recommend template for requirements
    - get_available_classes: Get all available classes
    - get_available_functions: Get all available functions
    """
    operation = args.get("operation")
    if not operation:
        return {
            "success": False,
            "error": "operation parameter required"
        }

    registry = get_registry()

    try:
        if operation == "register_module":
            path = args.get("module_path")
            exports = args.get("exports", [])
            dependencies = args.get("dependencies", [])
            template_preference = args.get("template_preference")
            description = args.get("description")

            registry.register_module(path, exports, dependencies, template_preference, description)
            return {
                "success": True,
                "message": f"Module {path} registered successfully",
                "module_path": path
            }

        elif operation == "get_dependencies":
            path = args.get("module_path")
            dependencies = registry.get_dependencies(path)
            return {
                "success": True,
                "module_path": path,
                "dependencies": dependencies
            }

        elif operation == "get_interface":
            path = args.get("module_path")
            interface = registry.get_interface(path)
            if interface:
                return {
                    "success": True,
                    "module_path": path,
                    "interface": {
                        "exports": interface.exports,
                        "dependencies": interface.dependencies,
                        "template_preference": interface.template_preference,
                        "description": interface.description
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"Interface not found for module: {path}"
                }

        elif operation == "get_context":
            path = args.get("module_path")
            context_type = args.get("context_type", "standard")
            context = registry.get_module_context(path, context_type)
            return {
                "success": True,
                "module_path": path,
                "context": context
            }

        elif operation == "validate_dependencies":
            path = args.get("module_path")
            is_valid, errors = registry.validate_dependencies(path)
            return {
                "success": True,
                "module_path": path,
                "is_valid": is_valid,
                "errors": errors
            }

        elif operation == "get_build_order":
            build_order = registry.get_build_order()
            has_circular, circular_modules = registry.has_circular_dependencies()
            return {
                "success": True,
                "data": {
                    "build_order": build_order,
                    "has_circular_dependencies": has_circular,
                    "circular_modules": circular_modules
                }
            }

        elif operation == "recommend_template":
            requirements = args.get("requirements", "")
            dependencies = args.get("dependencies", [])
            template = registry.recommend_template(requirements, dependencies)
            return {
                "success": True,
                "requirements": requirements,
                "recommended_template": template
            }

        elif operation == "get_available_classes":
            exclude_modules = args.get("exclude_modules", [])
            classes = registry.get_available_classes(exclude_modules)
            return {
                "success": True,
                "available_classes": classes
            }

        elif operation == "get_available_functions":
            exclude_modules = args.get("exclude_modules", [])
            functions = registry.get_available_functions(exclude_modules)
            return {
                "success": True,
                "available_functions": functions
            }

        else:
            return {
                "success": False,
                "error": f"Unknown operation: {operation}"
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Error in interface registry operation '{operation}': {str(e)}"
        }