"""Unit tests for the schema system (data classes, serialization, validation)"""

import pytest
from datetime import datetime

from src.schemas.python_components import *
from src.schemas.xml_serializer import PythonComponentXMLSerializer, create_example_python_file
from src.core.validation.xml_validator import PythonCodeXMLValidator


@pytest.mark.unit
class TestSchemaSystem:
    """Test the complete schema system"""

    def test_data_class_creation(self):
        """Test creating Python component data classes"""
        # Test FileMetadata
        metadata = FileMetadata(
            created=datetime.now(),
            agent_id="test_123",
            version="1.0.0",
            description="Test file"
        )
        assert metadata.agent_id == "test_123"
        assert metadata.version == "1.0.0"

        # Test Parameter
        param = Parameter(name="self")
        param2 = Parameter(name="value", type="str", default="'default'")
        assert param.to_signature_str() == "self"
        assert param2.to_signature_str() == "value: str = 'default'"

        # Test Function
        func = PythonFunction(
            id="func_001",
            name="test_function",
            parameters=[param, param2],
            returns=[ReturnSpec(type="str")],
            body=CodeBlock(content="return f'Hello {value}'")
        )
        signature = func.to_signature_str()
        assert "def test_function(self, value: str = 'default') -> str:" == signature

    def test_xml_serialization(self):
        """Test XML serialization of Python components"""
        python_file = create_example_python_file()
        serializer = PythonComponentXMLSerializer()
        xml_content = serializer.serialize_python_file(python_file)

        # Check XML contains expected elements
        expected_elements = [
            '<python_file',
            '<metadata>',
            '<imports>',
            '<constants>',
            '<classes>',
            '<functions>',
            'id="pf_001"',
            'filepath="src/example.py"'
        ]

        for element in expected_elements:
            assert element in xml_content, f"Missing expected element: {element}"

    def test_xml_validation(self):
        """Test XML validation against schema"""
        python_file = create_example_python_file()
        serializer = PythonComponentXMLSerializer()
        xml_content = serializer.serialize_python_file(python_file)

        validator = PythonCodeXMLValidator()
        result = validator.validate_xml_string(xml_content)

        assert result.is_valid, f"Validation failed: {result.errors}"
        assert not result.has_errors

    def test_code_generation(self):
        """Test generating Python code from data classes"""
        python_file = create_example_python_file()
        generated_code = python_file.generate_python_code()

        # Check generated code contains expected elements
        expected_code_elements = [
            "from typing import List, Optional, Dict",
            "from dataclasses import dataclass",
            "DEFAULT_TIMEOUT: int = 30",
            "def calculate_sum(a: int, b: int) -> int:",
            "class ExampleClass(BaseClass):",
            "def __init__(self, value: str = 'default'):",
            "def get_value(self) -> str:"
        ]

        for element in expected_code_elements:
            assert element in generated_code, f"Missing expected code element: {element}"

        # Test that generated code is syntactically valid
        compile(generated_code, "test_generated.py", "exec")

    def test_component_tracking(self):
        """Test component ID tracking and lookup"""
        python_file = create_example_python_file()

        # Test getting all components
        all_components = python_file.get_all_components()
        assert len(all_components) > 0

        # Test component lookup by ID
        for component in all_components:
            found_component = python_file.get_component_by_id(component.id)
            assert found_component is not None
            assert found_component.id == component.id

    def test_round_trip(self):
        """Test complete round-trip: data classes -> XML -> validation -> code generation"""
        # 1. Create data classes
        python_file = create_example_python_file()

        # 2. Serialize to XML
        serializer = PythonComponentXMLSerializer()
        xml_content = serializer.serialize_python_file(python_file)

        # 3. Validate XML
        validator = PythonCodeXMLValidator()
        validation_result = validator.validate_xml_string(xml_content)
        assert validation_result.is_valid

        # 4. Generate Python code
        generated_code = python_file.generate_python_code()

        # 5. Verify code compiles
        compile(generated_code, "round_trip_test.py", "exec")

    def test_complex_class_structure(self):
        """Test complex class with methods, properties, etc."""
        # Create a complex class structure
        init_method = InitMethod(
            id="init_001",
            parameters=[
                Parameter(name="self"),
                Parameter(name="name", type="str"),
                Parameter(name="age", type="int", default="0")
            ],
            body=CodeBlock(content="self.name = name\nself.age = age")
        )

        property_obj = Property(
            id="prop_001",
            name="display_name",
            type="str",
            getter=CodeBlock(content="return f'{self.name} ({self.age})'")
        )

        method = Method(
            id="meth_001",
            name="celebrate_birthday",
            parameters=[Parameter(name="self")],
            returns=[ReturnSpec(type="None")],
            body=CodeBlock(content="self.age += 1\nprint(f'Happy birthday {self.name}!')")
        )

        cls = PythonClass(
            id="cls_001",
            name="Person",
            init_method=init_method,
            properties=[property_obj],
            methods=[method]
        )

        # Test class structure
        assert cls.name == "Person"
        assert len(cls.properties) == 1
        assert len(cls.methods) == 1
        assert cls.init_method is not None

        # Test method retrieval
        all_methods = cls.get_all_methods()
        assert len(all_methods) == 2  # init + method

    def test_validation_errors(self):
        """Test validation catches errors"""
        # Create invalid XML (missing required attributes)
        invalid_xml = """<python_file>
            <metadata>
                <created>2024-01-01T00:00:00Z</created>
            </metadata>
        </python_file>"""

        validator = PythonCodeXMLValidator()
        result = validator.validate_xml_string(invalid_xml)

        assert not result.is_valid
        assert result.has_errors
        assert len(result.errors) > 0

    def test_import_serialization(self):
        """Test import statement serialization"""
        import_stmt = Import(
            id="imp_001",
            name="typing",
            module="typing",
            items="List, Dict, Optional"
        )

        expected = "from typing import List, Dict, Optional"
        assert import_stmt.to_import_str() == expected

        # Test simple import
        simple_import = Import(
            id="imp_002",
            name="os",
            module="os"
        )
        assert simple_import.to_import_str() == "import os"

        # Test import with alias
        alias_import = Import(
            id="imp_003",
            name="numpy",
            module="numpy",
            alias="np"
        )
        assert alias_import.to_import_str() == "import numpy as np"