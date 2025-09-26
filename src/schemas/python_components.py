"""Python Component Data Classes for JSON Schema

This module provides data classes that correspond to the JSON schema for
representing Python code components in a structured format.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Any, Dict
from enum import Enum


class ComponentType(Enum):
    """Types of Python components"""
    FILE = "file"
    CLASS = "class"
    FUNCTION = "function"
    METHOD = "method"
    PROPERTY = "property"
    VARIABLE = "variable"
    CONSTANT = "constant"
    IMPORT = "import"


@dataclass
class PythonComponent:
    """Base class for all Python components with tracking"""
    id: str  # Unique identifier for tracking
    name: str
    docstring: Optional[str] = None
    line_start: Optional[int] = None  # For mapping to actual file
    line_end: Optional[int] = None

    def generate_id(self, prefix: str = "comp") -> str:
        """Generate a unique ID for this component"""
        import uuid
        return f"{prefix}_{uuid.uuid4().hex[:8]}"


@dataclass
class FileMetadata:
    """Metadata for Python file"""
    created: datetime
    agent_id: str
    version: str
    description: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "created": self.created.isoformat(),
            "agent_id": self.agent_id,
            "version": self.version,
            "description": self.description
        }


@dataclass
class Parameter:
    """Function/method parameter"""
    name: str
    type: Optional[str] = None
    default: Optional[str] = None
    is_args: bool = False  # *args
    is_kwargs: bool = False  # **kwargs

    def to_signature_str(self) -> str:
        """Convert to function signature string"""
        result = ""
        if self.is_args:
            result = f"*{self.name}"
        elif self.is_kwargs:
            result = f"**{self.name}"
        else:
            result = self.name

        if self.type and not (self.is_args or self.is_kwargs):
            result += f": {self.type}"

        if self.default and not (self.is_args or self.is_kwargs):
            result += f" = {self.default}"

        return result


@dataclass
class ReturnSpec:
    """Function return specification"""
    type: str
    description: Optional[str] = None

    def to_annotation_str(self) -> str:
        """Convert to type annotation string"""
        return self.type


@dataclass
class Decorator:
    """Python decorator"""
    name: str
    arguments: Optional[str] = None

    def to_string(self) -> str:
        """Convert to decorator string"""
        if self.arguments:
            return f"@{self.name}({self.arguments})"
        return f"@{self.name}"


@dataclass
class Import:
    """Import statement"""
    id: str  # Unique identifier for tracking
    name: str
    module: str
    items: Optional[str] = None  # Comma-separated items for 'from' imports
    alias: Optional[str] = None
    docstring: Optional[str] = None
    line_start: Optional[int] = None  # For mapping to actual file
    line_end: Optional[int] = None

    def to_import_str(self) -> str:
        """Convert to import statement string"""
        if self.items:
            # from module import items
            import_str = f"from {self.module} import {self.items}"
            if self.alias:
                import_str += f" as {self.alias}"
        else:
            # import module
            import_str = f"import {self.module}"
            if self.alias:
                import_str += f" as {self.alias}"
        return import_str


@dataclass
class Variable:
    """Variable or constant"""
    id: str  # Unique identifier for tracking
    name: str
    type: Optional[str] = None
    value: Optional[str] = None
    docstring: Optional[str] = None
    line_start: Optional[int] = None  # For mapping to actual file
    line_end: Optional[int] = None

    def to_assignment_str(self) -> str:
        """Convert to assignment string"""
        result = self.name
        if self.type:
            result += f": {self.type}"
        if self.value:
            result += f" = {self.value}"
        return result


@dataclass
class Constant(Variable):
    """Module-level constant"""
    pass


@dataclass
class CodeBlock:
    """Code block with metadata"""
    content: str
    language: str = "python"
    formatted: bool = True

    def get_indented_content(self, indent: int = 4) -> str:
        """Get content with proper indentation"""
        if not self.content.strip():
            return "pass"

        lines = self.content.split('\n')
        indented_lines = []
        for line in lines:
            if line.strip():  # Only indent non-empty lines
                indented_lines.append(' ' * indent + line)
            else:
                indented_lines.append('')
        return '\n'.join(indented_lines)


@dataclass
class Property:
    """Property with getter/setter/deleter"""
    id: str  # Unique identifier for tracking
    name: str
    type: Optional[str] = None
    getter: Optional[CodeBlock] = None
    setter: Optional[CodeBlock] = None
    deleter: Optional[CodeBlock] = None
    docstring: Optional[str] = None
    line_start: Optional[int] = None  # For mapping to actual file
    line_end: Optional[int] = None

    def has_setter(self) -> bool:
        return self.setter is not None

    def has_deleter(self) -> bool:
        return self.deleter is not None


@dataclass
class Method:
    """Class method"""
    id: str  # Unique identifier for tracking
    name: str
    decorators: List[Decorator] = field(default_factory=list)
    parameters: List[Parameter] = field(default_factory=list)
    returns: List[ReturnSpec] = field(default_factory=list)  # Max 3
    body: Optional[CodeBlock] = None
    is_static: bool = False
    is_class_method: bool = False
    is_async: bool = False
    is_private: bool = False
    docstring: Optional[str] = None
    line_start: Optional[int] = None  # For mapping to actual file
    line_end: Optional[int] = None

    def get_method_type(self) -> str:
        """Get the type of method"""
        if self.is_static:
            return "staticmethod"
        elif self.is_class_method:
            return "classmethod"
        elif self.is_private:
            return "private"
        else:
            return "instance"

    def to_signature_str(self) -> str:
        """Convert to method signature string"""
        async_prefix = "async " if self.is_async else ""
        params_str = ", ".join(param.to_signature_str() for param in self.parameters)

        signature = f"{async_prefix}def {self.name}({params_str})"

        if self.returns:
            return_type = self.returns[0].to_annotation_str()
            signature += f" -> {return_type}"

        return signature + ":"


@dataclass
class InitMethod:
    """Class __init__ method"""
    id: str  # Unique identifier for tracking
    parameters: List[Parameter] = field(default_factory=list)
    body: Optional[CodeBlock] = None
    name: str = "__init__"
    docstring: Optional[str] = None
    line_start: Optional[int] = None  # For mapping to actual file
    line_end: Optional[int] = None

    def to_signature_str(self) -> str:
        """Convert to __init__ signature string"""
        params_str = ", ".join(param.to_signature_str() for param in self.parameters)
        return f"def __init__({params_str}):"


@dataclass
class PythonFunction:
    """Standalone function (not a method)"""
    id: str  # Unique identifier for tracking
    name: str
    decorators: List[Decorator] = field(default_factory=list)
    parameters: List[Parameter] = field(default_factory=list)
    returns: List[ReturnSpec] = field(default_factory=list)  # Max 3
    body: Optional[CodeBlock] = None
    is_async: bool = False
    docstring: Optional[str] = None
    line_start: Optional[int] = None  # For mapping to actual file
    line_end: Optional[int] = None

    def to_signature_str(self) -> str:
        """Convert to function signature string"""
        async_prefix = "async " if self.is_async else ""
        params_str = ", ".join(param.to_signature_str() for param in self.parameters)

        signature = f"{async_prefix}def {self.name}({params_str})"

        if self.returns:
            return_type = self.returns[0].to_annotation_str()
            signature += f" -> {return_type}"

        return signature + ":"


@dataclass
class PythonClass:
    """Python class definition"""
    id: str  # Unique identifier for tracking
    name: str
    base_classes: List[str] = field(default_factory=list)
    class_variables: List[Variable] = field(default_factory=list)
    init_method: Optional[InitMethod] = None
    properties: List[Property] = field(default_factory=list)
    methods: List[Method] = field(default_factory=list)
    docstring: Optional[str] = None
    line_start: Optional[int] = None  # For mapping to actual file
    line_end: Optional[int] = None

    def get_inheritance_str(self) -> str:
        """Get inheritance string for class definition"""
        if self.base_classes:
            return f"({', '.join(self.base_classes)})"
        return ""

    def to_class_definition_str(self) -> str:
        """Convert to class definition string"""
        inheritance = self.get_inheritance_str()
        return f"class {self.name}{inheritance}:"

    def get_all_methods(self) -> List[Method]:
        """Get all methods including init if present"""
        methods = []
        if self.init_method:
            # Convert InitMethod to Method for uniform handling
            init_as_method = Method(
                id=self.init_method.id,
                name="__init__",
                parameters=self.init_method.parameters,
                body=self.init_method.body,
                line_start=self.init_method.line_start,
                line_end=self.init_method.line_end
            )
            methods.append(init_as_method)
        methods.extend(self.methods)
        return methods


@dataclass
class PythonFile:
    """Complete Python file representation"""
    id: str
    filepath: str
    metadata: FileMetadata
    imports: List[Import] = field(default_factory=list)
    constants: List[Constant] = field(default_factory=list)
    classes: List[PythonClass] = field(default_factory=list)
    functions: List[PythonFunction] = field(default_factory=list)

    def get_all_components(self) -> List[PythonComponent]:
        """Get all components in the file"""
        components = []
        components.extend(self.imports)
        components.extend(self.constants)
        components.extend(self.classes)
        components.extend(self.functions)

        # Add nested components from classes
        for cls in self.classes:
            components.extend(cls.class_variables)
            if cls.init_method:
                components.append(cls.init_method)
            components.extend(cls.properties)
            components.extend(cls.methods)

        return components

    def get_component_by_id(self, component_id: str) -> Optional[PythonComponent]:
        """Find a component by its ID"""
        for component in self.get_all_components():
            if component.id == component_id:
                return component
        return None

    def generate_python_code(self) -> str:
        """Generate Python code from the structured representation"""
        lines = []

        # Add file docstring if present in metadata
        if self.metadata.description:
            lines.append(f'"""{self.metadata.description}"""')
            lines.append("")

        # Add imports
        if self.imports:
            for import_stmt in self.imports:
                lines.append(import_stmt.to_import_str())
            lines.append("")

        # Add constants
        if self.constants:
            for constant in self.constants:
                if constant.docstring:
                    lines.append(f'"""{constant.docstring}"""')
                lines.append(constant.to_assignment_str())
            lines.append("")

        # Add functions
        for function in self.functions:
            lines.extend(self._generate_function_code(function))
            lines.append("")

        # Add classes
        for cls in self.classes:
            lines.extend(self._generate_class_code(cls))
            lines.append("")

        return "\n".join(lines)

    def _generate_function_code(self, func: PythonFunction) -> List[str]:
        """Generate code for a function"""
        lines = []

        # Add decorators
        for decorator in func.decorators:
            lines.append(decorator.to_string())

        # Add function definition
        lines.append(func.to_signature_str())

        # Add docstring
        if func.docstring:
            lines.append(f'    """{func.docstring}"""')

        # Add body
        if func.body:
            body_lines = func.body.get_indented_content().split('\n')
            lines.extend(body_lines)
        else:
            lines.append("    pass")

        return lines

    def _generate_class_code(self, cls: PythonClass) -> List[str]:
        """Generate code for a class"""
        lines = []

        # Add class definition
        lines.append(cls.to_class_definition_str())

        # Add class docstring
        if cls.docstring:
            lines.append(f'    """{cls.docstring}"""')

        # Add class variables
        if cls.class_variables:
            lines.append("")
            for var in cls.class_variables:
                if var.docstring:
                    lines.append(f'    """{var.docstring}"""')
                lines.append(f"    {var.to_assignment_str()}")

        # Add init method
        if cls.init_method:
            lines.append("")
            lines.extend(self._generate_init_code(cls.init_method))

        # Add properties
        for prop in cls.properties:
            lines.append("")
            lines.extend(self._generate_property_code(prop))

        # Add methods
        for method in cls.methods:
            lines.append("")
            lines.extend(self._generate_method_code(method))

        # If class is empty, add pass
        if not (cls.class_variables or cls.init_method or cls.properties or cls.methods):
            if not cls.docstring:
                lines.append("    pass")

        return lines

    def _generate_init_code(self, init: InitMethod) -> List[str]:
        """Generate code for __init__ method"""
        lines = []
        lines.append(f"    {init.to_signature_str()}")

        if init.docstring:
            lines.append(f'        """{init.docstring}"""')

        if init.body:
            body_lines = init.body.get_indented_content(8).split('\n')
            lines.extend(body_lines)
        else:
            lines.append("        pass")

        return lines

    def _generate_method_code(self, method: Method) -> List[str]:
        """Generate code for a method"""
        lines = []

        # Add decorators
        for decorator in method.decorators:
            lines.append(f"    {decorator.to_string()}")

        # Add method definition
        lines.append(f"    {method.to_signature_str()}")

        # Add docstring
        if method.docstring:
            lines.append(f'        """{method.docstring}"""')

        # Add body
        if method.body:
            body_lines = method.body.get_indented_content(8).split('\n')
            lines.extend(body_lines)
        else:
            lines.append("        pass")

        return lines

    def _generate_property_code(self, prop: Property) -> List[str]:
        """Generate code for a property"""
        lines = []

        # Getter
        lines.append("    @property")
        lines.append(f"    def {prop.name}(self):")
        if prop.docstring:
            lines.append(f'        """{prop.docstring}"""')

        if prop.getter:
            getter_lines = prop.getter.get_indented_content(8).split('\n')
            lines.extend(getter_lines)
        else:
            lines.append("        pass")

        # Setter
        if prop.has_setter():
            lines.append("")
            lines.append(f"    @{prop.name}.setter")
            lines.append(f"    def {prop.name}(self, value):")
            setter_lines = prop.setter.get_indented_content(8).split('\n')
            lines.extend(setter_lines)

        # Deleter
        if prop.has_deleter():
            lines.append("")
            lines.append(f"    @{prop.name}.deleter")
            lines.append(f"    def {prop.name}(self):")
            deleter_lines = prop.deleter.get_indented_content(8).split('\n')
            lines.extend(deleter_lines)

        return lines