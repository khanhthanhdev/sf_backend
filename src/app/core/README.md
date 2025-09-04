Core Services

Purpose: Cross-cutting concerns and infrastructure helpers.

Highlights:
- logger.py: Structured logging via structlog (JSON in prod, console in dev). Correlation ID support.
- cache.py, cache_monitoring.py: Response caching and observability.
- redis.py: Redis clients and health checks.
- container.py, service_factory.py: Dependency injection and service wiring.

Usage:
- Import `get_logger()` from `logger.py` for consistent logs.
- Use DI dependencies from `...api.dependencies` or `...api.enhanced_dependencies`.

Design Notes:
- Separation of concerns: logging, caching, and DI are modularized for reuse.

