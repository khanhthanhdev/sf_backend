"""
Base service interface and common types.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TypeVar, Generic
from pydantic import BaseModel

T = TypeVar('T')
TResult = TypeVar('TResult')


class ServiceResult(BaseModel, Generic[T]):
    """Standard service result wrapper with error handling."""
    
    success: bool
    data: Optional[T] = None
    error: Optional[str] = None
    error_code: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    
    @classmethod
    def success(cls, data: T, metadata: Optional[Dict[str, Any]] = None) -> 'ServiceResult[T]':
        """Create successful result."""
        return cls(success=True, data=data, metadata=metadata)
    
    @classmethod
    def error(
        cls, 
        error: str, 
        error_code: Optional[str] = None, 
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'ServiceResult[T]':
        """Create error result."""
        return cls(
            success=False, 
            error=error, 
            error_code=error_code, 
            metadata=metadata
        )


class IService(ABC):
    """Base interface for all services."""
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Return service name for logging and monitoring."""
        pass
    
    async def initialize(self) -> None:
        """Initialize service resources."""
        pass
    
    async def cleanup(self) -> None:
        """Cleanup service resources."""
        pass
    
    async def health_check(self) -> ServiceResult[Dict[str, Any]]:
        """Check service health status."""
        return ServiceResult.success({
            "service": self.service_name,
            "status": "healthy",
            "timestamp": "now"
        })


class IAsyncContextService(IService):
    """Interface for services that support async context management."""
    
    async def __aenter__(self) -> 'IAsyncContextService':
        await self.initialize()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.cleanup()
