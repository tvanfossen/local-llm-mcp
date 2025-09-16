"""Python File Schema - Structured representation of Python code files

Responsibilities:
- Define JSON schema for Python code elements
- Support incremental updates and structured code generation
- Enable template-based file rendering
"""

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PythonElementType(Enum):
    """Types of Python code elements"""

    FUNCTION = "function"
    CLASS = "class"
    DATACLASS = "dataclass"
    IMPORT = "import"
    VARIABLE = "variable"


@dataclass
class PythonFunction:
    """Represents a Python function with full metadata"""

    name: str
    docstring: Optional[str]
    parameters: list[dict[str, Any]]  # [{"name": "x", "type": "int", "default": None}]
    return_type: Optional[str]
    body: str
    decorators: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class PythonMethod:
    """Represents a class method"""

    name: str
    docstring: Optional[str]
    parameters: list[dict[str, Any]]
    return_type: Optional[str]
    body: str
    decorators: list[str] = field(default_factory=list)
    is_static: bool = False
    is_class_method: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class PythonClass:
    """Represents a Python class with methods and variables"""

    name: str
    docstring: Optional[str]
    base_classes: list[str]
    methods: list[PythonMethod]
    class_variables: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    def get_method(self, method_name: str) -> Optional[PythonMethod]:
        """Get method by name"""
        for method in self.methods:
            if method.name == method_name:
                return method
        return None

    def add_or_update_method(self, method: PythonMethod) -> None:
        """Add new method or update existing one"""
        # Remove existing method with same name
        self.methods = [m for m in self.methods if m.name != method.name]
        # Add the new/updated method
        self.methods.append(method)


@dataclass
class PythonDataclass:
    """Represents a Python dataclass"""

    name: str
    docstring: Optional[str]
    fields: list[dict[str, Any]]  # [{"name": "id", "type": "str", "default": None}]
    base_classes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class PythonImport:
    """Represents an import statement"""

    module: str
    items: list[str] = field(default_factory=list)  # For 'from module import items'
    alias: Optional[str] = None  # For 'import module as alias'

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    def to_import_statement(self) -> str:
        """Convert to actual import statement"""
        if self.items:
            items_str = ", ".join(self.items)
            return f"from {self.module} import {items_str}"
        elif self.alias:
            return f"import {self.module} as {self.alias}"
        else:
            return f"import {self.module}"


@dataclass
class PythonVariable:
    """Represents a module-level variable"""

    name: str
    type_hint: Optional[str]
    value: str
    docstring: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)


@dataclass
class PythonFile:
    """Complete representation of a Python file"""

    filename: str
    module_docstring: Optional[str] = None
    imports: list[PythonImport] = field(default_factory=list)
    variables: list[PythonVariable] = field(default_factory=list)
    dataclasses: list[PythonDataclass] = field(default_factory=list)
    classes: list[PythonClass] = field(default_factory=list)
    functions: list[PythonFunction] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return asdict(self)

    def get_function(self, function_name: str) -> Optional[PythonFunction]:
        """Get function by name"""
        for func in self.functions:
            if func.name == function_name:
                return func
        return None

    def get_class(self, class_name: str) -> Optional[PythonClass]:
        """Get class by name"""
        for cls in self.classes:
            if cls.name == class_name:
                return cls
        return None

    def get_dataclass(self, dataclass_name: str) -> Optional[PythonDataclass]:
        """Get dataclass by name"""
        for dc in self.dataclasses:
            if dc.name == dataclass_name:
                return dc
        return None

    def add_or_update_function(self, function: PythonFunction) -> None:
        """Add new function or update existing one"""
        # Remove existing function with same name
        self.functions = [f for f in self.functions if f.name != function.name]
        # Add the new/updated function
        self.functions.append(function)

    def add_or_update_class(self, python_class: PythonClass) -> None:
        """Add new class or update existing one"""
        # Remove existing class with same name
        self.classes = [c for c in self.classes if c.name != python_class.name]
        # Add the new/updated class
        self.classes.append(python_class)

    def add_or_update_dataclass(self, dataclass: PythonDataclass) -> None:
        """Add new dataclass or update existing one"""
        # Remove existing dataclass with same name
        self.dataclasses = [dc for dc in self.dataclasses if dc.name != dataclass.name]
        # Add the new/updated dataclass
        self.dataclasses.append(dataclass)

    def add_import(self, import_stmt: PythonImport) -> None:
        """Add import if not already present"""
        # Check if import already exists
        for existing_import in self.imports:
            if (
                existing_import.module == import_stmt.module
                and existing_import.items == import_stmt.items
                and existing_import.alias == import_stmt.alias
            ):
                return  # Import already exists

        self.imports.append(import_stmt)


def create_empty_python_file(filename: str) -> PythonFile:
    """Create an empty Python file structure"""
    return PythonFile(filename=filename)


def create_function_from_dict(data: dict[str, Any]) -> PythonFunction:
    """Create PythonFunction from dictionary data"""
    return PythonFunction(**data)


def create_class_from_dict(data: dict[str, Any]) -> PythonClass:
    """Create PythonClass from dictionary data"""
    # Convert method dictionaries to PythonMethod objects
    if "methods" in data:
        data["methods"] = [PythonMethod(**method_data) for method_data in data["methods"]]
    return PythonClass(**data)


def create_dataclass_from_dict(data: dict[str, Any]) -> PythonDataclass:
    """Create PythonDataclass from dictionary data"""
    return PythonDataclass(**data)
