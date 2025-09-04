"""
Common domain types and patterns.

This module contains shared types, patterns, and utilities used across
the domain layer, including the Result pattern for error handling and
base classes for domain entities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Generic, TypeVar, Optional, Union, Any, List, Dict
from uuid import UUID, uuid4


T = TypeVar('T')
E = TypeVar('E')


@dataclass(frozen=True)
class Result(Generic[T]):
    """
    Result pattern implementation for error handling in business logic.
    
    The Result pattern provides a way to handle errors without exceptions,
    making error handling explicit and improving code clarity and testability.
    
    Examples:
        # Success case
        result = Result.ok("success value")
        if result.is_success:
            print(result.value)
        
        # Failure case
        result = Result.fail("Something went wrong")
        if result.is_failure:
            print(result.error)
        
        # Chaining operations
        result = (Result.ok(5)
                 .map(lambda x: x * 2)
                 .map(lambda x: str(x)))
    """
    
    _value: Optional[T] = None
    _error: Optional[str] = None
    _is_success: bool = True
    
    @classmethod
    def ok(cls, value: T) -> "Result[T]":
        """Create a successful result with a value."""
        return cls(_value=value, _is_success=True)
    
    @classmethod
    def fail(cls, error: str) -> "Result[T]":
        """Create a failed result with an error message."""
        return cls(_error=error, _is_success=False)
    
    @property
    def is_success(self) -> bool:
        """Check if the result is successful."""
        return self._is_success
    
    @property
    def is_failure(self) -> bool:
        """Check if the result is a failure."""
        return not self._is_success
    
    @property
    def value(self) -> T:
        """Get the success value. Raises ValueError if called on failure."""
        if self.is_failure:
            raise ValueError(f"Cannot get value from failed result: {self._error}")
        return self._value
    
    @property
    def error(self) -> str:
        """Get the error message. Raises ValueError if called on success."""
        if self.is_success:
            raise ValueError("Cannot get error from successful result")
        return self._error
    
    def map(self, func: callable) -> "Result":
        """
        Apply a function to the value if the result is successful.
        Returns a new Result with the transformed value or the original error.
        """
        if self.is_failure:
            return Result.fail(self._error)
        
        try:
            new_value = func(self._value)
            return Result.ok(new_value)
        except Exception as e:
            return Result.fail(str(e))
    
    def flat_map(self, func: callable) -> "Result":
        """
        Apply a function that returns a Result to the value if successful.
        Flattens the nested Result structure.
        """
        if self.is_failure:
            return Result.fail(self._error)
        
        try:
            return func(self._value)
        except Exception as e:
            return Result.fail(str(e))
    
    def unwrap_or(self, default: T) -> T:
        """Get the value if successful, otherwise return the default."""
        return self._value if self.is_success else default
    
    def unwrap_or_else(self, func: callable) -> T:
        """Get the value if successful, otherwise call the function with the error."""
        return self._value if self.is_success else func(self._error)


@dataclass(frozen=True)
class DomainEvent(ABC):
    """
    Base class for domain events.
    
    Domain events represent something that happened in the domain
    that other parts of the system might be interested in.
    """
    
    event_id: UUID
    occurred_at: datetime
    aggregate_id: UUID
    version: int
    
    def __post_init__(self):
        """Ensure event_id and occurred_at are set if not provided."""
        if not hasattr(self, 'event_id') or self.event_id is None:
            object.__setattr__(self, 'event_id', uuid4())
        if not hasattr(self, 'occurred_at') or self.occurred_at is None:
            object.__setattr__(self, 'occurred_at', datetime.utcnow())


class Entity(ABC):
    """
    Base class for domain entities.
    
    Entities have identity and lifecycle. They are defined by their
    identity rather than their attributes.
    """
    
    def __init__(self, entity_id: UUID):
        self._id = entity_id
        self._version = 0
        self._domain_events: List[DomainEvent] = []
    
    @property
    def id(self) -> UUID:
        """Get the entity's unique identifier."""
        return self._id
    
    @property
    def version(self) -> int:
        """Get the entity's version for optimistic locking."""
        return self._version
    
    def increment_version(self) -> None:
        """Increment the entity version."""
        self._version += 1
    
    def add_domain_event(self, event: DomainEvent) -> None:
        """Add a domain event to be published."""
        self._domain_events.append(event)
    
    def clear_domain_events(self) -> List[DomainEvent]:
        """Clear and return domain events for publishing."""
        events = self._domain_events.copy()
        self._domain_events.clear()
        return events
    
    def __eq__(self, other: object) -> bool:
        """Entities are equal if they have the same ID and type."""
        if not isinstance(other, Entity):
            return False
        return self._id == other._id and type(self) == type(other)
    
    def __hash__(self) -> int:
        """Hash based on entity ID and type."""
        return hash((self._id, type(self)))


@dataclass(frozen=True)
class ValueObject(ABC):
    """
    Base class for value objects.
    
    Value objects are immutable and defined by their attributes.
    They have no identity and are equal when all their attributes are equal.
    """
    
    def __post_init__(self):
        """Validate the value object after creation."""
        self.validate()
    
    @abstractmethod
    def validate(self) -> None:
        """Validate the value object's invariants."""
        pass


class AggregateRoot(Entity):
    """
    Base class for aggregate roots.
    
    Aggregate roots are entities that serve as the entry point
    to an aggregate and maintain consistency boundaries.
    """
    
    def __init__(self, aggregate_id: UUID):
        super().__init__(aggregate_id)


class BusinessRuleViolation(Exception):
    """
    Exception raised when a business rule is violated.
    
    This should be used for domain-specific business rule violations
    that represent invalid operations rather than system errors.
    """
    
    def __init__(self, rule_name: str, message: str):
        self.rule_name = rule_name
        super().__init__(f"Business rule '{rule_name}' violated: {message}")


class DomainError:
    """
    Represents a domain-specific error.
    
    Used with the Result pattern to represent business logic errors
    without using exceptions.
    """
    
    def __init__(self, code: str, message: str, details: Optional[Dict[str, Any]] = None):
        self.code = code
        self.message = message
        self.details = details or {}
    
    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
    
    def __repr__(self) -> str:
        return f"DomainError(code='{self.code}', message='{self.message}', details={self.details})"


class Specification(ABC):
    """
    Base class for domain specifications.
    
    Specifications encapsulate business rules and can be combined
    using logical operators.
    """
    
    @abstractmethod
    def is_satisfied_by(self, candidate: Any) -> bool:
        """Check if the specification is satisfied by the candidate."""
        pass
    
    def and_(self, other: "Specification") -> "AndSpecification":
        """Combine with another specification using AND logic."""
        return AndSpecification(self, other)
    
    def or_(self, other: "Specification") -> "OrSpecification":
        """Combine with another specification using OR logic."""
        return OrSpecification(self, other)
    
    def not_(self) -> "NotSpecification":
        """Negate this specification."""
        return NotSpecification(self)


class AndSpecification(Specification):
    """Specification that combines two specifications with AND logic."""
    
    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right
    
    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) and self.right.is_satisfied_by(candidate)


class OrSpecification(Specification):
    """Specification that combines two specifications with OR logic."""
    
    def __init__(self, left: Specification, right: Specification):
        self.left = left
        self.right = right
    
    def is_satisfied_by(self, candidate: Any) -> bool:
        return self.left.is_satisfied_by(candidate) or self.right.is_satisfied_by(candidate)


class NotSpecification(Specification):
    """Specification that negates another specification."""
    
    def __init__(self, spec: Specification):
        self.spec = spec
    
    def is_satisfied_by(self, candidate: Any) -> bool:
        return not self.spec.is_satisfied_by(candidate)
