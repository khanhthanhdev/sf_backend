"""
Dependency injection container for service layer.

This module provides a dependency injection container that manages
service instances and their dependencies following SOLID principles.
"""

from typing import Dict, Any, Type, TypeVar, Generic, Optional, Callable, Awaitable, Union, List
from abc import ABC, abstractmethod
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

T = TypeVar('T')


class IDependencyContainer(ABC):
    """Interface for dependency injection container."""
    
    @abstractmethod
    def register_singleton(self, interface: Type[T], implementation: Type[T]) -> None:
        """Register a singleton service implementation."""
        pass
    
    @abstractmethod
    def register_transient(self, interface: Type[T], implementation: Type[T]) -> None:
        """Register a transient service implementation."""
        pass
    
    @abstractmethod
    def register_instance(self, interface: Type[T], instance: T) -> None:
        """Register a specific instance."""
        pass
    
    @abstractmethod
    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory function for creating service instances."""
        pass
    
    @abstractmethod
    def register_async_factory(self, interface: Type[T], factory: Callable[[], Awaitable[T]]) -> None:
        """Register an async factory function for creating service instances."""
        pass
    
    @abstractmethod
    def resolve(self, interface: Type[T]) -> T:
        """Resolve service instance."""
        pass
    
    @abstractmethod
    async def resolve_async(self, interface: Type[T]) -> T:
        """Resolve service instance asynchronously."""
        pass
    
    @abstractmethod
    async def initialize_all(self) -> None:
        """Initialize all registered services."""
        pass
    
    @abstractmethod
    async def cleanup_all(self) -> None:
        """Cleanup all registered services."""
        pass
    
    @abstractmethod
    def add_dependency(self, dependent: Type, dependency: Type) -> None:
        """Add explicit dependency relationship for initialization order."""
        pass


class ServiceLifetime:
    """Service lifetime enumeration."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    INSTANCE = "instance"
    FACTORY = "factory"
    ASYNC_FACTORY = "async_factory"


class ServiceRegistration:
    """Service registration information."""
    
    def __init__(
        self, 
        interface: Type, 
        implementation: Optional[Type] = None, 
        lifetime: str = ServiceLifetime.TRANSIENT,
        instance: Any = None,
        factory: Optional[Callable] = None,
        async_factory: Optional[Callable[[], Awaitable[Any]]] = None,
        dependencies: Optional[List[Type]] = None
    ):
        self.interface = interface
        self.implementation = implementation
        self.lifetime = lifetime
        self.instance = instance
        self.factory = factory
        self.async_factory = async_factory
        self.dependencies = dependencies or []
        self.initialized = False
        self.initialization_order = 0


class DependencyContainer(IDependencyContainer):
    """
    Enhanced dependency injection container implementation.
    
    Supports singleton, transient, instance, factory, and async factory registrations
    with automatic dependency resolution, lifecycle management, and initialization ordering.
    """
    
    def __init__(self):
        self._registrations: Dict[Type, ServiceRegistration] = {}
        self._singletons: Dict[Type, Any] = {}
        self._dependencies: Dict[Type, List[Type]] = {}
        self._initialized = False
        self._initialization_order: List[Type] = []
        self._startup_time: Optional[datetime] = None
    
    def register_singleton(self, interface: Type[T], implementation: Type[T]) -> None:
        """Register a singleton service implementation."""
        self._registrations[interface] = ServiceRegistration(
            interface=interface,
            implementation=implementation,
            lifetime=ServiceLifetime.SINGLETON
        )
        logger.debug(f"Registered singleton: {interface.__name__} -> {implementation.__name__}")
    
    def register_transient(self, interface: Type[T], implementation: Type[T]) -> None:
        """Register a transient service implementation."""
        self._registrations[interface] = ServiceRegistration(
            interface=interface,
            implementation=implementation,
            lifetime=ServiceLifetime.TRANSIENT
        )
        logger.debug(f"Registered transient: {interface.__name__} -> {implementation.__name__}")
    
    def register_instance(self, interface: Type[T], instance: T) -> None:
        """Register a specific instance."""
        self._registrations[interface] = ServiceRegistration(
            interface=interface,
            implementation=type(instance),
            lifetime=ServiceLifetime.INSTANCE,
            instance=instance
        )
        logger.debug(f"Registered instance: {interface.__name__}")
    
    def register_factory(self, interface: Type[T], factory: Callable[[], T]) -> None:
        """Register a factory function for creating service instances."""
        self._registrations[interface] = ServiceRegistration(
            interface=interface,
            lifetime=ServiceLifetime.FACTORY,
            factory=factory
        )
        logger.debug(f"Registered factory: {interface.__name__}")
    
    def register_async_factory(self, interface: Type[T], factory: Callable[[], Awaitable[T]]) -> None:
        """Register an async factory function for creating service instances."""
        self._registrations[interface] = ServiceRegistration(
            interface=interface,
            lifetime=ServiceLifetime.ASYNC_FACTORY,
            async_factory=factory
        )
        logger.debug(f"Registered async factory: {interface.__name__}")
    
    def add_dependency(self, dependent: Type, dependency: Type) -> None:
        """Add explicit dependency relationship for initialization order."""
        if dependent not in self._dependencies:
            self._dependencies[dependent] = []
        self._dependencies[dependent].append(dependency)
        logger.debug(f"Added dependency: {dependent.__name__} depends on {dependency.__name__}")
    
    def resolve(self, interface: Type[T]) -> T:
        """Resolve service instance."""
        if interface not in self._registrations:
            raise ValueError(f"Service {interface.__name__} not registered")
        
        registration = self._registrations[interface]
        
        if registration.lifetime == ServiceLifetime.INSTANCE:
            return registration.instance
        
        elif registration.lifetime == ServiceLifetime.SINGLETON:
            if interface not in self._singletons:
                self._singletons[interface] = self._create_instance(registration)
            return self._singletons[interface]
        
        elif registration.lifetime == ServiceLifetime.TRANSIENT:
            return self._create_instance(registration)
        
        elif registration.lifetime == ServiceLifetime.FACTORY:
            if registration.factory is None:
                raise ValueError(f"Factory not provided for {interface.__name__}")
            try:
                return registration.factory()
            except Exception as e:
                logger.error(f"Factory failed for {interface.__name__}: {e}")
                raise
        
        elif registration.lifetime == ServiceLifetime.ASYNC_FACTORY:
            raise ValueError(f"Use resolve_async for async factory service {interface.__name__}")
        
        else:
            raise ValueError(f"Unknown service lifetime: {registration.lifetime}")
    
    async def resolve_async(self, interface: Type[T]) -> T:
        """Resolve service instance asynchronously."""
        if interface not in self._registrations:
            raise ValueError(f"Service {interface.__name__} not registered")
        
        registration = self._registrations[interface]
        
        if registration.lifetime == ServiceLifetime.ASYNC_FACTORY:
            if registration.async_factory is None:
                raise ValueError(f"Async factory not provided for {interface.__name__}")
            try:
                return await registration.async_factory()
            except Exception as e:
                logger.error(f"Async factory failed for {interface.__name__}: {e}")
                raise
        else:
            # For non-async factories, use regular resolve
            return self.resolve(interface)
    
    def _create_instance(self, registration: ServiceRegistration) -> Any:
        """Create service instance with dependency injection."""
        try:
            if registration.implementation is None:
                raise ValueError(f"No implementation provided for {registration.interface.__name__}")
            
            # Get constructor parameters
            import inspect
            signature = inspect.signature(registration.implementation.__init__)
            params = {}
            
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                
                # Check if parameter has type annotation
                if param.annotation != inspect.Parameter.empty:
                    # Resolve dependency
                    dependency = self.resolve(param.annotation)
                    params[param_name] = dependency
            
            # Create instance with resolved dependencies
            instance = registration.implementation(**params)
            logger.debug(f"Created instance: {registration.implementation.__name__}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create instance of {registration.implementation.__name__}: {e}")
            raise
    def _calculate_initialization_order(self) -> List[Type]:
        """Calculate the correct initialization order based on dependencies."""
        visited = set()
        temp_visited = set()
        order = []
        
        def visit(service_type: Type):
            if service_type in temp_visited:
                raise ValueError(f"Circular dependency detected involving {service_type.__name__}")
            if service_type in visited:
                return
            
            temp_visited.add(service_type)
            
            # Visit dependencies first
            for dependency in self._dependencies.get(service_type, []):
                if dependency in self._registrations:
                    visit(dependency)
            
            temp_visited.remove(service_type)
            visited.add(service_type)
            order.append(service_type)
        
        # Visit all registered services
        for service_type in self._registrations.keys():
            if service_type not in visited:
                visit(service_type)
        
        return order
    
    async def initialize_all(self) -> None:
        """Initialize all registered services in dependency order."""
        if self._initialized:
            return
        
        logger.info("Initializing all registered services")
        self._startup_time = datetime.utcnow()
        
        try:
            # Calculate initialization order
            self._initialization_order = self._calculate_initialization_order()
            
            # Initialize services in correct order
            for i, interface in enumerate(self._initialization_order):
                registration = self._registrations[interface]
                registration.initialization_order = i
                
                logger.debug(f"Initializing service {interface.__name__} (order: {i})")
                
                # Get or create the service instance
                if registration.lifetime == ServiceLifetime.SINGLETON:
                    service = self.resolve(interface)
                elif registration.lifetime == ServiceLifetime.INSTANCE:
                    service = registration.instance
                elif registration.lifetime == ServiceLifetime.ASYNC_FACTORY:
                    service = await self.resolve_async(interface)
                    # Store async factory result as singleton for subsequent access
                    self._singletons[interface] = service
                else:
                    # Transient and factory services are not initialized upfront
                    continue
                
                # Call initialize method if available
                if hasattr(service, 'initialize'):
                    try:
                        if asyncio.iscoroutinefunction(service.initialize):
                            await service.initialize()
                        else:
                            service.initialize()
                        registration.initialized = True
                        logger.debug(f"Initialized service {interface.__name__}")
                    except Exception as e:
                        logger.error(f"Failed to initialize service {interface.__name__}: {e}")
                        raise
            
            self._initialized = True
            startup_duration = (datetime.utcnow() - self._startup_time).total_seconds()
            logger.info(f"All services initialized successfully in {startup_duration:.2f}s")
            
        except Exception as e:
            logger.error(f"Service initialization failed: {e}")
            await self.cleanup_all()  # Cleanup any partially initialized services
            raise
    
    async def cleanup_all(self) -> None:
        """Cleanup all registered services in reverse initialization order."""
        if not self._initialized:
            return
        
        logger.info("Cleaning up all services")
        cleanup_start = datetime.utcnow()
        
        # Cleanup in reverse order
        cleanup_order = list(reversed(self._initialization_order))
        
        for interface in cleanup_order:
            registration = self._registrations[interface]
            
            if not registration.initialized:
                continue
            
            # Get the service instance
            service = None
            if registration.lifetime == ServiceLifetime.SINGLETON and interface in self._singletons:
                service = self._singletons[interface]
            elif registration.lifetime == ServiceLifetime.INSTANCE:
                service = registration.instance
            
            if service and hasattr(service, 'cleanup'):
                try:
                    logger.debug(f"Cleaning up service {interface.__name__}")
                    if asyncio.iscoroutinefunction(service.cleanup):
                        await service.cleanup()
                    else:
                        service.cleanup()
                    registration.initialized = False
                except Exception as e:
                    logger.error(f"Error cleaning up service {interface.__name__}: {e}")
        
        # Clear singleton instances
        self._singletons.clear()
        self._initialized = False
        
        cleanup_duration = (datetime.utcnow() - cleanup_start).total_seconds()
        logger.info(f"All services cleaned up in {cleanup_duration:.2f}s")
    
    def get_registration_info(self) -> Dict[str, Dict[str, Any]]:
        """Get information about all registered services."""
        info = {}
        for interface, registration in self._registrations.items():
            info[interface.__name__] = {
                "implementation": registration.implementation.__name__ if registration.implementation else "Factory",
                "lifetime": registration.lifetime,
                "has_instance": registration.lifetime == ServiceLifetime.INSTANCE,
                "is_singleton_created": interface in self._singletons,
                "initialized": registration.initialized,
                "initialization_order": registration.initialization_order,
                "dependencies": [dep.__name__ for dep in self._dependencies.get(interface, [])]
            }
        return info
    
    def get_health_status(self) -> Dict[str, Any]:
        """Get health status of the container and its services."""
        total_services = len(self._registrations)
        initialized_services = sum(1 for reg in self._registrations.values() if reg.initialized)
        
        return {
            "container_initialized": self._initialized,
            "startup_time": self._startup_time.isoformat() if self._startup_time else None,
            "total_services": total_services,
            "initialized_services": initialized_services,
            "singleton_instances": len(self._singletons),
            "health": "healthy" if self._initialized and initialized_services == total_services else "degraded"
        }


# Global container instance
_container: Optional[DependencyContainer] = None


def get_container() -> DependencyContainer:
    """Get the global container instance."""
    global _container
    if _container is None:
        _container = DependencyContainer()
    return _container


def set_container(container: DependencyContainer) -> None:
    """Set the global container instance."""
    global _container
    _container = container


async def initialize_container() -> None:
    """Initialize the global container."""
    container = get_container()
    await container.initialize_all()


async def cleanup_container() -> None:
    """Cleanup the global container."""
    container = get_container()
    await container.cleanup_all()
