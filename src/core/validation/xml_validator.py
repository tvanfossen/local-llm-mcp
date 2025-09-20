"""XML Validator for Python Code Schema

This module provides validation against the XSD schema for Python code
XML representations with detailed error reporting.
"""

import logging
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ValidationError:
    """Represents a validation error"""
    level: str  # 'error', 'warning', 'info'
    message: str
    line: Optional[int] = None
    column: Optional[int] = None
    element: Optional[str] = None
    attribute: Optional[str] = None


@dataclass
class ValidationResult:
    """Result of XML validation"""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[ValidationError]
    schema_version: Optional[str] = None

    @property
    def has_errors(self) -> bool:
        return len(self.errors) > 0

    @property
    def has_warnings(self) -> bool:
        return len(self.warnings) > 0

    def get_summary(self) -> str:
        """Get a summary of validation results"""
        if self.is_valid:
            summary = "✅ Valid XML"
        else:
            summary = "❌ Invalid XML"

        if self.errors:
            summary += f" ({len(self.errors)} errors"
            if self.warnings:
                summary += f", {len(self.warnings)} warnings)"
            else:
                summary += ")"
        elif self.warnings:
            summary += f" ({len(self.warnings)} warnings)"

        return summary


class PythonCodeXMLValidator:
    """Validator for Python code XML against our schema"""

    def __init__(self, schema_path: Optional[Path] = None):
        if schema_path is None:
            # Default to schema in project
            project_root = Path(__file__).parent.parent.parent.parent
            schema_path = project_root / "src" / "schemas" / "python_code.xsd"

        self.schema_path = schema_path
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Load schema for reference (basic validation without lxml)
        try:
            self.schema_tree = ET.parse(schema_path)
            self.schema_root = self.schema_tree.getroot()
            self.logger.info(f"Loaded schema from {schema_path}")
        except Exception as e:
            self.logger.error(f"Failed to load schema: {e}")
            self.schema_tree = None
            self.schema_root = None

    def validate_xml_string(self, xml_content: str) -> ValidationResult:
        """Validate XML content string against schema"""
        errors = []
        warnings = []

        try:
            # Parse XML
            root = ET.fromstring(xml_content)
            self.logger.info(f"Successfully parsed XML, root element: {root.tag}")

            # Basic structure validation
            structure_errors = self._validate_structure(root)
            errors.extend(structure_errors)

            # Attribute validation
            attr_errors = self._validate_attributes(root)
            errors.extend(attr_errors)

            # Content validation
            content_errors = self._validate_content(root)
            errors.extend(content_errors)

            # ID uniqueness validation
            id_errors = self._validate_id_uniqueness(root)
            errors.extend(id_errors)

            is_valid = len(errors) == 0

        except ET.ParseError as e:
            errors.append(ValidationError(
                level='error',
                message=f"XML Parse Error: {e}",
                line=getattr(e, 'lineno', None),
                column=getattr(e, 'offset', None)
            ))
            is_valid = False

        except Exception as e:
            errors.append(ValidationError(
                level='error',
                message=f"Validation Error: {e}"
            ))
            is_valid = False

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            schema_version="1.0"
        )

    def validate_xml_file(self, xml_file_path: Path) -> ValidationResult:
        """Validate XML file against schema"""
        try:
            with open(xml_file_path, 'r', encoding='utf-8') as f:
                xml_content = f.read()
            return self.validate_xml_string(xml_content)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                errors=[ValidationError(
                    level='error',
                    message=f"Failed to read XML file: {e}"
                )],
                warnings=[]
            )

    def _validate_structure(self, root: ET.Element) -> List[ValidationError]:
        """Validate basic XML structure"""
        errors = []

        # Check root element
        if root.tag != 'python_file':
            errors.append(ValidationError(
                level='error',
                message=f"Root element must be 'python_file', found '{root.tag}'",
                element=root.tag
            ))

        # Check required attributes on root
        required_root_attrs = ['id', 'filepath']
        for attr in required_root_attrs:
            if attr not in root.attrib:
                errors.append(ValidationError(
                    level='error',
                    message=f"Root element missing required attribute '{attr}'",
                    element=root.tag,
                    attribute=attr
                ))

        # Check required child elements
        metadata = root.find('metadata')
        if metadata is None:
            errors.append(ValidationError(
                level='error',
                message="Missing required 'metadata' element",
                element=root.tag
            ))
        else:
            # Validate metadata structure
            required_metadata_children = ['created', 'agent_id', 'version']
            for child in required_metadata_children:
                if metadata.find(child) is None:
                    errors.append(ValidationError(
                        level='error',
                        message=f"Missing required metadata child '{child}'",
                        element='metadata'
                    ))

        return errors

    def _validate_attributes(self, root: ET.Element) -> List[ValidationError]:
        """Validate element attributes"""
        errors = []

        # Validate all elements with required attributes
        required_attrs = {
            'python_file': ['id', 'filepath'],
            'import': ['id', 'module'],
            'constant': ['id', 'name', 'value'],
            'variable': ['id', 'name'],
            'class': ['id', 'name'],
            'function': ['id', 'name'],
            'method': ['id', 'name'],
            'property': ['id', 'name'],
            'parameter': ['name']
        }

        for elem in root.iter():
            if elem.tag in required_attrs:
                for attr in required_attrs[elem.tag]:
                    if attr not in elem.attrib:
                        errors.append(ValidationError(
                            level='error',
                            message=f"Element '{elem.tag}' missing required attribute '{attr}'",
                            element=elem.tag,
                            attribute=attr
                        ))

        return errors

    def _validate_content(self, root: ET.Element) -> List[ValidationError]:
        """Validate element content"""
        errors = []

        # Validate that code blocks are not empty
        for code_block in root.iter():
            if code_block.tag in ['body', 'getter', 'setter', 'deleter']:
                if not code_block.text or not code_block.text.strip():
                    errors.append(ValidationError(
                        level='warning',
                        message=f"Code block '{code_block.tag}' is empty",
                        element=code_block.tag
                    ))

        # Validate that names follow Python naming conventions
        for elem in root.iter():
            if elem.tag in ['class', 'function', 'method', 'variable', 'constant', 'property']:
                name = elem.get('name')
                if name:
                    if not self._is_valid_python_name(name):
                        errors.append(ValidationError(
                            level='error',
                            message=f"Invalid Python name '{name}' in {elem.tag}",
                            element=elem.tag,
                            attribute='name'
                        ))

        return errors

    def _validate_id_uniqueness(self, root: ET.Element) -> List[ValidationError]:
        """Validate that all IDs are unique"""
        errors = []
        seen_ids = set()

        for elem in root.iter():
            elem_id = elem.get('id')
            if elem_id:
                if elem_id in seen_ids:
                    errors.append(ValidationError(
                        level='error',
                        message=f"Duplicate ID '{elem_id}' found in {elem.tag}",
                        element=elem.tag,
                        attribute='id'
                    ))
                else:
                    seen_ids.add(elem_id)

        return errors

    def _is_valid_python_name(self, name: str) -> bool:
        """Check if name is a valid Python identifier"""
        if not name:
            return False

        # Python identifier rules: start with letter or underscore,
        # followed by letters, digits, or underscores
        import re
        pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'

        # Allow private/dunder names
        if name.startswith('__') and name.endswith('__'):
            return True

        return bool(re.match(pattern, name))

    def validate_component_structure(self, xml_content: str) -> Tuple[bool, List[str]]:
        """Validate that XML represents a valid component structure"""
        try:
            root = ET.fromstring(xml_content)
            issues = []

            # Check if it's a valid python_file structure
            if root.tag != 'python_file':
                issues.append(f"Root must be 'python_file', not '{root.tag}'")

            # Check for circular dependencies in class inheritance
            classes = root.findall('.//class')
            class_names = {cls.get('name') for cls in classes}

            for cls in classes:
                base_classes_elem = cls.find('base_classes')
                if base_classes_elem is not None:
                    for base_class in base_classes_elem.findall('base_class'):
                        base_name = base_class.get('name')
                        if base_name in class_names:
                            # This could lead to circular inheritance
                            issues.append(f"Potential circular inheritance: {cls.get('name')} -> {base_name}")

            # Check method parameters include 'self' for instance methods
            for method in root.findall('.//method'):
                if not method.get('is_static') == 'true' and not method.get('is_class_method') == 'true':
                    params = method.find('parameters')
                    if params is not None:
                        first_param = params.find('parameter')
                        if first_param is None or first_param.get('name') != 'self':
                            issues.append(f"Instance method '{method.get('name')}' should have 'self' as first parameter")

            return len(issues) == 0, issues

        except ET.ParseError as e:
            return False, [f"XML parsing error: {e}"]
        except Exception as e:
            return False, [f"Validation error: {e}"]

    def get_schema_info(self) -> Dict[str, Any]:
        """Get information about the loaded schema"""
        if not self.schema_root:
            return {"error": "Schema not loaded"}

        return {
            "schema_path": str(self.schema_path),
            "target_namespace": self.schema_root.get('targetNamespace'),
            "loaded": self.schema_root is not None,
            "root_element": "python_file",
            "version": "1.0"
        }


class ValidationReporter:
    """Helper class for reporting validation results"""

    @staticmethod
    def format_validation_result(result: ValidationResult, verbose: bool = False) -> str:
        """Format validation result for display"""
        lines = []

        lines.append(result.get_summary())

        if result.errors:
            lines.append(f"\n❌ Errors ({len(result.errors)}):")
            for i, error in enumerate(result.errors, 1):
                lines.append(f"  {i}. {error.message}")
                if verbose and error.element:
                    lines.append(f"     Element: {error.element}")
                if verbose and error.attribute:
                    lines.append(f"     Attribute: {error.attribute}")

        if result.warnings:
            lines.append(f"\n⚠️  Warnings ({len(result.warnings)}):")
            for i, warning in enumerate(result.warnings, 1):
                lines.append(f"  {i}. {warning.message}")

        return "\n".join(lines)

    @staticmethod
    def log_validation_result(result: ValidationResult, logger_instance: Optional[logging.Logger] = None):
        """Log validation result"""
        if logger_instance is None:
            logger_instance = logger

        if result.is_valid:
            logger_instance.info(f"✅ XML validation passed")
        else:
            logger_instance.error(f"❌ XML validation failed with {len(result.errors)} errors")

        for error in result.errors:
            logger_instance.error(f"  - {error.message}")

        for warning in result.warnings:
            logger_instance.warning(f"  - {warning.message}")


def validate_python_xml(xml_content: str) -> ValidationResult:
    """Convenience function for validating Python XML content"""
    validator = PythonCodeXMLValidator()
    return validator.validate_xml_string(xml_content)