"""
Service Factory for Configuring SOLID-Principle Based Service Layer.

This module provides factory functions for creating and configuring the complete
service layer with proper dependency injection, following SOLID principles.
"""

import logging
from typing import Dict, Any, Optional

from .dependency_injection import DIContainer, ServiceContainerBuilder
from .interfaces.base import IService
from .interfaces.domain import (
    IVideoGenerationService,
    IJobManagementService,
    IFileProcessingService,
    IUserManagementService,
    INotificationService
)
from .interfaces.application import (
    IVideoGenerationUseCase,
    IJobManagementUseCase,
    IFileManagementUseCase,
    IUserManagementUseCase
)
from .interfaces.infrastructure import (
    IQueueService,
    IStorageService,
    IEmailService,
    IMetricsService,
    ILoggingService
)

# Domain service implementations
from .domain.video_generation import VideoGenerationService
from .domain.job_management import JobManagementService
from .domain.file_processing import FileProcessingService
from .domain.user_management import UserManagementService
from .domain.notification import NotificationService

# Application service implementations
from .application.video_generation_use_case import VideoGenerationUseCase
from .application.job_management_use_case import JobManagementUseCase
from .application.file_management_use_case import FileManagementUseCase
from .application.user_management_use_case import UserManagementUseCase

# Infrastructure service implementations
from .infrastructure.queue_service import InMemoryQueueService, RedisQueueService
from .infrastructure.storage_service import S3StorageService, LocalStorageService
from .infrastructure.email_service import SESEmailService, SMTPEmailService, ConsoleEmailService
from .infrastructure.metrics_service import CloudWatchMetricsService, ConsoleMetricsService
from .infrastructure.logging_service import StructuredLoggingService

logger = logging.getLogger(__name__)


class ServiceFactory:
    """Factory for creating and configuring services with dependency injection."""
    
    @staticmethod
    def create_container(config: Dict[str, Any]) -> DIContainer:
        """
        Create and configure dependency injection container.
        
        Args:
            config: Application configuration dictionary
            
        Returns:
            Configured DIContainer instance
        """
        logger.info("Creating service container with SOLID principles")
        
        builder = ServiceContainerBuilder()
        
        # Configure infrastructure services (external dependencies)
        ServiceFactory._configure_infrastructure_services(builder, config)
        
        # Configure domain services (business logic)
        ServiceFactory._configure_domain_services(builder, config)
        
        # Configure application services (use cases)
        ServiceFactory._configure_application_services(builder, config)
        
        container = builder.build()
        logger.info("Service container created successfully")
        
        return container
    
    @staticmethod
    def _configure_infrastructure_services(
        builder: ServiceContainerBuilder, 
        config: Dict[str, Any]
    ) -> None:
        """Configure infrastructure layer services."""
        logger.debug("Configuring infrastructure services")
        
        # Queue Service
        queue_config = config.get('queue', {})
        if queue_config.get('provider') == 'redis':
            builder.add_singleton(
                IQueueService,
                factory=lambda: RedisQueueService(queue_config.get('redis', {}))
            )
        else:
            builder.add_singleton(IQueueService, InMemoryQueueService)
        
        # Storage Service
        storage_config = config.get('storage', {})
        if storage_config.get('provider') == 's3':
            builder.add_singleton(
                IStorageService,
                factory=lambda: S3StorageService(storage_config.get('aws', {}))
            )
        else:
            builder.add_singleton(
                IStorageService,
                factory=lambda: LocalStorageService(storage_config.get('path'))
            )
        
        # Email Service
        email_config = config.get('email', {})
        email_provider = email_config.get('provider', 'console')
        
        if email_provider == 'ses':
            builder.add_singleton(
                IEmailService,
                factory=lambda: SESEmailService(email_config.get('aws', {}))
            )
        elif email_provider == 'smtp':
            builder.add_singleton(
                IEmailService,
                factory=lambda: SMTPEmailService(email_config.get('smtp', {}))
            )
        else:
            builder.add_singleton(IEmailService, ConsoleEmailService)
        
        # Metrics Service
        metrics_config = config.get('metrics', {})
        if metrics_config.get('provider') == 'cloudwatch':
            builder.add_singleton(
                IMetricsService,
                factory=lambda: CloudWatchMetricsService(metrics_config.get('aws', {}))
            )
        else:
            builder.add_singleton(IMetricsService, ConsoleMetricsService)
        
        # Logging Service
        logging_config = config.get('logging', {})
        builder.add_singleton(
            ILoggingService,
            factory=lambda: StructuredLoggingService(logging_config)
        )
        
        logger.debug("Infrastructure services configured")
    
    @staticmethod
    def _configure_domain_services(
        builder: ServiceContainerBuilder, 
        config: Dict[str, Any]
    ) -> None:
        """Configure domain layer services (business logic)."""
        logger.debug("Configuring domain services")
        
        # Domain services are typically singletons as they contain stateless business logic
        builder.add_singleton(IVideoGenerationService, VideoGenerationService)
        builder.add_singleton(IJobManagementService, JobManagementService)
        builder.add_singleton(IFileProcessingService, FileProcessingService)
        builder.add_singleton(IUserManagementService, UserManagementService)
        builder.add_singleton(INotificationService, NotificationService)
        
        logger.debug("Domain services configured")
    
    @staticmethod
    def _configure_application_services(
        builder: ServiceContainerBuilder, 
        config: Dict[str, Any]
    ) -> None:
        """Configure application layer services (use cases)."""
        logger.debug("Configuring application services")
        
        # Application services orchestrate domain services and can be singletons
        # since they typically don't hold state between requests
        builder.add_singleton(IVideoGenerationUseCase, VideoGenerationUseCase)
        builder.add_singleton(IJobManagementUseCase, JobManagementUseCase)
        builder.add_singleton(IFileManagementUseCase, FileManagementUseCase)
        builder.add_singleton(IUserManagementUseCase, UserManagementUseCase)
        
        logger.debug("Application services configured")
    
    @staticmethod
    def create_development_container() -> DIContainer:
        """Create container with development-friendly configuration."""
        config = {
            'queue': {'provider': 'memory'},
            'storage': {'provider': 'local', 'path': '/tmp/dev_storage'},
            'email': {'provider': 'console'},
            'metrics': {'provider': 'console'},
            'logging': {'level': 'DEBUG', 'format': 'detailed'}
        }
        
        return ServiceFactory.create_container(config)
    
    @staticmethod
    def create_production_container(
        aws_config: Dict[str, Any],
        redis_config: Optional[Dict[str, Any]] = None
    ) -> DIContainer:
        """Create container with production configuration."""
        config = {
            'queue': {
                'provider': 'redis' if redis_config else 'memory',
                'redis': redis_config or {}
            },
            'storage': {
                'provider': 's3',
                'aws': aws_config
            },
            'email': {
                'provider': 'ses',
                'aws': aws_config
            },
            'metrics': {
                'provider': 'cloudwatch',
                'aws': aws_config
            },
            'logging': {'level': 'INFO', 'format': 'json'}
        }
        
        return ServiceFactory.create_container(config)
    
    @staticmethod
    def create_test_container() -> DIContainer:
        """Create container with test-friendly configuration."""
        config = {
            'queue': {'provider': 'memory'},
            'storage': {'provider': 'local', 'path': '/tmp/test_storage'},
            'email': {'provider': 'console'},
            'metrics': {'provider': 'console'},
            'logging': {'level': 'WARNING', 'format': 'simple'}
        }
        
        return ServiceFactory.create_container(config)


class ServiceHealthChecker:
    """Health checker for service layer components."""
    
    def __init__(self, container: DIContainer):
        """Initialize health checker with service container."""
        self.container = container
    
    async def check_service_health(self) -> Dict[str, Any]:
        """
        Check health of all registered services.
        
        Returns:
            Dictionary with health status of each service
        """
        health_status = {
            'overall_status': 'healthy',
            'services': {},
            'unhealthy_services': []
        }
        
        registrations = self.container.get_registrations()
        
        for interface, registration in registrations.items():
            service_name = interface.__name__
            
            try:
                # Resolve service to check if it can be created
                service = self.container.resolve(interface)
                
                # If service implements IService, check its health
                if isinstance(service, IService):
                    health_result = await service.health_check()
                    health_status['services'][service_name] = {
                        'status': 'healthy' if health_result.success else 'unhealthy',
                        'details': health_result.data if health_result.success else health_result.error,
                        'service_type': registration.lifetime.value
                    }
                    
                    if not health_result.success:
                        health_status['unhealthy_services'].append(service_name)
                else:
                    health_status['services'][service_name] = {
                        'status': 'healthy',
                        'details': 'Service created successfully',
                        'service_type': registration.lifetime.value
                    }
                    
            except Exception as e:
                health_status['services'][service_name] = {
                    'status': 'unhealthy',
                    'details': str(e),
                    'service_type': registration.lifetime.value
                }
                health_status['unhealthy_services'].append(service_name)
        
        # Set overall status
        if health_status['unhealthy_services']:
            health_status['overall_status'] = 'unhealthy'
        
        return health_status
    
    async def check_dependencies(self) -> Dict[str, Any]:
        """
        Check if all service dependencies can be resolved.
        
        Returns:
            Dictionary with dependency resolution status
        """
        dependency_status = {
            'overall_status': 'resolved',
            'services': {},
            'unresolved_dependencies': []
        }
        
        registrations = self.container.get_registrations()
        
        for interface, registration in registrations.items():
            service_name = interface.__name__
            
            try:
                # Attempt to resolve the service
                self.container.resolve(interface)
                dependency_status['services'][service_name] = {
                    'status': 'resolved',
                    'dependencies': 'All dependencies satisfied'
                }
                
            except Exception as e:
                dependency_status['services'][service_name] = {
                    'status': 'unresolved',
                    'error': str(e)
                }
                dependency_status['unresolved_dependencies'].append(service_name)
        
        # Set overall status
        if dependency_status['unresolved_dependencies']:
            dependency_status['overall_status'] = 'unresolved'
        
        return dependency_status
