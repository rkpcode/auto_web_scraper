"""
Custom exceptions for the video ingestion pipeline.
All exceptions are logged automatically when raised.
"""
from core.logger import logger


class PipelineException(Exception):
    """Base exception for all pipeline errors."""
    
    def __init__(self, message, url=None, details=None):
        self.message = message
        self.url = url
        self.details = details
        super().__init__(self.message)
        
        # Auto-log exception
        log_msg = f"❌ {self.__class__.__name__}: {message}"
        if url:
            log_msg += f" | URL: {url}"
        if details:
            log_msg += f" | Details: {details}"
        logger.error(log_msg)


class ExtractionError(PipelineException):
    """Raised when video extraction fails."""
    pass


class DownloadError(PipelineException):
    """Raised when video download fails."""
    pass


class UploadError(PipelineException):
    """Raised when upload to Bunny Stream fails."""
    pass


class DiskSpaceError(PipelineException):
    """Raised when insufficient disk space is available."""
    pass


class DatabaseError(PipelineException):
    """Raised when database operations fail."""
    pass


class ConfigurationError(PipelineException):
    """Raised when configuration is invalid or missing."""
    pass


class ProxyError(PipelineException):
    """Raised when proxy connection fails."""
    pass


# Export all exceptions
__all__ = [
    'PipelineException',
    'ExtractionError',
    'DownloadError',
    'UploadError',
    'DiskSpaceError',
    'DatabaseError',
    'ConfigurationError',
    'ProxyError',
]
