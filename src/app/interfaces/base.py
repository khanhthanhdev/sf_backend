"""
Base interfaces for the application.

This module defines foundational interfaces that are used throughout
the application to ensure consistent behavior and enable dependency injection.
"""

from abc import ABC, abstractmethod
from typing import Any, Generic, TypeVar, Optional, Dict
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# Type variables for generic interfaces
T = TypeVar('T')
TRequest = TypeVar('TRequest')
TResponse = TypeVar('TResponse')


class ServiceResult(Generic[T]):
    """
    Standard result wrapper for service operations.
    
    Provides consistent error handling and success/failure indication
    across all service layers.
    """
    
    def __init__(
        self,
        data: Optional[T] = None,
        success: bool = True,
        error: Optional[str] = None,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ):
        self.data = data
        self.success = success
        self.error = error
        self.error_code = error_code
        self.metadata = metadata or {}
        self.timestamp = datetime.utcnow()
    
    @classmethod
    def success(cls, data: T, metadata: Optional[Dict[str, Any]] = None) -> 'ServiceResult[T]':
        """Create a successful result."""
        return cls(data=data, success=True, metadata=metadata)
    
    @classmethod
    def error(
        cls,
        error: str,
        error_code: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> 'ServiceResult[T]':
        """Create an error result."""
        return cls(
            data=None,
            success=False,
            error=error,
            error_code=error_code,
            metadata=metadata
        )
    
    def __repr__(self) -> str:
        if self.success:
            return f"ServiceResult(success=True, data={self.data})"
        else:
            return f"ServiceResult(success=False, error='{self.error}', error_code='{self.error_code}')"


class ServiceLifetime(Enum):
    """Service lifetime enumeration for dependency injection."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


@dataclass
class ServiceRegistration:
    """Service registration information for dependency injection."""
    service_type: type
    implementation_type: type
    lifetime: ServiceLifetime
    factory: Optional[callable] = None


class IService(ABC):
    """
    Base interface for all services.
    
    Provides common functionality that all services should implement
    for consistent behavior across the application.
    """
    
    @property
    @abstractmethod
    def service_name(self) -> str:
        """Get the name of this service."""
        pass
    
    @abstractmethod
    async def initialize(self) -> ServiceResult[bool]:
        """Initialize the service."""
        pass
    
    @abstractmethod
    async def health_check(self) -> ServiceResult[Dict[str, Any]]:
        """Perform a health check on the service."""
        pass
    
    @abstractmethod
    async def cleanup(self) -> ServiceResult[bool]:
        """Clean up resources used by the service."""
        pass


class IUseCase(Generic[TRequest, TResponse], ABC):
    """
    Base interface for use cases (application services).
    
    Use cases represent business workflows and coordinate
    between domain services and infrastructure.
    """
    
    @abstractmethod
    async def execute(self, request: TRequest) -> ServiceResult[TResponse]:
        """Execute the use case with the given request."""
        pass


class IDomainService(IService):
    """
    Base interface for domain services.
    
    Domain services contain business logic and rules
    that don't naturally fit within entity models.
    """
    pass


class IApplicationService(IService):
    """
    Base interface for application services (use cases).
    
    Application services orchestrate business workflows
    by coordinating domain services and infrastructure services.
    """
    pass


class IInfrastructureService(IService):
    """
    Base interface for infrastructure services.
    
    Infrastructure services handle integration with
    external systems like databases, file storage, email, etc.
    """
    pass


class IRepository(Generic[T], ABC):
    """
    Base interface for repositories.
    
    Repositories abstract data access operations and provide
    a consistent interface for working with entities.
    """
    
    @abstractmethod
    async def get_by_id(self, entity_id: str) -> ServiceResult[Optional[T]]:
        """Get an entity by its ID."""
        pass
    
    @abstractmethod
    async def create(self, entity: T) -> ServiceResult[T]:
        """Create a new entity."""
        pass
    
    @abstractmethod
    async def update(self, entity: T) -> ServiceResult[T]:
        """Update an existing entity."""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: str) -> ServiceResult[bool]:
        """Delete an entity by its ID."""
        pass


class IEventHandler(Generic[T], ABC):
    """
    Base interface for event handlers.
    
    Event handlers process domain events and can trigger
    side effects or update read models.
    """
    
    @abstractmethod
    async def handle(self, event: T) -> ServiceResult[bool]:
        """Handle the given event."""
        pass
    
    @abstractmethod
    def can_handle(self, event: Any) -> bool:
        """Check if this handler can process the given event."""
        pass


class IValidator(Generic[T], ABC):
    """
    Base interface for validators.
    
    Validators ensure that data meets business rules
    and constraints before processing.
    """
    
    @abstractmethod
    async def validate(self, data: T) -> ServiceResult[bool]:
        """Validate the given data."""
        pass
    
    @abstractmethod
    def get_validation_rules(self) -> Dict[str, Any]:
        """Get the validation rules for this validator."""
        pass


# Common exceptions for consistent error handling
class ServiceException(Exception):
    """Base exception for service-related errors."""
    
    def __init__(self, message: str, error_code: str = None, metadata: Dict[str, Any] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.metadata = metadata or {}


class ValidationException(ServiceException):
    """Exception raised when validation fails."""
    pass


class BusinessRuleException(ServiceException):
    """Exception raised when business rules are violated."""
    pass


class InfrastructureException(ServiceException):
    """Exception raised when infrastructure operations fail."""
    pass


class RepositoryException(ServiceException):
    """Exception raised when repository operations fail."""
    pass
