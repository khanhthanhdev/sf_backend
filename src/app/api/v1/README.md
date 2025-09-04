API v1

Purpose: FastAPI endpoints for system monitoring and job management.

Modules:
- system.py: Health, metrics, and queue status endpoints with caching and dependency injection.
- jobs.py: List, cancel, delete, inspect jobs; fetch job logs. Integrates AWS-backed services.

Auth: Most endpoints require authenticated users (Clerk integration in core/auth).

Examples:
- Health Check:
```bash
curl -X GET http://localhost:8000/api/v1/system/health
```

- List Jobs:
```bash
curl -H "Authorization: Bearer <token>" \
  'http://localhost:8000/api/v1/jobs?page=1&items_per_page=10'
```

Notes:
- Endpoints use ETag for conditional GETs and caching via `cache_response` decorator.
- Error handling standardized with HTTPException and service-specific helpers.

