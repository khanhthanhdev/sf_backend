"""
Dependency Injection Container for Service Layer Management.

This module provides a comprehensive dependency injection container that manages
service lifecycles, resolves dependencies, and enables proper SOLID principles
implementation throughout the application.
"""

import logging
import asyncio
from typing import Type, TypeVar, Dict, Any, Callable, Optional, Union, List
from abc import ABC, abstractmethod
from enum import Enum
import inspect

from ..interfaces.base import IService

logger = logging.getLogger(__name__)

T = TypeVar('T')


class ServiceLifetime(Enum):
    """Service lifetime enumeration."""
    SINGLETON = "singleton"
    TRANSIENT = "transient"
    SCOPED = "scoped"


class ServiceRegistration:
    """Service registration information."""
    
    def __init__(
        self,
        interface: Type[T],
        implementation: Type[T],
        lifetime: ServiceLifetime,
        factory: Optional[Callable[[], T]] = None,
        instance: Optional[T] = None
    ):
        self.interface = interface
        self.implementation = implementation
        self.lifetime = lifetime
        self.factory = factory
        self.instance = instance


class DIContainer:
    """Dependency injection container with lifecycle management."""
    
    def __init__(self):
        """Initialize the dependency injection container."""
        self._registrations: Dict[Type, ServiceRegistration] = {}
        self._singletons: Dict[Type, Any] = {}
        self._scoped_instances: Dict[Type, Any] = {}
        self._resolution_stack: List[Type] = []
        
    def register_singleton(
        self, 
        interface: Type[T], 
        implementation: Type[T] = None,
        factory: Callable[[], T] = None,
        instance: T = None
    ) -> 'DIContainer':
        """
        Register a service as singleton (single instance for application lifetime).
        
        Args:
            interface: Service interface type
            implementation: Concrete implementation type
            factory: Factory function to create instance
            instance: Pre-created instance
            
        Returns:
            Self for method chaining
        """
        if instance is not None:
            self._singletons[interface] = instance
            
        self._registrations[interface] = ServiceRegistration(
            interface=interface,
            implementation=implementation or interface,
            lifetime=ServiceLifetime.SINGLETON,
            factory=factory,
            instance=instance
        )
        
        logger.debug(f"Registered singleton service: {interface.__name__}")
        return self
    
    def register_transient(
        self, 
        interface: Type[T], 
        implementation: Type[T] = None,
        factory: Callable[[], T] = None
    ) -> 'DIContainer':
        """
        Register a service as transient (new instance every time).
        
        Args:
            interface: Service interface type
            implementation: Concrete implementation type
            factory: Factory function to create instance
            
        Returns:
            Self for method chaining
        """
        self._registrations[interface] = ServiceRegistration(
            interface=interface,
            implementation=implementation or interface,
            lifetime=ServiceLifetime.TRANSIENT,
            factory=factory
        )
        
        logger.debug(f"Registered transient service: {interface.__name__}")
        return self
    
    def register_scoped(
        self, 
        interface: Type[T], 
        implementation: Type[T] = None,
        factory: Callable[[], T] = None
    ) -> 'DIContainer':
        """
        Register a service as scoped (single instance per scope/request).
        
        Args:
            interface: Service interface type
            implementation: Concrete implementation type
            factory: Factory function to create instance
            
        Returns:
            Self for method chaining
        """
        self._registrations[interface] = ServiceRegistration(
            interface=interface,
            implementation=implementation or interface,
            lifetime=ServiceLifetime.SCOPED,
            factory=factory
        )
        
        logger.debug(f"Registered scoped service: {interface.__name__}")
        return self
    
    def register_factory(
        self, 
        interface: Type[T], 
        factory: Callable[[], T],
        lifetime: ServiceLifetime = ServiceLifetime.TRANSIENT
    ) -> 'DIContainer':
        """
        Register a service with a factory function.
        
        Args:
            interface: Service interface type
            factory: Factory function to create instance
            lifetime: Service lifetime
            
        Returns:
            Self for method chaining
        """
        registration_method = {
            ServiceLifetime.SINGLETON: self.register_singleton,
            ServiceLifetime.TRANSIENT: self.register_transient,
            ServiceLifetime.SCOPED: self.register_scoped
        }[lifetime]
        
        return registration_method(interface, factory=factory)
    
    def resolve(self, interface: Type[T]) -> T:
        """
        Resolve a service instance by interface type.
        
        Args:
            interface: Service interface type to resolve
            
        Returns:
            Service instance
            
        Raises:
            ValueError: If service is not registered or circular dependency detected
        """
        # Check for circular dependencies
        if interface in self._resolution_stack:
            circular_path = " -> ".join([t.__name__ for t in self._resolution_stack] + [interface.__name__])
            raise ValueError(f"Circular dependency detected: {circular_path}")
        
        # Check if service is registered
        if interface not in self._registrations:
            raise ValueError(f"Service {interface.__name__} is not registered")
        
        registration = self._registrations[interface]
        
        # Handle different lifetimes
        if registration.lifetime == ServiceLifetime.SINGLETON:
            return self._resolve_singleton(interface, registration)
        elif registration.lifetime == ServiceLifetime.SCOPED:
            return self._resolve_scoped(interface, registration)
        else:  # TRANSIENT
            return self._resolve_transient(interface, registration)
    
    def _resolve_singleton(self, interface: Type[T], registration: ServiceRegistration) -> T:
        """Resolve singleton service instance."""
        if interface in self._singletons:
            return self._singletons[interface]
        
        instance = self._create_instance(registration)
        self._singletons[interface] = instance
        return instance
    
    def _resolve_scoped(self, interface: Type[T], registration: ServiceRegistration) -> T:
        """Resolve scoped service instance."""
        if interface in self._scoped_instances:
            return self._scoped_instances[interface]
        
        instance = self._create_instance(registration)
        self._scoped_instances[interface] = instance
        return instance
    
    def _resolve_transient(self, interface: Type[T], registration: ServiceRegistration) -> T:
        """Resolve transient service instance."""
        return self._create_instance(registration)
    
    def _create_instance(self, registration: ServiceRegistration) -> Any:
        """Create service instance using registration information."""
        self._resolution_stack.append(registration.interface)
        
        try:
            # Use pre-created instance if available
            if registration.instance is not None:
                return registration.instance
            
            # Use factory if provided
            if registration.factory is not None:
                return registration.factory()
            
            # Use constructor injection
            return self._create_with_constructor_injection(registration.implementation)
            
        finally:
            self._resolution_stack.pop()
    
    def _create_with_constructor_injection(self, implementation_type: Type[T]) -> T:
        """Create instance using constructor dependency injection."""
        try:
            # Get constructor signature
            signature = inspect.signature(implementation_type.__init__)
            
            # Resolve constructor parameters
            kwargs = {}
            for param_name, param in signature.parameters.items():
                if param_name == 'self':
                    continue
                
                # Get parameter type annotation
                param_type = param.annotation
                if param_type == inspect.Parameter.empty:
                    if param.default != inspect.Parameter.empty:
                        continue  # Skip optional parameters without type hints
                    else:
                        raise ValueError(
                            f"Parameter '{param_name}' in {implementation_type.__name__} "
                            f"has no type annotation"
                        )
                
                # Handle optional parameters
                if param.default != inspect.Parameter.empty:
                    if param_type in self._registrations:
                        kwargs[param_name] = self.resolve(param_type)
                    # If not registered and has default, use default (None)
                    continue
                
                # Resolve required parameter
                if param_type not in self._registrations:
                    raise ValueError(
                        f"Required dependency {param_type.__name__} for "
                        f"{implementation_type.__name__} is not registered"
                    )
                
                kwargs[param_name] = self.resolve(param_type)
            
            # Create instance
            instance = implementation_type(**kwargs)
            
            logger.debug(f"Created instance of {implementation_type.__name__} with dependencies: {list(kwargs.keys())}")
            return instance
            
        except Exception as e:
            logger.error(f"Failed to create instance of {implementation_type.__name__}: {e}")
            raise
    
    def clear_scoped(self) -> None:
        """Clear scoped service instances (call at end of request/scope)."""
        self._scoped_instances.clear()
        logger.debug("Cleared scoped service instances")
    
    def get_registrations(self) -> Dict[Type, ServiceRegistration]:
        """Get all service registrations (for debugging/inspection)."""
        return self._registrations.copy()
    
    def is_registered(self, interface: Type) -> bool:
        """Check if a service is registered."""
        return interface in self._registrations
    
    async def initialize_services(self) -> None:
        """Initialize all singleton services that implement IService."""
        logger.info("Initializing singleton services...")
        
        for interface, registration in self._registrations.items():
            if registration.lifetime == ServiceLifetime.SINGLETON:
                try:
                    instance = self.resolve(interface)
                    
                    # If service implements IService, call initialize
                    if isinstance(instance, IService):
                        await instance.initialize()
                        logger.debug(f"Initialized service: {instance.service_name}")
                        
                except Exception as e:
                    logger.error(f"Failed to initialize service {interface.__name__}: {e}")
                    raise
        
        logger.info("All singleton services initialized successfully")
    
    async def cleanup_services(self) -> None:
        """Cleanup all singleton services that implement IService."""
        logger.info("Cleaning up singleton services...")
        
        for interface in self._singletons:
            try:
                instance = self._singletons[interface]
                
                # If service implements IService, call cleanup
                if isinstance(instance, IService):
                    await instance.cleanup()
                    logger.debug(f"Cleaned up service: {instance.service_name}")
                    
            except Exception as e:
                logger.error(f"Failed to cleanup service {interface.__name__}: {e}")
                # Continue cleanup for other services
        
        # Clear all singletons
        self._singletons.clear()
        logger.info("All singleton services cleaned up")


class ServiceContainerBuilder:
    """Builder for creating and configuring dependency injection container."""
    
    def __init__(self):
        """Initialize the container builder."""
        self.container = DIContainer()
    
    def add_singleton(
        self, 
        interface: Type[T], 
        implementation: Type[T] = None,
        factory: Callable[[], T] = None,
        instance: T = None
    ) -> 'ServiceContainerBuilder':
        """Add singleton service registration."""
        self.container.register_singleton(interface, implementation, factory, instance)
        return self
    
    def add_transient(
        self, 
        interface: Type[T], 
        implementation: Type[T] = None,
        factory: Callable[[], T] = None
    ) -> 'ServiceContainerBuilder':
        """Add transient service registration."""
        self.container.register_transient(interface, implementation, factory)
        return self
    
    def add_scoped(
        self, 
        interface: Type[T], 
        implementation: Type[T] = None,
        factory: Callable[[], T] = None
    ) -> 'ServiceContainerBuilder':
        """Add scoped service registration."""
        self.container.register_scoped(interface, implementation, factory)
        return self
    
    def build(self) -> DIContainer:
        """Build and return the configured container."""
        return self.container


# Global container instance (can be replaced with FastAPI dependency override)
_global_container: Optional[DIContainer] = None


def get_container() -> DIContainer:
    """Get the global DI container instance."""
    global _global_container
    if _global_container is None:
        raise RuntimeError("DI Container not initialized. Call setup_container() first.")
    return _global_container


def setup_container(container: DIContainer) -> None:
    """Set up the global DI container."""
    global _global_container
    _global_container = container
    logger.info("Global DI container configured")


def reset_container() -> None:
    """Reset the global DI container (for testing)."""
    global _global_container
    _global_container = None
    logger.info("Global DI container reset")
