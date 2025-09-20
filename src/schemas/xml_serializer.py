"""XML Serializer for Python Components

This module provides serialization of Python component data classes to XML format
according to the python_code.xsd schema.
"""

import logging
import xml.etree.ElementTree as ET
from typing import Optional
from datetime import datetime

from .python_components import (
    PythonFile, PythonClass, PythonFunction, Method, InitMethod,
    Property, Variable, Constant, Import, Parameter, Decorator,
    ReturnSpec, CodeBlock, FileMetadata
)

logger = logging.getLogger(__name__)


class PythonComponentXMLSerializer:
    """Serializes Python components to XML format"""

    def __init__(self, namespace: Optional[str] = None):
        self.namespace = namespace or "http://local-llm-mcp/python-code"
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    def serialize_python_file(self, python_file: PythonFile) -> str:
        """Serialize a PythonFile to XML string"""
        # Create root element without namespace for now (simpler validation)
        root = ET.Element("python_file")
        root.set("id", python_file.id)
        root.set("filepath", python_file.filepath)

        # Add metadata
        metadata_elem = ET.SubElement(root, "metadata")
        self._serialize_metadata(metadata_elem, python_file.metadata)

        # Add imports
        if python_file.imports:
            imports_elem = ET.SubElement(root, "imports")
            for import_item in python_file.imports:
                self._serialize_import(imports_elem, import_item)

        # Add constants
        if python_file.constants:
            constants_elem = ET.SubElement(root, "constants")
            for constant in python_file.constants:
                self._serialize_constant(constants_elem, constant)

        # Add classes
        if python_file.classes:
            classes_elem = ET.SubElement(root, "classes")
            for cls in python_file.classes:
                self._serialize_class(classes_elem, cls)

        # Add functions
        if python_file.functions:
            functions_elem = ET.SubElement(root, "functions")
            for func in python_file.functions:
                self._serialize_function(functions_elem, func)

        # Convert to string with proper formatting
        return self._prettify_xml(root)

    def _serialize_metadata(self, parent: ET.Element, metadata: FileMetadata):
        """Serialize FileMetadata to XML"""
        created_elem = ET.SubElement(parent, "created")
        created_elem.text = metadata.created.isoformat()

        agent_id_elem = ET.SubElement(parent, "agent_id")
        agent_id_elem.text = metadata.agent_id

        version_elem = ET.SubElement(parent, "version")
        version_elem.text = metadata.version

        if metadata.description:
            desc_elem = ET.SubElement(parent, "description")
            desc_elem.text = metadata.description

    def _serialize_import(self, parent: ET.Element, import_item: Import):
        """Serialize Import to XML"""
        import_elem = ET.SubElement(parent, "import")
        import_elem.set("id", import_item.id)
        import_elem.set("module", import_item.module)

        if import_item.items:
            import_elem.set("items", import_item.items)

        if import_item.alias:
            import_elem.set("alias", import_item.alias)

    def _serialize_constant(self, parent: ET.Element, constant: Constant):
        """Serialize Constant to XML"""
        const_elem = ET.SubElement(parent, "constant")
        const_elem.set("id", constant.id)
        const_elem.set("name", constant.name)
        const_elem.set("value", constant.value or "")

        if constant.type:
            const_elem.set("type", constant.type)

        if constant.line_start is not None:
            const_elem.set("line_start", str(constant.line_start))

        if constant.line_end is not None:
            const_elem.set("line_end", str(constant.line_end))

        if constant.docstring:
            docstring_elem = ET.SubElement(const_elem, "docstring")
            docstring_elem.text = constant.docstring

    def _serialize_class(self, parent: ET.Element, cls: PythonClass):
        """Serialize PythonClass to XML"""
        class_elem = ET.SubElement(parent, "class")
        class_elem.set("id", cls.id)
        class_elem.set("name", cls.name)

        if cls.line_start is not None:
            class_elem.set("line_start", str(cls.line_start))

        if cls.line_end is not None:
            class_elem.set("line_end", str(cls.line_end))

        # Add docstring
        if cls.docstring:
            docstring_elem = ET.SubElement(class_elem, "docstring")
            docstring_elem.text = cls.docstring

        # Add base classes
        if cls.base_classes:
            base_classes_elem = ET.SubElement(class_elem, "base_classes")
            for base_class in cls.base_classes:
                base_elem = ET.SubElement(base_classes_elem, "base_class")
                base_elem.set("name", base_class)

        # Add class variables
        if cls.class_variables:
            vars_elem = ET.SubElement(class_elem, "class_variables")
            for var in cls.class_variables:
                self._serialize_variable(vars_elem, var)

        # Add init method
        if cls.init_method:
            self._serialize_init_method(class_elem, cls.init_method)

        # Add properties
        if cls.properties:
            props_elem = ET.SubElement(class_elem, "properties")
            for prop in cls.properties:
                self._serialize_property(props_elem, prop)

        # Add methods
        if cls.methods:
            methods_elem = ET.SubElement(class_elem, "methods")
            for method in cls.methods:
                self._serialize_method(methods_elem, method)

    def _serialize_function(self, parent: ET.Element, func: PythonFunction):
        """Serialize PythonFunction to XML"""
        func_elem = ET.SubElement(parent, "function")
        func_elem.set("id", func.id)
        func_elem.set("name", func.name)

        if func.line_start is not None:
            func_elem.set("line_start", str(func.line_start))

        if func.line_end is not None:
            func_elem.set("line_end", str(func.line_end))

        if func.is_async:
            func_elem.set("is_async", "true")

        # Add docstring
        if func.docstring:
            docstring_elem = ET.SubElement(func_elem, "docstring")
            docstring_elem.text = func.docstring

        # Add decorators
        if func.decorators:
            decorators_elem = ET.SubElement(func_elem, "decorators")
            for decorator in func.decorators:
                self._serialize_decorator(decorators_elem, decorator)

        # Add parameters
        if func.parameters:
            params_elem = ET.SubElement(func_elem, "parameters")
            for param in func.parameters:
                self._serialize_parameter(params_elem, param)

        # Add returns
        if func.returns:
            for return_spec in func.returns:
                self._serialize_return_spec(func_elem, return_spec)

        # Add body
        if func.body:
            self._serialize_code_block(func_elem, "body", func.body)

    def _serialize_variable(self, parent: ET.Element, var: Variable):
        """Serialize Variable to XML"""
        var_elem = ET.SubElement(parent, "variable")
        var_elem.set("id", var.id)
        var_elem.set("name", var.name)

        if var.type:
            var_elem.set("type", var.type)

        if var.value:
            var_elem.set("value", var.value)

        if var.line_start is not None:
            var_elem.set("line_start", str(var.line_start))

        if var.line_end is not None:
            var_elem.set("line_end", str(var.line_end))

        if var.docstring:
            docstring_elem = ET.SubElement(var_elem, "docstring")
            docstring_elem.text = var.docstring

    def _serialize_init_method(self, parent: ET.Element, init: InitMethod):
        """Serialize InitMethod to XML"""
        init_elem = ET.SubElement(parent, "init_method")
        init_elem.set("id", init.id)

        if init.line_start is not None:
            init_elem.set("line_start", str(init.line_start))

        if init.line_end is not None:
            init_elem.set("line_end", str(init.line_end))

        # Add docstring
        if init.docstring:
            docstring_elem = ET.SubElement(init_elem, "docstring")
            docstring_elem.text = init.docstring

        # Add parameters
        if init.parameters:
            params_elem = ET.SubElement(init_elem, "parameters")
            for param in init.parameters:
                self._serialize_parameter(params_elem, param)

        # Add body
        if init.body:
            self._serialize_code_block(init_elem, "body", init.body)

    def _serialize_property(self, parent: ET.Element, prop: Property):
        """Serialize Property to XML"""
        prop_elem = ET.SubElement(parent, "property")
        prop_elem.set("id", prop.id)
        prop_elem.set("name", prop.name)

        if prop.type:
            prop_elem.set("type", prop.type)

        if prop.line_start is not None:
            prop_elem.set("line_start", str(prop.line_start))

        if prop.line_end is not None:
            prop_elem.set("line_end", str(prop.line_end))

        # Add docstring
        if prop.docstring:
            docstring_elem = ET.SubElement(prop_elem, "docstring")
            docstring_elem.text = prop.docstring

        # Add getter
        if prop.getter:
            self._serialize_code_block(prop_elem, "getter", prop.getter)

        # Add setter
        if prop.setter:
            self._serialize_code_block(prop_elem, "setter", prop.setter)

        # Add deleter
        if prop.deleter:
            self._serialize_code_block(prop_elem, "deleter", prop.deleter)

    def _serialize_method(self, parent: ET.Element, method: Method):
        """Serialize Method to XML"""
        method_elem = ET.SubElement(parent, "method")
        method_elem.set("id", method.id)
        method_elem.set("name", method.name)

        if method.is_static:
            method_elem.set("is_static", "true")

        if method.is_class_method:
            method_elem.set("is_class_method", "true")

        if method.is_async:
            method_elem.set("is_async", "true")

        if method.is_private:
            method_elem.set("is_private", "true")

        if method.line_start is not None:
            method_elem.set("line_start", str(method.line_start))

        if method.line_end is not None:
            method_elem.set("line_end", str(method.line_end))

        # Add docstring
        if method.docstring:
            docstring_elem = ET.SubElement(method_elem, "docstring")
            docstring_elem.text = method.docstring

        # Add decorators
        if method.decorators:
            decorators_elem = ET.SubElement(method_elem, "decorators")
            for decorator in method.decorators:
                self._serialize_decorator(decorators_elem, decorator)

        # Add parameters
        if method.parameters:
            params_elem = ET.SubElement(method_elem, "parameters")
            for param in method.parameters:
                self._serialize_parameter(params_elem, param)

        # Add returns
        if method.returns:
            for return_spec in method.returns:
                self._serialize_return_spec(method_elem, return_spec)

        # Add body
        if method.body:
            self._serialize_code_block(method_elem, "body", method.body)

    def _serialize_decorator(self, parent: ET.Element, decorator: Decorator):
        """Serialize Decorator to XML"""
        dec_elem = ET.SubElement(parent, "decorator")
        dec_elem.set("name", decorator.name)

        if decorator.arguments:
            dec_elem.set("arguments", decorator.arguments)

    def _serialize_parameter(self, parent: ET.Element, param: Parameter):
        """Serialize Parameter to XML"""
        param_elem = ET.SubElement(parent, "parameter")
        param_elem.set("name", param.name)

        if param.type:
            param_elem.set("type", param.type)

        if param.default:
            param_elem.set("default", param.default)

        if param.is_args:
            param_elem.set("is_args", "true")

        if param.is_kwargs:
            param_elem.set("is_kwargs", "true")

    def _serialize_return_spec(self, parent: ET.Element, return_spec: ReturnSpec):
        """Serialize ReturnSpec to XML"""
        return_elem = ET.SubElement(parent, "returns")
        return_elem.set("type", return_spec.type)

        if return_spec.description:
            return_elem.set("description", return_spec.description)

    def _serialize_code_block(self, parent: ET.Element, tag_name: str, code_block: CodeBlock):
        """Serialize CodeBlock to XML"""
        code_elem = ET.SubElement(parent, tag_name)
        code_elem.text = code_block.content

        if code_block.language != "python":
            code_elem.set("language", code_block.language)

        if not code_block.formatted:
            code_elem.set("formatted", "false")

    def _prettify_xml(self, element: ET.Element) -> str:
        """Return a pretty-printed XML string"""
        # Simple indentation - for production, consider using lxml for better formatting
        return ET.tostring(element, encoding='unicode', method='xml')


def serialize_python_file_to_xml(python_file: PythonFile) -> str:
    """Convenience function to serialize a PythonFile to XML"""
    serializer = PythonComponentXMLSerializer()
    return serializer.serialize_python_file(python_file)


def create_example_python_file() -> PythonFile:
    """Create an example PythonFile for testing"""
    from datetime import datetime

    # Create metadata
    metadata = FileMetadata(
        created=datetime.now(),
        agent_id="test_agent_123",
        version="1.0.0",
        description="Example Python file for testing XML serialization"
    )

    # Create imports
    imports = [
        Import(
            id="imp_001",
            name="typing",
            module="typing",
            items="List, Optional, Dict"
        ),
        Import(
            id="imp_002",
            name="dataclasses",
            module="dataclasses",
            items="dataclass"
        )
    ]

    # Create a constant
    constants = [
        Constant(
            id="const_001",
            name="DEFAULT_TIMEOUT",
            type="int",
            value="30",
            docstring="Default timeout in seconds"
        )
    ]

    # Create a function
    functions = [
        PythonFunction(
            id="func_001",
            name="calculate_sum",
            docstring="Calculate the sum of two numbers",
            parameters=[
                Parameter(name="a", type="int"),
                Parameter(name="b", type="int")
            ],
            returns=[ReturnSpec(type="int", description="Sum of a and b")],
            body=CodeBlock(content="return a + b")
        )
    ]

    # Create a class
    classes = [
        PythonClass(
            id="cls_001",
            name="ExampleClass",
            docstring="Example class for demonstration",
            base_classes=["BaseClass"],
            class_variables=[
                Variable(
                    id="var_001",
                    name="class_var",
                    type="str",
                    value="'example'"
                )
            ],
            init_method=InitMethod(
                id="init_001",
                parameters=[
                    Parameter(name="self"),
                    Parameter(name="value", type="str", default="'default'")
                ],
                body=CodeBlock(content="self.value = value")
            ),
            methods=[
                Method(
                    id="mth_001",
                    name="get_value",
                    parameters=[Parameter(name="self")],
                    returns=[ReturnSpec(type="str", description="The current value")],
                    body=CodeBlock(content="return self.value")
                )
            ]
        )
    ]

    return PythonFile(
        id="pf_001",
        filepath="src/example.py",
        metadata=metadata,
        imports=imports,
        constants=constants,
        classes=classes,
        functions=functions
    )