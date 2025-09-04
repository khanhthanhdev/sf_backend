"""
Circuit Breaker Pattern Implementation

This module provides a robust circuit breaker implementation for handling
external service failures gracefully. The circuit breaker prevents cascading
failures by temporarily disabling calls to failing services.

Features:
- Configurable failure thresholds and timeouts
- Exponential backoff for recovery attempts
- Comprehensive monitoring and metrics
- Integration with enhanced exception system
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Callable, Any, Optional, Dict, TypeVar, Generic, Awaitable
from dataclasses import dataclass, field
from contextlib import asynccontextmanager

from .enhanced_exceptions import (
    CircuitBreakerOpenException,
    ServiceTimeoutException,
    ExternalServiceException,
    ErrorContext,
    ErrorSeverity
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


class CircuitState(str, Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, blocking requests
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""
    failure_threshold: int = 5
    """Number of failures before opening circuit"""
    
    success_threshold: int = 3
    """Number of successes needed to close circuit from half-open"""
    
    timeout: int = 60
    """Timeout in seconds before attempting to close circuit"""
    
    call_timeout: int = 30
    """Maximum time to wait for individual calls"""
    
    expected_exception: type = Exception
    """Exception type that counts as failure"""
    
    exponential_backoff: bool = True
    """Whether to use exponential backoff for timeouts"""
    
    max_timeout: int = 300
    """Maximum timeout when using exponential backoff"""


@dataclass
class CircuitBreakerMetrics:
    """Metrics tracked by circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None
    state_change_time: Optional[datetime] = None
    circuit_opened_count: int = 0
    
    def reset_consecutive_counters(self):
        """Reset consecutive counters."""
        self.consecutive_failures = 0
        self.consecutive_successes = 0
    
    def record_success(self):
        """Record a successful call."""
        self.total_calls += 1
        self.successful_calls += 1
        self.consecutive_successes += 1
        self.consecutive_failures = 0
        self.last_success_time = datetime.utcnow()
    
    def record_failure(self):
        """Record a failed call."""
        self.total_calls += 1
        self.failed_calls += 1
        self.consecutive_failures += 1
        self.consecutive_successes = 0
        self.last_failure_time = datetime.utcnow()
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        if self.total_calls == 0:
            return 1.0
        return self.successful_calls / self.total_calls
    
    def get_failure_rate(self) -> float:
        """Calculate failure rate."""
        return 1.0 - self.get_success_rate()


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker implementation for external service calls.
    
    Provides automatic failure detection and recovery with configurable
    thresholds and timeouts. Integrates with the enhanced exception system
    for proper error handling and logging.
    """
    
    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker.
        
        Args:
            name: Unique name for this circuit breaker
            config: Configuration options
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics()
        self._lock = asyncio.Lock()
        
        logger.info(
            f"Circuit breaker '{name}' initialized",
            extra={
                "circuit_breaker": name,
                "config": {
                    "failure_threshold": self.config.failure_threshold,
                    "timeout": self.config.timeout,
                    "call_timeout": self.config.call_timeout
                }
            }
        )
    
    async def call(
        self,
        func: Callable[[], Awaitable[T]],
        *args,
        **kwargs
    ) -> T:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args: Function arguments
            **kwargs: Function keyword arguments
        
        Returns:
            Function result
        
        Raises:
            CircuitBreakerOpenException: When circuit is open
            ServiceTimeoutException: When call times out
            ExternalServiceException: When call fails
        """
        async with self._lock:
            await self._check_and_update_state()
        
        if self.state == CircuitState.OPEN:
            error_context = ErrorContext(
                operation=f"circuit_breaker_call_{self.name}",
                service_name=self.name,
                additional_data={
                    "circuit_state": self.state.value,
                    "consecutive_failures": self.metrics.consecutive_failures,
                    "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None
                }
            )
            
            raise CircuitBreakerOpenException(
                service_name=self.name,
                failure_count=self.metrics.consecutive_failures,
                context=error_context,
                severity=ErrorSeverity.HIGH
            )
        
        try:
            # Execute with timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs),
                timeout=self.config.call_timeout
            )
            
            # Record success
            await self._record_success()
            return result
            
        except asyncio.TimeoutError:
            await self._record_failure()
            
            error_context = ErrorContext(
                operation=f"circuit_breaker_timeout_{self.name}",
                service_name=self.name,
                additional_data={
                    "timeout": self.config.call_timeout,
                    "circuit_state": self.state.value
                }
            )
            
            raise ServiceTimeoutException(
                service_name=self.name,
                timeout=self.config.call_timeout,
                context=error_context,
                severity=ErrorSeverity.HIGH
            )
            
        except self.config.expected_exception as e:
            await self._record_failure()
            
            error_context = ErrorContext(
                operation=f"circuit_breaker_failure_{self.name}",
                service_name=self.name,
                additional_data={
                    "original_error": str(e),
                    "circuit_state": self.state.value,
                    "consecutive_failures": self.metrics.consecutive_failures
                }
            )
            
            # Re-raise as external service exception with context
            raise ExternalServiceException(
                service_name=self.name,
                message=f"Service call failed: {str(e)}",
                context=error_context,
                severity=ErrorSeverity.HIGH
            ) from e
    
    async def _check_and_update_state(self):
        """Check current state and update if necessary."""
        now = datetime.utcnow()
        
        if self.state == CircuitState.OPEN:
            # Check if timeout period has passed
            if (self.metrics.state_change_time and 
                now - self.metrics.state_change_time >= timedelta(seconds=self._get_current_timeout())):
                await self._set_state(CircuitState.HALF_OPEN)
        
        elif self.state == CircuitState.HALF_OPEN:
            # In half-open state, allow limited calls to test service
            if self.metrics.consecutive_successes >= self.config.success_threshold:
                await self._set_state(CircuitState.CLOSED)
            elif self.metrics.consecutive_failures > 0:
                await self._set_state(CircuitState.OPEN)
    
    async def _record_success(self):
        """Record successful call and update state if necessary."""
        async with self._lock:
            self.metrics.record_success()
            
            if self.state == CircuitState.HALF_OPEN:
                if self.metrics.consecutive_successes >= self.config.success_threshold:
                    await self._set_state(CircuitState.CLOSED)
            
            logger.debug(
                f"Circuit breaker '{self.name}' recorded success",
                extra={
                    "circuit_breaker": self.name,
                    "state": self.state.value,
                    "consecutive_successes": self.metrics.consecutive_successes,
                    "success_rate": self.metrics.get_success_rate()
                }
            )
    
    async def _record_failure(self):
        """Record failed call and update state if necessary."""
        async with self._lock:
            self.metrics.record_failure()
            
            if (self.state in [CircuitState.CLOSED, CircuitState.HALF_OPEN] and
                self.metrics.consecutive_failures >= self.config.failure_threshold):
                await self._set_state(CircuitState.OPEN)
            
            logger.warning(
                f"Circuit breaker '{self.name}' recorded failure",
                extra={
                    "circuit_breaker": self.name,
                    "state": self.state.value,
                    "consecutive_failures": self.metrics.consecutive_failures,
                    "failure_rate": self.metrics.get_failure_rate()
                }
            )
    
    async def _set_state(self, new_state: CircuitState):
        """Update circuit breaker state."""
        old_state = self.state
        self.state = new_state
        self.metrics.state_change_time = datetime.utcnow()
        
        if new_state == CircuitState.OPEN:
            self.metrics.circuit_opened_count += 1
        
        if new_state == CircuitState.CLOSED:
            self.metrics.reset_consecutive_counters()
        
        logger.info(
            f"Circuit breaker '{self.name}' state changed",
            extra={
                "circuit_breaker": self.name,
                "old_state": old_state.value,
                "new_state": new_state.value,
                "consecutive_failures": self.metrics.consecutive_failures,
                "consecutive_successes": self.metrics.consecutive_successes
            }
        )
    
    def _get_current_timeout(self) -> int:
        """Get current timeout with exponential backoff if enabled."""
        if not self.config.exponential_backoff:
            return self.config.timeout
        
        # Exponential backoff based on number of times circuit was opened
        multiplier = 2 ** min(self.metrics.circuit_opened_count - 1, 5)  # Cap at 2^5 = 32
        timeout = self.config.timeout * multiplier
        
        return min(timeout, self.config.max_timeout)
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get current circuit breaker metrics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "metrics": {
                "total_calls": self.metrics.total_calls,
                "successful_calls": self.metrics.successful_calls,
                "failed_calls": self.metrics.failed_calls,
                "consecutive_failures": self.metrics.consecutive_failures,
                "consecutive_successes": self.metrics.consecutive_successes,
                "success_rate": self.metrics.get_success_rate(),
                "failure_rate": self.metrics.get_failure_rate(),
                "circuit_opened_count": self.metrics.circuit_opened_count,
                "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
                "last_success_time": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None,
                "state_change_time": self.metrics.state_change_time.isoformat() if self.metrics.state_change_time else None
            },
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout": self.config.timeout,
                "call_timeout": self.config.call_timeout,
                "current_timeout": self._get_current_timeout()
            }
        }
    
    async def reset(self):
        """Reset circuit breaker to initial state."""
        async with self._lock:
            self.state = CircuitState.CLOSED
            self.metrics = CircuitBreakerMetrics()
            
            logger.info(
                f"Circuit breaker '{self.name}' reset",
                extra={"circuit_breaker": self.name}
            )


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    
    Provides centralized management and monitoring of circuit breakers
    across the application.
    """
    
    def __init__(self):
        self._circuit_breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()
    
    async def get_or_create(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Get existing circuit breaker or create new one.
        
        Args:
            name: Circuit breaker name
            config: Configuration for new circuit breaker
        
        Returns:
            CircuitBreaker instance
        """
        async with self._lock:
            if name not in self._circuit_breakers:
                self._circuit_breakers[name] = CircuitBreaker(name, config)
            
            return self._circuit_breakers[name]
    
    async def get(self, name: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by name."""
        return self._circuit_breakers.get(name)
    
    async def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """Get metrics for all circuit breakers."""
        metrics = {}
        for name, cb in self._circuit_breakers.items():
            metrics[name] = cb.get_metrics()
        return metrics
    
    async def reset_all(self):
        """Reset all circuit breakers."""
        for cb in self._circuit_breakers.values():
            await cb.reset()
        
        logger.info("All circuit breakers reset")
    
    async def get_unhealthy_services(self) -> Dict[str, Dict[str, Any]]:
        """Get list of services with open or problematic circuit breakers."""
        unhealthy = {}
        
        for name, cb in self._circuit_breakers.items():
            if (cb.state == CircuitState.OPEN or 
                cb.metrics.get_failure_rate() > 0.5):  # More than 50% failure rate
                unhealthy[name] = cb.get_metrics()
        
        return unhealthy


# Global circuit breaker registry
circuit_breaker_registry = CircuitBreakerRegistry()


@asynccontextmanager
async def circuit_breaker(
    service_name: str,
    config: Optional[CircuitBreakerConfig] = None
):
    """
    Context manager for circuit breaker protection.
    
    Args:
        service_name: Name of the service to protect
        config: Circuit breaker configuration
    
    Yields:
        Function to execute protected calls
    
    Example:
        async with circuit_breaker("aws_s3") as cb:
            result = await cb(s3_client.upload_file, file_path, bucket, key)
    """
    cb = await circuit_breaker_registry.get_or_create(service_name, config)
    yield cb.call


def circuit_breaker_decorator(
    service_name: str,
    config: Optional[CircuitBreakerConfig] = None
):
    """
    Decorator for applying circuit breaker protection to functions.
    
    Args:
        service_name: Name of the service to protect
        config: Circuit breaker configuration
    
    Example:
        @circuit_breaker_decorator("external_api")
        async def call_external_api():
            # Function implementation
            pass
    """
    def decorator(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
        async def wrapper(*args, **kwargs) -> T:
            cb = await circuit_breaker_registry.get_or_create(service_name, config)
            return await cb.call(func, *args, **kwargs)
        
        return wrapper
    return decorator
