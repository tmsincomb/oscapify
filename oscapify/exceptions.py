"""Custom exceptions for Oscapify."""


class OscapifyError(Exception):
    """Base exception for all Oscapify errors."""

    pass


class HeaderValidationError(OscapifyError):
    """Raised when CSV headers don't match expected format."""

    def __init__(self, message: str, missing_headers: list = None, extra_headers: list = None):
        super().__init__(message)
        self.missing_headers = missing_headers or []
        self.extra_headers = extra_headers or []


class DOIRetrievalError(OscapifyError):
    """Raised when DOI retrieval fails."""

    def __init__(self, message: str, pmid: str = None, pmcid: str = None):
        super().__init__(message)
        self.pmid = pmid
        self.pmcid = pmcid


class ConfigurationError(OscapifyError):
    """Raised when configuration is invalid."""

    pass


class FileProcessingError(OscapifyError):
    """Raised when file processing fails."""

    def __init__(self, message: str, file_path: str = None):
        super().__init__(message)
        self.file_path = file_path
