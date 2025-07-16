"""Custom exceptions for Oscapify."""

from typing import Dict, List, Optional


class OscapifyError(Exception):
    """Base exception for all Oscapify errors."""

    pass


class HeaderValidationError(OscapifyError):
    """Raised when CSV headers don't match expected format."""

    def __init__(
        self,
        message: str,
        missing_headers: Optional[List[str]] = None,
        extra_headers: Optional[List[str]] = None,
    ):
        super().__init__(message)
        self.missing_headers = missing_headers or []
        self.extra_headers = extra_headers or []


class DOIRetrievalError(OscapifyError):
    """Raised when DOI retrieval fails."""

    def __init__(
        self,
        message: str,
        pmid: Optional[str] = None,
        pmcid: Optional[str] = None,
        identifier_used: Optional[str] = None,
        api_url: Optional[str] = None,
        api_response: Optional[Dict] = None,
        status_code: Optional[int] = None,
        debug_info: Optional[Dict] = None,
    ):
        super().__init__(message)
        self.pmid = pmid
        self.pmcid = pmcid
        self.identifier_used = identifier_used
        self.api_url = api_url
        self.api_response = api_response
        self.status_code = status_code
        self.debug_info = debug_info or {}


class ConfigurationError(OscapifyError):
    """Raised when configuration is invalid."""

    pass


class FileProcessingError(OscapifyError):
    """Raised when file processing fails."""

    def __init__(self, message: str, file_path: Optional[str] = None):
        super().__init__(message)
        self.file_path = file_path
