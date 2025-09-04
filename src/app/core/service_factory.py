"""
Enhanced service factory for creating and managing application services.

This factory integrates with the dependency injection container and existing
AWS service factory to provide centralized service creation and lifecycle management.
"""

import logging
from typing import Optional, Dict, Any, Type, TypeVar
from datetime import datetime

from .config import get_settings
from .container import DependencyContainer, get_container
from ..services.aws_service_factory import AWSServiceFactory
from ..database.connection import RDSConnectionManager, ConnectionConfig
from src.config.aws_config import AWSConfig, AWSConfigManager

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ApplicationServiceFactory:
    """
    Enhanced service factory that coordinates between the DI container 
    and AWS service factory for comprehensive service management.
    """
    
    def __init__(
        self,
        container: Optional[DependencyContainer] = None,
        aws_config: Optional[AWSConfig] = None
    ):
        self.container = container or get_container()
        self.aws_config = aws_config
        self.aws_service_factory: Optional[AWSServiceFactory] = None
        self.db_manager: Optional[RDSConnectionManager] = None
        self.settings = get_settings()
        self._initialized = False
        self._startup_time: Optional[datetime] = None
    
    async def initialize(self) -> bool:
        """
        Initialize the service factory and all its dependencies.
        
        Returns:
            bool: True if initialization successful
        """
        try:
            logger.info("Initializing Application Service Factory")
            self._startup_time = datetime.utcnow()
            
            # Initialize AWS services if configuration is available
            await self._initialize_aws_services()
            
            # Initialize database connection manager
            await self._initialize_database_manager()
            
            # Register all services in the DI container
            await self._register_services()
            
            # Initialize the DI container
            await self.container.initialize_all()
            
            self._initialized = True
            startup_duration = (datetime.utcnow() - self._startup_time).total_seconds()
            logger.info(f"Application Service Factory initialized successfully in {startup_duration:.2f}s")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Application Service Factory: {e}", exc_info=True)
            await self.cleanup()
            return False
    
    async def _initialize_aws_services(self) -> None:
        """Initialize AWS service factory if configuration is available."""
        try:
            if not self.aws_config:
                # Try to load AWS config from environment
                try:
                    self.aws_config = AWSConfigManager.load_config(self.settings.environment)
                except Exception as e:
                    logger.warning(f"AWS configuration not available: {e}")
                    return
            
            if self.aws_config:
                logger.info("Initializing AWS Service Factory")
                self.aws_service_factory = AWSServiceFactory(self.aws_config)
                
                success = await self.aws_service_factory.initialize()
                if success:
                    logger.info("AWS Service Factory initialized successfully")
                else:
                    logger.warning("AWS Service Factory initialization failed")
                    self.aws_service_factory = None
            
        except Exception as e:
            logger.warning(f"Failed to initialize AWS services: {e}")
            self.aws_service_factory = None
    
    async def _initialize_database_manager(self) -> None:
        """Initialize database connection manager."""
        try:
            if self.aws_service_factory and self.aws_service_factory.rds_manager:
                # Use RDS manager from AWS service factory
                self.db_manager = self.aws_service_factory.rds_manager
                logger.info("Using RDS manager from AWS Service Factory")
            else:
                # Create standalone database manager for development
                logger.info("Creating standalone database manager")
                # This would need database configuration from settings
                # For now, we'll skip standalone DB manager creation
                logger.warning("No database manager available - some services may not work")
        
        except Exception as e:
            logger.error(f"Failed to initialize database manager: {e}")
            raise
    
    async def _register_services(self) -> None:
        """Register all services with the DI container."""
        logger.info("Registering services with DI container")
        
        # Register core infrastructure services
        await self._register_infrastructure_services()
        
        # Register business domain services  
        await self._register_domain_services()
        
        # Register application use case services
        await self._register_application_services()
        
        # Register AWS-integrated services
        await self._register_aws_services()
    
    async def _register_infrastructure_services(self) -> None:
        """Register infrastructure services."""
        from ..services.user_service import UserService
        from ..services.job_service import JobService
        from ..services.file_service import FileService
        from ..services.queue_service import QueueService
        
        # Register database manager if available
        if self.db_manager:
            self.container.register_instance(RDSConnectionManager, self.db_manager)
        
        # Register core services with database dependencies
        if self.db_manager:
            self.container.register_factory(
                UserService,
                lambda: UserService()
            )
            
            self.container.register_factory(
                JobService,
                lambda: JobService(self.db_manager)
            )
            
            self.container.register_factory(
                FileService,
                lambda: FileService(self.db_manager)
            )
        
        # Register queue service (in-memory for now)
        self.container.register_singleton(QueueService, QueueService)
    
    async def _register_domain_services(self) -> None:
        """Register domain services."""
        # Import domain services as they become available
        # from ..services.domain import VideoGenerationService
        # self.container.register_singleton(IVideoGenerationService, VideoGenerationService)
        pass
    
    async def _register_application_services(self) -> None:
        """Register application use case services."""
        # Import application services as they become available
        # from ..services.application import VideoGenerationUseCase
        # self.container.register_singleton(IVideoGenerationUseCase, VideoGenerationUseCase)
        pass
    
    async def _register_aws_services(self) -> None:
        """Register AWS-integrated services."""
        if not self.aws_service_factory:
            logger.info("AWS Service Factory not available - skipping AWS service registration")
            return
        
        from ..services.aws_service_factory import AWSServiceFactory
        from ..services.aws_video_service import AWSVideoService
        from ..services.aws_s3_file_service import AWSS3FileService
        from ..services.aws_job_service import AWSJobService
        from ..services.aws_user_service import AWSUserService
        
        # Register AWS service factory as singleton instance
        self.container.register_instance(AWSServiceFactory, self.aws_service_factory)
        
        # Register AWS services as factories (created on demand)
        self.container.register_factory(
            AWSVideoService,
            lambda: self.aws_service_factory.create_video_service()
        )
        
        self.container.register_factory(
            AWSS3FileService,
            lambda: self.aws_service_factory.create_file_service()
        )
        
        self.container.register_factory(
            AWSJobService,
            lambda: self.aws_service_factory.create_job_service()
        )
        
        self.container.register_factory(
            AWSUserService,
            lambda: self.aws_service_factory.create_user_service()
        )
    
    async def cleanup(self) -> None:
        """Cleanup all services and resources."""
        logger.info("Cleaning up Application Service Factory")
        
        try:
            # Cleanup DI container
            await self.container.cleanup_all()
            
            # Cleanup AWS service factory
            if self.aws_service_factory:
                await self.aws_service_factory.close()
            
            self._initialized = False
            logger.info("Application Service Factory cleanup completed")
            
        except Exception as e:
            logger.error(f"Error during cleanup: {e}", exc_info=True)
    
    def get_service(self, service_type: Type[T]) -> T:
        """
        Get a service instance from the container.
        
        Args:
            service_type: The service type/interface to resolve
            
        Returns:
            Service instance
        """
        if not self._initialized:
            raise RuntimeError("Service factory not initialized")
        
        return self.container.resolve(service_type)
    
    async def get_service_async(self, service_type: Type[T]) -> T:
        """
        Get a service instance asynchronously from the container.
        
        Args:
            service_type: The service type/interface to resolve
            
        Returns:
            Service instance
        """
        if not self._initialized:
            raise RuntimeError("Service factory not initialized")
        
        return await self.container.resolve_async(service_type)
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get comprehensive health status of all services."""
        container_health = self.container.get_health_status()
        
        aws_health = {}
        if self.aws_service_factory:
            try:
                # Note: This would need to be made async in a real implementation
                aws_health = {"status": "available", "initialized": self.aws_service_factory.is_initialized()}
            except Exception as e:
                aws_health = {"status": "error", "error": str(e)}
        else:
            aws_health = {"status": "not_available"}
        
        return {
            "factory_initialized": self._initialized,
            "startup_time": self._startup_time.isoformat() if self._startup_time else None,
            "container": container_health,
            "aws_services": aws_health,
            "database": {
                "available": self.db_manager is not None,
                "type": "rds" if self.db_manager else "none"
            }
        }
    
    def is_initialized(self) -> bool:
        """Check if the service factory is initialized."""
        return self._initialized


# Global service factory instance
_service_factory: Optional[ApplicationServiceFactory] = None


def get_service_factory() -> ApplicationServiceFactory:
    """Get the global service factory instance."""
    global _service_factory
    if _service_factory is None:
        _service_factory = ApplicationServiceFactory()
    return _service_factory


def set_service_factory(factory: ApplicationServiceFactory) -> None:
    """Set the global service factory instance."""
    global _service_factory
    _service_factory = factory


async def initialize_service_factory(
    aws_config: Optional[AWSConfig] = None,
    container: Optional[DependencyContainer] = None
) -> ApplicationServiceFactory:
    """
    Initialize the global service factory.
    
    Args:
        aws_config: Optional AWS configuration
        container: Optional DI container
        
    Returns:
        Initialized service factory
    """
    factory = ApplicationServiceFactory(container=container, aws_config=aws_config)
    success = await factory.initialize()
    
    if success:
        set_service_factory(factory)
        return factory
    else:
        raise RuntimeError("Failed to initialize service factory")


async def cleanup_service_factory() -> None:
    """Cleanup the global service factory."""
    global _service_factory
    if _service_factory:
        await _service_factory.cleanup()
        _service_factory = None
