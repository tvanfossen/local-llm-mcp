"""Code Generation Tool - Generate Python code from JSON metadata

This tool focuses solely on code generation using Jinja2 templates,
providing better error handling and debugging capabilities.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List

from jinja2 import Environment, FileSystemLoader
from src.core.utils.utils import create_mcp_response, handle_exception
from src.schemas.files.python_file import (
    PythonFile, PythonClass, PythonMethod, PythonFunction,
    PythonImport, PythonVariable, create_empty_python_file
)

logger = logging.getLogger(__name__)


class CodeGenerator:
    """Handles Python code generation from JSON metadata"""

    def __init__(self, templates_path: str = "templates"):
        self.templates_path = Path(templates_path)
        logger.info(f"Initializing CodeGenerator with templates path: {templates_path}")

        # Initialize Jinja2 environment with extensive debugging
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_path),
            trim_blocks=True,
            lstrip_blocks=True,
            autoescape=False,  # Required for code generation
        )

        # Enable template debugging
        self.jinja_env.globals['debug'] = True

    def convert_operations_to_body(self, operations: List[Dict[str, Any]]) -> str:
        """Convert operations array to Python method/function body"""
        logger.debug(f"Converting {len(operations)} operations to body")

        if not operations:
            return "pass"

        body_lines = []
        for i, operation in enumerate(operations):
            op_type = operation.get('type', '')
            logger.debug(f"Processing operation {i}: {op_type}")

            if op_type == 'return':
                value = operation.get('value', '')
                if value:
                    body_lines.append(f"return {value}")
                else:
                    body_lines.append("return")
            elif op_type == 'assignment':
                target = operation.get('target', '')
                value = operation.get('value', '')
                if target and value:
                    body_lines.append(f"{target} = {value}")
            elif op_type == 'validation':
                condition = operation.get('condition', '')
                exception_type = operation.get('exception_type', 'ValueError')
                exception_message = operation.get('exception_message', 'Invalid input')
                if condition:
                    body_lines.append(f"if not ({condition}):")
                    body_lines.append(f"    raise {exception_type}('{exception_message}')")
            elif op_type == 'function_call':
                function_name = operation.get('function_name', '')
                arguments = operation.get('arguments', [])
                target = operation.get('target', '')
                if function_name:
                    args_str = ", ".join(str(arg) for arg in arguments)
                    call_str = f"{function_name}({args_str})"
                    if target:
                        body_lines.append(f"{target} = {call_str}")
                    else:
                        body_lines.append(call_str)
            elif op_type == 'pass':
                body_lines.append("pass")
            else:
                # Default case for unknown operation types
                description = operation.get('description', f'TODO: Implement {op_type}')
                body_lines.append(f"# {description}")
                if not body_lines or body_lines[-1] != "pass":
                    body_lines.append("pass")

        result = '\n'.join(body_lines) if body_lines else "pass"
        logger.debug(f"Generated body ({len(result)} chars): {result[:100]}...")
        return result

    def json_to_python_file(self, json_obj: Dict[str, Any], filename: str) -> PythonFile:
        """Convert JSON structure to PythonFile schema object with extensive validation"""
        logger.info(f"Converting JSON to PythonFile for {filename}")
        python_file = create_empty_python_file(filename)

        try:
            # Extract module docstring from metadata or file_info
            metadata = json_obj.get('metadata', {})
            file_info = json_obj.get('file_info', {})
            description = metadata.get('description', '') or file_info.get('description', '')
            if description:
                python_file.module_docstring = description.strip()
                logger.debug(f"Set module docstring: {description[:50]}...")

            # Process imports with validation
            imports = json_obj.get('imports', [])
            logger.debug(f"Processing {len(imports)} imports")

            if imports and isinstance(imports, list):
                for i, import_data in enumerate(imports):
                    if isinstance(import_data, dict):
                        module = import_data.get('module', '')
                        items = import_data.get('items', '')
                        imported_items = import_data.get('imported_items', '')

                        if module:
                            # Handle both 'items' and 'imported_items' field formats
                            items_source = items or imported_items
                            items_list = [item.strip() for item in items_source.split(',')] if items_source else []

                            import_obj = PythonImport(module=module, items=items_list)
                            python_file.add_import(import_obj)
                            logger.debug(f"Added import {i}: {import_obj.to_import_statement()}")

            # Process functions with detailed logging
            functions = json_obj.get('functions', [])
            logger.debug(f"Processing {len(functions)} functions")

            if functions and isinstance(functions, list):
                for i, func_data in enumerate(functions):
                    if isinstance(func_data, dict):
                        name = func_data.get('name', f'unknown_function_{i}')
                        logger.debug(f"Processing function {i}: {name}")

                        # Extract parameters with validation
                        parameters = []
                        params_data = func_data.get('parameters', [])
                        if params_data and isinstance(params_data, list):
                            for param_data in params_data:
                                if isinstance(param_data, dict):
                                    param_name = param_data.get('name', '')
                                    param_type = param_data.get('type', '')
                                    param_default = param_data.get('default', '')

                                    if param_name:
                                        param_dict = {"name": param_name}
                                        if param_type:
                                            param_dict["type"] = param_type
                                        if param_default:
                                            param_dict["default"] = param_default
                                        parameters.append(param_dict)

                        # Extract return type
                        return_type = None
                        returns_data = func_data.get('returns', {})
                        if returns_data and isinstance(returns_data, dict):
                            return_type = returns_data.get('type')

                        # Convert operations to body
                        operations = func_data.get('operations', [])
                        body = self.convert_operations_to_body(operations) if operations else "pass"

                        function = PythonFunction(
                            name=name,
                            docstring=func_data.get('docstring'),
                            parameters=parameters,
                            return_type=return_type,
                            body=body
                        )
                        python_file.add_or_update_function(function)
                        logger.debug(f"Added function: {name} with {len(parameters)} params")

            # Process classes with detailed logging
            classes = json_obj.get('classes', [])
            logger.debug(f"Processing {len(classes)} classes")

            if classes and isinstance(classes, list):
                for i, class_data in enumerate(classes):
                    if isinstance(class_data, dict):
                        class_name = class_data.get('name', f'UnknownClass_{i}')
                        logger.debug(f"Processing class {i}: {class_name}")

                        docstring = class_data.get('docstring', '')
                        methods = []

                        # Process methods
                        methods_data = class_data.get('methods', [])
                        if methods_data and isinstance(methods_data, list):
                            for j, method_data in enumerate(methods_data):
                                if isinstance(method_data, dict):
                                    method_name = method_data.get('name', f'unknown_method_{j}')
                                    logger.debug(f"Processing method {j}: {method_name}")

                                    # Extract method parameters
                                    method_params = []
                                    params_data = method_data.get('parameters', [])
                                    if params_data and isinstance(params_data, list):
                                        for param_data in params_data:
                                            if isinstance(param_data, dict):
                                                param_name = param_data.get('name', '')
                                                param_type = param_data.get('type', '')
                                                param_default = param_data.get('default', '')

                                                if param_name:
                                                    param_dict = {"name": param_name}
                                                    if param_type:
                                                        param_dict["type"] = param_type
                                                    if param_default:
                                                        param_dict["default"] = param_default
                                                    method_params.append(param_dict)

                                    # Extract method return type
                                    method_return_type = None
                                    returns_data = method_data.get('returns', {})
                                    if returns_data and isinstance(returns_data, dict):
                                        method_return_type = returns_data.get('type')

                                    # Convert operations to method body
                                    operations = method_data.get('operations', [])
                                    method_body = self.convert_operations_to_body(operations) if operations else "pass"

                                    method = PythonMethod(
                                        name=method_name,
                                        docstring=method_data.get('docstring'),
                                        parameters=method_params,
                                        return_type=method_return_type,
                                        body=method_body
                                    )
                                    methods.append(method)
                                    logger.debug(f"Added method: {method_name} with {len(method_params)} params")

                        python_class = PythonClass(
                            name=class_name,
                            docstring=docstring,
                            base_classes=[],
                            methods=methods
                        )
                        python_file.add_or_update_class(python_class)
                        logger.debug(f"Added class: {class_name} with {len(methods)} methods")

            logger.info(f"Successfully converted JSON to PythonFile: {len(python_file.imports)} imports, {len(python_file.functions)} functions, {len(python_file.classes)} classes")
            return python_file

        except Exception as e:
            logger.error(f"Error converting JSON to PythonFile for {filename}: {e}")
            raise

    def validate_template_data(self, template_data: Dict[str, Any]) -> bool:
        """Validate template data structure before rendering"""
        logger.info("Validating template data structure")

        # Check imports have required methods
        imports = template_data.get('imports', [])
        for i, import_obj in enumerate(imports):
            if not hasattr(import_obj, 'to_import_statement'):
                logger.error(f"Import {i} missing to_import_statement method: {type(import_obj)}")
                return False
            try:
                import_statement = import_obj.to_import_statement()
                logger.debug(f"Import {i} statement: {import_statement}")
            except Exception as e:
                logger.error(f"Import {i} to_import_statement() failed: {e}")
                return False

        # Check functions have required fields
        functions = template_data.get('functions', [])
        for i, func in enumerate(functions):
            if not hasattr(func, 'body'):
                logger.error(f"Function {i} missing body field: {func.name if hasattr(func, 'name') else 'unknown'}")
                return False

        # Check classes and methods
        classes = template_data.get('classes', [])
        for i, cls in enumerate(classes):
            if not hasattr(cls, 'methods'):
                logger.error(f"Class {i} missing methods field: {cls.name if hasattr(cls, 'name') else 'unknown'}")
                return False

            for j, method in enumerate(cls.methods):
                if not hasattr(method, 'body'):
                    logger.error(f"Method {j} in class {i} missing body field: {method.name if hasattr(method, 'name') else 'unknown'}")
                    return False

        logger.info("Template data validation passed")
        return True

    async def generate_python_code(self, metadata_path: str, output_path: str = None) -> Dict[str, Any]:
        """Generate Python code from JSON metadata with extensive error handling"""
        try:
            metadata_file = Path(metadata_path)
            if not metadata_file.exists():
                return create_mcp_response(False, f"Metadata file not found: {metadata_path}")

            logger.info(f"Loading metadata from: {metadata_file}")

            # Read and parse JSON metadata
            with open(metadata_file, 'r', encoding='utf-8') as f:
                json_content = f.read()

            try:
                metadata_obj = json.loads(json_content)
                logger.debug(f"Parsed JSON metadata with keys: {list(metadata_obj.keys())}")
            except json.JSONDecodeError as e:
                logger.error(f"Invalid JSON in metadata file: {e}")
                return create_mcp_response(False, f"Invalid JSON: {e}")

            # Convert to PythonFile schema
            filename = metadata_file.stem.replace('.json', '')
            if filename.endswith('.py'):
                filename = filename[:-3] + '.py'
            else:
                filename = filename + '.py'

            logger.info(f"Converting metadata to PythonFile schema for: {filename}")
            python_file_obj = self.json_to_python_file(metadata_obj, filename)

            # Prepare template data
            template_data = {
                'module_docstring': python_file_obj.module_docstring,
                'imports': python_file_obj.imports,
                'variables': python_file_obj.variables,
                'classes': python_file_obj.classes,
                'functions': python_file_obj.functions,
                'dataclasses': python_file_obj.dataclasses
            }

            logger.info(f"Template data prepared: {len(template_data['imports'])} imports, {len(template_data['functions'])} functions, {len(template_data['classes'])} classes")

            # Validate template data
            if not self.validate_template_data(template_data):
                return create_mcp_response(False, "Template data validation failed")

            # Load and render template
            try:
                template = self.jinja_env.get_template("python_file.j2")
                logger.info("Template loaded successfully")
            except Exception as e:
                logger.error(f"Failed to load template: {e}")
                return create_mcp_response(False, f"Template loading failed: {e}")

            try:
                python_code = template.render(template_data)
                logger.info(f"Template rendered successfully: {len(python_code)} characters")
                logger.debug(f"Generated code preview: {python_code[:200]}...")
            except Exception as e:
                logger.error(f"Template rendering failed: {e}")
                logger.error(f"Template data keys: {list(template_data.keys())}")
                return create_mcp_response(False, f"Template rendering failed: {e}")

            # Optionally write to file
            if output_path:
                output_file = Path(output_path)
                output_file.parent.mkdir(parents=True, exist_ok=True)

                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(python_code)

                logger.info(f"Generated code written to: {output_file}")

            # Create custom response with data
            return {
                "content": [{
                    "type": "text",
                    "text": f"✅ Successfully generated {len(python_code)} characters of Python code",
                    "data": {
                        "code": python_code,
                        "metadata_file": str(metadata_file),
                        "output_file": str(output_path) if output_path else None,
                        "size": len(python_code),
                        "imports_count": len(template_data['imports']),
                        "functions_count": len(template_data['functions']),
                        "classes_count": len(template_data['classes'])
                    }
                }],
                "isError": False
            }

        except Exception as e:
            logger.error(f"Code generation failed: {e}")
            return handle_exception(e, "code_generation")


# Global code generator instance
_code_generator = CodeGenerator()


async def code_generation_tool(arguments: Dict[str, Any]) -> Dict[str, Any]:
    """Code Generation Tool Handler

    Actions:
        generate_python: Generate Python code from JSON metadata
        preview_code: Generate code without writing to file
        validate_metadata: Validate JSON metadata structure
    """
    try:
        action = arguments.get("action")
        if not action:
            return create_mcp_response(False, "Missing 'action' parameter. Available: generate_python, preview_code, validate_metadata")

        if action == "generate_python":
            metadata_path = arguments.get("metadata_path")
            output_path = arguments.get("output_path")

            if not metadata_path:
                return create_mcp_response(False, "Missing 'metadata_path' parameter for generate_python action")

            return await _code_generator.generate_python_code(metadata_path, output_path)

        elif action == "preview_code":
            metadata_path = arguments.get("metadata_path")

            if not metadata_path:
                return create_mcp_response(False, "Missing 'metadata_path' parameter for preview_code action")

            # Generate without writing to file
            return await _code_generator.generate_python_code(metadata_path)

        elif action == "validate_metadata":
            metadata_path = arguments.get("metadata_path")

            if not metadata_path:
                return create_mcp_response(False, "Missing 'metadata_path' parameter for validate_metadata action")

            # TODO: Implement metadata validation
            return create_mcp_response(False, "validate_metadata action not yet implemented")

        else:
            return create_mcp_response(False, f"Unknown action: {action}. Available: generate_python, preview_code, validate_metadata")

    except Exception as e:
        return handle_exception(e, "code_generation_tool")