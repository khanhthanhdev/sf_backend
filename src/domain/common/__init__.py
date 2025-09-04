"""
Common domain types and utilities.
"""

from .types import (
    Result,
    DomainEvent,
    Entity,
    ValueObject,
    AggregateRoot,
    BusinessRuleViolation,
    DomainError,
    Specification,
    AndSpecification,
    OrSpecification,
    NotSpecification,
)

__all__ = [
    "Result",
    "DomainEvent", 
    "Entity",
    "ValueObject",
    "AggregateRoot",
    "BusinessRuleViolation",
    "DomainError",
    "Specification",
    "AndSpecification",
    "OrSpecification",
    "NotSpecification",
]
