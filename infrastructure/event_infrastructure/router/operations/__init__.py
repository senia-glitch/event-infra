"""Операции для универсального CRUD."""

from .base import BaseOperation
from .create import CreateOperation
from .read import ReadOperation
from .update import UpdateOperation
from .delete import DeleteOperation
from .custom import CustomOperation

__all__ = [
    "BaseOperation",
    "CreateOperation",
    "ReadOperation",
    "UpdateOperation",
    "DeleteOperation",
    "CustomOperation",
]