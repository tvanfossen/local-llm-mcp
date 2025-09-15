"""JSON File Manager - Manages structured Python file representations

Responsibilities:
- Maintain JSON representations of Python files
- Handle incremental updates to code elements
- Render Python files using Jinja2 templates
- Preserve file structure during updates
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from jinja2 import Environment, FileSystemLoader

from src.schemas.files.python_file import (
    PythonClass,
    PythonDataclass,
    PythonFile,
    PythonFunction,
    PythonImport,
    PythonMethod,
    PythonVariable,
    create_class_from_dict,
    create_dataclass_from_dict,
    create_empty_python_file,
    create_function_from_dict,
)


class JsonFileManager:
    """Manages JSON-based file representations and template rendering"""

    def __init__(self, workspace_path: str, templates_path: str = "templates"):
        self.workspace_path = Path(workspace_path)
        self.templates_path = Path(templates_path)
        self.logger = logging.getLogger(__name__)

        # Initialize Jinja2 environment
        self.jinja_env = Environment(
            loader=FileSystemLoader(self.templates_path),
            trim_blocks=True,
            lstrip_blocks=True,
        )

        # Ensure .meta directory exists
        self.meta_path = self.workspace_path / ".meta"
        self.meta_path.mkdir(exist_ok=True)

    async def load_file_json(self, filename: str) -> Optional[PythonFile]:
        """Load existing JSON representation of file"""
        json_path = self.meta_path / f"{filename}.json"

        if not json_path.exists():
            self.logger.info(f"No JSON metadata found for {filename}")
            return None

        try:
            with open(json_path) as f:
                data = json.load(f)

            # Reconstruct PythonFile from JSON data
            python_file = PythonFile(
                filename=data.get("filename", filename),
                module_docstring=data.get("module_docstring"),
            )

            # Load imports
            for import_data in data.get("imports", []):
                python_file.imports.append(PythonImport(**import_data))

            # Load variables
            for var_data in data.get("variables", []):
                python_file.variables.append(PythonVariable(**var_data))

            # Load dataclasses
            for dc_data in data.get("dataclasses", []):
                python_file.dataclasses.append(create_dataclass_from_dict(dc_data))

            # Load classes
            for class_data in data.get("classes", []):
                python_file.classes.append(create_class_from_dict(class_data))

            # Load functions
            for func_data in data.get("functions", []):
                python_file.functions.append(create_function_from_dict(func_data))

            self.logger.info(f"Loaded JSON metadata for {filename}")
            return python_file

        except Exception as e:
            self.logger.error(f"Failed to load JSON metadata for {filename}: {e}")
            return None

    async def save_file_json(self, python_file: PythonFile) -> bool:
        """Save JSON representation of file"""
        json_path = self.meta_path / f"{python_file.filename}.json"

        try:
            with open(json_path, "w") as f:
                json.dump(python_file.to_dict(), f, indent=2)

            self.logger.info(f"Saved JSON metadata for {python_file.filename}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to save JSON metadata for {python_file.filename}: {e}")
            return False

    async def update_element(self, filename: str, element_type: str, element_data: dict[str, Any]) -> bool:
        """Update a single element (function/class/dataclass) in the file"""
        try:
            # Load existing file or create new one
            python_file = await self.load_file_json(filename)
            if python_file is None:
                python_file = create_empty_python_file(filename)
                self.logger.info(f"Created new file structure for {filename}")

            # Update the appropriate element
            if element_type == "function":
                function = create_function_from_dict(element_data)
                python_file.add_or_update_function(function)
                self.logger.info(f"Updated function '{function.name}' in {filename}")

            elif element_type == "class":
                python_class = create_class_from_dict(element_data)
                python_file.add_or_update_class(python_class)
                self.logger.info(f"Updated class '{python_class.name}' in {filename}")

            elif element_type == "dataclass":
                dataclass = create_dataclass_from_dict(element_data)
                python_file.add_or_update_dataclass(dataclass)
                self.logger.info(f"Updated dataclass '{dataclass.name}' in {filename}")

            elif element_type == "method":
                # For updating a method within a class
                class_name = element_data.get("class_name")
                method_data = element_data.get("method_data")

                if not class_name or not method_data:
                    raise ValueError("Method update requires 'class_name' and 'method_data'")

                # Find the class
                target_class = python_file.get_class(class_name)
                if target_class is None:
                    raise ValueError(f"Class '{class_name}' not found in {filename}")

                # Update the method
                method = PythonMethod(**method_data)
                target_class.add_or_update_method(method)
                self.logger.info(f"Updated method '{method.name}' in class '{class_name}' in {filename}")

            elif element_type == "import":
                import_stmt = PythonImport(**element_data)
                python_file.add_import(import_stmt)
                self.logger.info(f"Added import '{import_stmt.to_import_statement()}' to {filename}")

            elif element_type == "variable":
                variable = PythonVariable(**element_data)
                # Remove existing variable with same name
                python_file.variables = [v for v in python_file.variables if v.name != variable.name]
                python_file.variables.append(variable)
                self.logger.info(f"Updated variable '{variable.name}' in {filename}")

            else:
                raise ValueError(f"Unknown element type: {element_type}")

            # Save updated JSON representation
            await self.save_file_json(python_file)

            # Render the updated file
            await self.render_file(python_file)

            return True

        except Exception as e:
            self.logger.error(f"Failed to update element in {filename}: {e}")
            return False

    async def render_file(self, python_file: PythonFile) -> bool:
        """Render Python file from JSON using Jinja2 template"""
        try:
            # Get template
            template = self.jinja_env.get_template("python_file.j2")

            # Render file content
            rendered_content = template.render(python_file.to_dict())

            # Write to actual Python file
            output_path = self.workspace_path / python_file.filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, "w") as f:
                f.write(rendered_content)

            self.logger.info(f"Rendered {python_file.filename} ({len(rendered_content)} chars)")
            return True

        except Exception as e:
            self.logger.error(f"Failed to render {python_file.filename}: {e}")
            return False

    async def get_file_structure(self, filename: str) -> Optional[dict[str, Any]]:
        """Get the current structure of a file for context"""
        python_file = await self.load_file_json(filename)
        if python_file is None:
            return None

        return {
            "filename": python_file.filename,
            "functions": [{"name": f.name, "docstring": f.docstring} for f in python_file.functions],
            "classes": [
                {
                    "name": c.name,
                    "docstring": c.docstring,
                    "methods": [{"name": m.name, "docstring": m.docstring} for m in c.methods],
                }
                for c in python_file.classes
            ],
            "dataclasses": [{"name": dc.name, "docstring": dc.docstring} for dc in python_file.dataclasses],
            "imports": [import_stmt.to_import_statement() for import_stmt in python_file.imports],
        }

    async def delete_element(self, filename: str, element_type: str, element_name: str) -> bool:
        """Delete an element from the file"""
        try:
            python_file = await self.load_file_json(filename)
            if python_file is None:
                return False

            if element_type == "function":
                python_file.functions = [f for f in python_file.functions if f.name != element_name]
            elif element_type == "class":
                python_file.classes = [c for c in python_file.classes if c.name != element_name]
            elif element_type == "dataclass":
                python_file.dataclasses = [dc for dc in python_file.dataclasses if dc.name != element_name]
            else:
                raise ValueError(f"Unknown element type: {element_type}")

            # Save and render
            await self.save_file_json(python_file)
            await self.render_file(python_file)

            self.logger.info(f"Deleted {element_type} '{element_name}' from {filename}")
            return True

        except Exception as e:
            self.logger.error(f"Failed to delete element from {filename}: {e}")
            return False
