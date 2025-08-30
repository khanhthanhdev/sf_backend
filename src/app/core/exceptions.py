"""
Custom exceptions for the video generation application.

This module defines application-specific exceptions for better error handling
and debugging throughout the system.
"""


class T2MBaseException(Exception):
    """Base exception class for all T2M application exceptions."""
    
    def __init__(self, message: str, error_code: str = None, details: dict = None):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        super().__init__(self.message)


class DatabaseError(T2MBaseException):
    """Raised when database operations fail."""
    pass


class JobNotFoundError(T2MBaseException):
    """Raised when a requested job cannot be found."""
    pass


class JobValidationError(T2MBaseException):
    """Raised when job configuration or data is invalid."""
    pass


class UserNotFoundError(T2MBaseException):
    """Raised when a requested user cannot be found."""
    pass


class FileNotFoundError(T2MBaseException):
    """Raised when a requested file cannot be found."""
    pass


class S3OperationError(T2MBaseException):
    """Raised when S3 operations fail."""
    pass


class VideoProcessingError(T2MBaseException):
    """Raised when video processing operations fail."""
    pass


class AuthenticationError(T2MBaseException):
    """Raised when authentication fails."""
    pass


class AuthorizationError(T2MBaseException):
    """Raised when user lacks permission for an operation."""
    pass


class ConfigurationError(T2MBaseException):
    """Raised when application configuration is invalid."""
    pass


class ExternalServiceError(T2MBaseException):
    """Raised when external service calls fail."""
    pass


class RateLimitError(T2MBaseException):
    """Raised when rate limits are exceeded."""
    pass


class ValidationError(T2MBaseException):
    """Raised when input validation fails."""
    pass