"""Oscapify - Convert scientific literature CSV files to OSCAP-compatible format."""

__version__ = "0.1.0"
__author__ = "Troy Sincomb"

from .core import OscapifyProcessor
from .exceptions import DOIRetrievalError, HeaderValidationError, OscapifyError

__all__ = [
    "OscapifyProcessor",
    "OscapifyError",
    "HeaderValidationError",
    "DOIRetrievalError",
    "__version__",
    "__author__",
]
