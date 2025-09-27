"""File metadata operations package"""

from .base import BaseMetadataOperation
from .create_file import CreateFileOperation
from .add_import import AddImportOperation
from .add_variable import AddVariableOperation
from .add_class import AddClassOperation
from .add_function import AddFunctionOperation
from .add_field import AddFieldOperation
from .complete_file import CompleteFileOperation
from .read_metadata import ReadMetadataOperation
from .list_metadata import ListMetadataOperation

__all__ = [
    "BaseMetadataOperation",
    "CreateFileOperation",
    "AddImportOperation",
    "AddVariableOperation",
    "AddClassOperation",
    "AddFunctionOperation",
    "AddFieldOperation",
    "CompleteFileOperation",
    "ReadMetadataOperation",
    "ListMetadataOperation"
]