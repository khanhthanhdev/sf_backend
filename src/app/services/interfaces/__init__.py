"""
Service interfaces for dependency injection and abstraction.
"""

from .base import IService
from .domain import (
    IVideoGenerationService,
    IJobManagementService,
    IFileProcessingService,
    IUserManagementService,
    INotificationService
)
from .application import (
    IVideoGenerationUseCase,
    IJobManagementUseCase,
    IFileManagementUseCase,
    IUserManagementUseCase
)
from .infrastructure import (
    IQueueService,
    IStorageService,
    IExternalAPIService,
    IEmailService,
    IMetricsService,
    ILoggingService
)

__all__ = [
    # Base
    'IService',
    
    # Domain Services
    'IVideoGenerationService',
    'IJobManagementService',
    'IFileProcessingService',
    'IUserManagementService',
    'INotificationService',
    
    # Application Services (Use Cases)
    'IVideoGenerationUseCase',
    'IJobManagementUseCase',
    'IFileManagementUseCase',
    'IUserManagementUseCase',
    
    # Infrastructure Services
    'IQueueService',
    'IStorageService',
    'IExternalAPIService',
    'IEmailService',
    'IMetricsService',
    'ILoggingService'
]
