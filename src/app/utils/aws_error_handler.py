"""
AWS Error Handler Utilities

This module provides utilities for handling AWS service errors and converting
them to appropriate HTTP responses for the FastAPI application.
"""

import logging
from typing import Dict, Any, Optional
from fastapi import HTTPException, status
from botocore.exceptions import ClientError, NoCredentialsError, EndpointConnectionError

logger = logging.getLogger(__name__)


class AWSErrorHandler:
    """Handles AWS service errors and converts them to HTTP exceptions."""
    
    @staticmethod
    def handle_s3_error(error: Exception, operation: str = "S3 operation") -> HTTPException:
        """
        Handle S3-specific errors and convert to HTTP exceptions.
        
        Args:
            error: The exception that occurred
            operation: Description of the operation that failed
            
        Returns:
            HTTPException with appropriate status code and message
        """
        if isinstance(error, ClientError):
            error_code = error.response['Error']['Code']
            error_message = error.response['Error']['Message']
            
            if error_code == 'NoSuchBucket':
                return HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Storage service unavailable: {error_message}"
                )
            elif error_code == 'NoSuchKey':
                return HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="File not found"
                )
            elif error_code == 'AccessDenied':
                return HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Access denied to storage service"
                )
            elif error_code == 'InvalidRequest':
                return HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid request: {error_message}"
                )
            else:
                logger.error(f"S3 {operation} failed with error {error_code}: {error_message}")
                return HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Storage service error: {operation} failed"
                )
        
        elif isinstance(error, NoCredentialsError):
            logger.error(f"AWS credentials not found for {operation}")
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service configuration error"
            )
        
        elif isinstance(error, EndpointConnectionError):
            logger.error(f"Cannot connect to AWS endpoint for {operation}: {error}")
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Storage service temporarily unavailable"
            )
        
        else:
            logger.error(f"Unexpected error during {operation}: {error}")
            return HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Storage service error: {operation} failed"
            )
    
    @staticmethod
    def handle_rds_error(error: Exception, operation: str = "Database operation") -> HTTPException:
        """
        Handle RDS/Database-specific errors and convert to HTTP exceptions.
        
        Args:
            error: The exception that occurred
            operation: Description of the operation that failed
            
        Returns:
            HTTPException with appropriate status code and message
        """
        # Handle PostgreSQL specific errors
        if hasattr(error, 'pgcode'):
            pgcode = getattr(error, 'pgcode', None)
            
            if pgcode == '23505':  # Unique violation
                return HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Resource already exists"
                )
            elif pgcode == '23503':  # Foreign key violation
                return HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Invalid reference to related resource"
                )
            elif pgcode == '23502':  # Not null violation
                return HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Required field missing"
                )
        
        # Handle connection errors
        if "connection" in str(error).lower():
            logger.error(f"Database connection error during {operation}: {error}")
            return HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Database service temporarily unavailable"
            )
        
        # Handle timeout errors
        if "timeout" in str(error).lower():
            logger.error(f"Database timeout during {operation}: {error}")
            return HTTPException(
                status_code=status.HTTP_504_GATEWAY_TIMEOUT,
                detail="Database operation timed out"
            )
        
        # Generic database error
        logger.error(f"Database error during {operation}: {error}")
        return HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Database error: {operation} failed"
        )
    
    @staticmethod
    def handle_service_unavailable(service_name: str) -> HTTPException:
        """
        Handle cases where AWS services are not available.
        
        Args:
            service_name: Name of the unavailable service
            
        Returns:
            HTTPException indicating service unavailability
        """
        return HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"{service_name} service not available. Please try again later."
        )
    
    @staticmethod
    def handle_generic_aws_error(error: Exception, operation: str = "AWS operation") -> HTTPException:
        """
        Handle generic AWS errors that don't fit specific service categories.
        
        Args:
            error: The exception that occurred
            operation: Description of the operation that failed
            
        Returns:
            HTTPException with appropriate status code and message
        """
        if isinstance(error, ClientError):
            error_code = error.response['Error']['Code']
            error_message = error.response['Error']['Message']
            
            if error_code in ['Throttling', 'RequestLimitExceeded']:
                return HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Service temporarily overloaded. Please try again later."
                )
            elif error_code == 'ServiceUnavailable':
                return HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="AWS service temporarily unavailable"
                )
            else:
                logger.error(f"AWS {operation} failed with error {error_code}: {error_message}")
                return HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"AWS service error: {operation} failed"
                )
        
        else:
            logger.error(f"Unexpected AWS error during {operation}: {error}")
            return HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"AWS service error: {operation} failed"
            )


def handle_aws_service_error(error: Exception, service_type: str, operation: str) -> HTTPException:
    """
    Main error handler that routes to appropriate service-specific handlers.
    
    Args:
        error: The exception that occurred
        service_type: Type of AWS service (s3, rds, generic)
        operation: Description of the operation that failed
        
    Returns:
        HTTPException with appropriate status code and message
    """
    if service_type.lower() == 's3':
        return AWSErrorHandler.handle_s3_error(error, operation)
    elif service_type.lower() in ['rds', 'database', 'postgres']:
        return AWSErrorHandler.handle_rds_error(error, operation)
    else:
        return AWSErrorHandler.handle_generic_aws_error(error, operation)


def log_aws_error(error: Exception, context: Dict[str, Any]) -> None:
    """
    Log AWS errors with context information.
    
    Args:
        error: The exception that occurred
        context: Additional context information for logging
    """
    logger.error(
        "AWS service error occurred",
        extra={
            "error_type": type(error).__name__,
            "error_message": str(error),
            **context
        },
        exc_info=True
    )