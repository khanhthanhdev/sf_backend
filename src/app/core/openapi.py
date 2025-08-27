"""
OpenAPI documentation configuration and customization.

This module provides comprehensive OpenAPI schema customization,
including enhanced documentation, examples, and client generation support.
"""

from typing import Dict, Any, List, Optional
from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

from .config import get_settings

settings = get_settings()


class OpenAPIConfig:
    """OpenAPI configuration and customization manager."""
    
    @staticmethod
    def get_api_description() -> str:
        """Get comprehensive API description for OpenAPI documentation."""
        return """
## FastAPI Video Generation Backend

This API provides comprehensive video generation capabilities using multi-agent AI systems.
The backend supports video creation from textual descriptions, job management, file handling,
and real-time progress monitoring.

### Key Features

- **Video Generation**: Create educational videos from topic and context descriptions
- **Job Management**: Track video generation progress with real-time updates
- **File Handling**: Secure upload, download, and streaming of video content
- **Authentication**: Clerk-based user authentication and authorization
- **Batch Processing**: Support for multiple video generation requests
- **Monitoring**: Comprehensive system health and performance monitoring

### Authentication

This API uses Clerk authentication. Include your Clerk session token in the Authorization header:

```
Authorization: Bearer <your-clerk-session-token>
```

### Rate Limiting

API requests are rate-limited per user. Current limits:
- 100 requests per minute for authenticated users
- 50 requests per minute for video generation endpoints

### Error Handling

All errors follow a consistent format:

```json
{
  "error": {
    "message": "Human-readable error message",
    "error_code": "MACHINE_READABLE_CODE",
    "details": {},
    "timestamp": "2024-01-15T10:30:00Z",
    "path": "/api/v1/videos/generate"
  }
}
```

### WebSocket Support

Real-time job status updates are available via WebSocket connections:
- `ws://localhost:8000/ws/jobs/{job_id}` - Job-specific updates
- `ws://localhost:8000/ws/system/health` - System health monitoring

### Pagination

List endpoints support pagination with the following parameters:
- `page`: Page number (default: 1)
- `items_per_page`: Items per page (default: 10, max: 100)

### Filtering and Sorting

Many endpoints support filtering and sorting:
- `status`: Filter by job status
- `created_after`: Filter by creation date
- `sort_by`: Sort field (created_at, updated_at, etc.)
- `sort_order`: Sort order (asc, desc)

### Client SDKs

This API supports automatic client SDK generation using OpenAPI specifications.
Supported languages include:
- TypeScript/JavaScript
- Python
- Java
- C#
- Go
- PHP
- Ruby

### API Versioning

This API uses URL-based versioning:
- Current version: v1
- Base URL: `/api/v1`
- Deprecated versions will be supported for 6 months after deprecation notice

### Support

For API support and questions:
- Documentation: https://docs.example.com
- Support Email: support@example.com
- GitHub Issues: https://github.com/example/video-api/issues
"""

    @staticmethod
    def get_openapi_tags() -> List[Dict[str, Any]]:
        """Get OpenAPI tags for endpoint organization."""
        return [
            {
                "name": "videos",
                "description": "Video generation and management operations. Create videos from text descriptions, monitor progress, and download results.",
                "externalDocs": {
                    "description": "Video Generation Guide",
                    "url": "https://docs.example.com/video-generation",
                },
            },
            {
                "name": "jobs",
                "description": "Job management operations. Monitor job status, cancel jobs, retrieve logs, and manage job lifecycle.",
                "externalDocs": {
                    "description": "Job Management Guide",
                    "url": "https://docs.example.com/job-management",
                },
            },
            {
                "name": "files",
                "description": "File upload, download, and management operations. Handle video files, thumbnails, and related assets.",
                "externalDocs": {
                    "description": "File Handling Guide",
                    "url": "https://docs.example.com/file-handling",
                },
            },
            {
                "name": "system",
                "description": "System monitoring, health checks, and administrative operations. Monitor system performance and health.",
                "externalDocs": {
                    "description": "System Monitoring Guide",
                    "url": "https://docs.example.com/system-monitoring",
                },
            },
            {
                "name": "auth",
                "description": "Authentication and authorization operations. Manage user sessions and authentication status.",
                "externalDocs": {
                    "description": "Authentication Guide",
                    "url": "https://docs.example.com/authentication",
                },
            },
            {
                "name": "testing",
                "description": "Testing endpoints for API functionality verification.",
            },
        ]

    @staticmethod
    def get_api_servers() -> List[Dict[str, Any]]:
        """Get API server configurations for different environments."""
        servers = []
        
        if settings.environment == "development":
            servers.extend([
                {
                    "url": "http://localhost:8000",
                    "description": "Development server",
                    "variables": {
                        "port": {
                            "default": "8000",
                            "description": "Development server port"
                        }
                    }
                },
                {
                    "url": "http://127.0.0.1:8000",
                    "description": "Local development server"
                }
            ])
        elif settings.environment == "staging":
            servers.append({
                "url": "https://api-staging.example.com",
                "description": "Staging server"
            })
        elif settings.environment == "production":
            servers.append({
                "url": "https://api.example.com",
                "description": "Production server"
            })
        
        return servers

    @staticmethod
    def get_security_schemes() -> Dict[str, Any]:
        """Get security scheme definitions."""
        return {
            "ClerkAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "Clerk session token authentication. Obtain token from Clerk authentication flow.",
                "x-clerk-docs": "https://clerk.com/docs/authentication/overview"
            },
            "ApiKeyAuth": {
                "type": "apiKey",
                "in": "header",
                "name": "X-API-Key",
                "description": "API key for service-to-service authentication (internal use only).",
            }
        }

    @staticmethod
    def get_custom_extensions() -> Dict[str, Any]:
        """Get custom OpenAPI extensions."""
        return {
            "x-logo": {
                "url": "https://example.com/logo.png",
                "altText": "Video Generation API",
                "href": "https://example.com"
            },
            "x-api-version": {
                "current": "v1",
                "supported": ["v1"],
                "deprecated": [],
                "sunset": {},
                "changelog": "https://docs.example.com/changelog"
            },
            "x-rate-limit": {
                "default": "100 requests per minute",
                "video-generation": "50 requests per minute",
                "file-upload": "20 requests per minute",
                "documentation": "https://docs.example.com/rate-limits"
            },
            "x-response-time": {
                "typical": "< 200ms",
                "video-generation": "5-10 minutes",
                "file-upload": "< 30 seconds"
            }
        }

    @classmethod
    def customize_openapi_schema(cls, app: FastAPI) -> None:
        """Customize OpenAPI schema with enhanced documentation."""
        def custom_openapi():
            if app.openapi_schema:
                return app.openapi_schema
            
            openapi_schema = get_openapi(
                title=app.title,
                version=app.version,
                description=app.description,
                routes=app.routes,
                tags=app.openapi_tags,
                servers=app.servers,
            )
            
            # Add security schemes
            if "components" not in openapi_schema:
                openapi_schema["components"] = {}
            
            openapi_schema["components"]["securitySchemes"] = cls.get_security_schemes()
            
            # Add global security requirement
            openapi_schema["security"] = [
                {"ClerkAuth": []},
                {"ApiKeyAuth": []}
            ]
            
            # Add custom extensions
            openapi_schema.update(cls.get_custom_extensions())
            
            # Enhance operation IDs for better client generation
            cls._enhance_operation_ids(openapi_schema)
            
            # Add comprehensive examples
            cls._add_comprehensive_examples(openapi_schema)
            
            # Add response headers documentation
            cls._add_response_headers(openapi_schema)
            
            # Add webhook documentation
            cls._add_webhook_documentation(openapi_schema)
            
            app.openapi_schema = openapi_schema
            return app.openapi_schema
        
        app.openapi = custom_openapi

    @staticmethod
    def _enhance_operation_ids(openapi_schema: Dict[str, Any]) -> None:
        """Enhance operation IDs for better client generation."""
        for path, path_data in openapi_schema.get("paths", {}).items():
            for method, operation in path_data.items():
                if isinstance(operation, dict) and "operationId" in operation:
                    operation_id = operation["operationId"]
                    
                    # Ensure operation IDs follow consistent naming conventions
                    if not any(operation_id.startswith(prefix) for prefix in ["get", "post", "put", "delete", "patch"]):
                        # Add HTTP method prefix based on operation type
                        summary = operation.get("summary", "").lower()
                        if method.upper() == "POST":
                            if "create" in summary or "generate" in summary:
                                operation["operationId"] = f"create_{operation_id}"
                            elif "upload" in summary:
                                operation["operationId"] = f"upload_{operation_id}"
                            else:
                                operation["operationId"] = f"post_{operation_id}"
                        elif method.upper() == "GET":
                            if "list" in summary:
                                operation["operationId"] = f"list_{operation_id}"
                            else:
                                operation["operationId"] = f"get_{operation_id}"
                        elif method.upper() == "PUT":
                            operation["operationId"] = f"update_{operation_id}"
                        elif method.upper() == "DELETE":
                            operation["operationId"] = f"delete_{operation_id}"
                        elif method.upper() == "PATCH":
                            operation["operationId"] = f"patch_{operation_id}"
                    
                    # Add client-friendly descriptions
                    if "description" not in operation and "summary" in operation:
                        operation["description"] = f"{operation['summary']}. {OpenAPIConfig._get_operation_description(path, method)}"

    @staticmethod
    def _get_operation_description(path: str, method: str) -> str:
        """Get enhanced description for operations."""
        descriptions = {
            "/api/v1/videos/generate": "Submits a video generation request and returns a job ID for tracking progress.",
            "/api/v1/videos/jobs/{job_id}/status": "Retrieves current status and progress information for a video generation job.",
            "/api/v1/videos/jobs/{job_id}/download": "Downloads the completed video file with support for range requests.",
            "/api/v1/jobs": "Lists jobs with pagination, filtering, and sorting options.",
            "/api/v1/jobs/{job_id}/cancel": "Cancels a job if it's in a cancellable state (queued or processing).",
            "/api/v1/system/health": "Provides comprehensive system health status including all components.",
        }
        return descriptions.get(path, "")

    @staticmethod
    def _add_comprehensive_examples(openapi_schema: Dict[str, Any]) -> None:
        """Add comprehensive examples to schema definitions."""
        if "components" not in openapi_schema:
            return
        
        schemas = openapi_schema["components"].get("schemas", {})
        
        # Add examples for common error responses
        if "HTTPValidationError" in schemas:
            schemas["HTTPValidationError"]["examples"] = {
                "validation_error": {
                    "summary": "Validation Error Example",
                    "description": "Example of a validation error response",
                    "value": {
                        "detail": [
                            {
                                "loc": ["body", "configuration", "topic"],
                                "msg": "field required",
                                "type": "value_error.missing"
                            },
                            {
                                "loc": ["body", "configuration", "context"],
                                "msg": "ensure this value has at least 1 characters",
                                "type": "value_error.any_str.min_length",
                                "ctx": {"limit_value": 1}
                            }
                        ]
                    }
                }
            }
        
        # Add examples for job responses
        job_examples = {
            "queued_job": {
                "summary": "Queued Job",
                "description": "A newly created job in the queue",
                "value": {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "queued",
                    "progress": {
                        "percentage": 0.0,
                        "current_stage": None,
                        "stages_completed": [],
                        "estimated_completion": "2024-01-15T10:35:00Z"
                    },
                    "created_at": "2024-01-15T10:30:00Z"
                }
            },
            "processing_job": {
                "summary": "Processing Job",
                "description": "A job currently being processed",
                "value": {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "processing",
                    "progress": {
                        "percentage": 45.0,
                        "current_stage": "video_generation",
                        "stages_completed": ["validation", "content_preparation"],
                        "estimated_completion": "2024-01-15T10:33:00Z"
                    },
                    "created_at": "2024-01-15T10:30:00Z"
                }
            },
            "completed_job": {
                "summary": "Completed Job",
                "description": "A successfully completed job",
                "value": {
                    "job_id": "550e8400-e29b-41d4-a716-446655440000",
                    "status": "completed",
                    "progress": {
                        "percentage": 100.0,
                        "current_stage": "completed",
                        "stages_completed": ["validation", "content_preparation", "video_generation", "post_processing"],
                        "estimated_completion": None
                    },
                    "created_at": "2024-01-15T10:30:00Z"
                }
            }
        }
        
        # Apply examples to relevant schemas
        for schema_name, schema_data in schemas.items():
            if "JobResponse" in schema_name:
                schema_data["examples"] = job_examples

    @staticmethod
    def _add_response_headers(openapi_schema: Dict[str, Any]) -> None:
        """Add response headers documentation."""
        common_headers = {
            "X-Request-ID": {
                "description": "Unique request identifier for tracking and debugging",
                "schema": {"type": "string", "format": "uuid"}
            },
            "X-Rate-Limit-Remaining": {
                "description": "Number of requests remaining in the current rate limit window",
                "schema": {"type": "integer"}
            },
            "X-Rate-Limit-Reset": {
                "description": "Unix timestamp when the rate limit window resets",
                "schema": {"type": "integer"}
            }
        }
        
        # Add headers to all responses
        for path_data in openapi_schema.get("paths", {}).values():
            for operation in path_data.values():
                if isinstance(operation, dict) and "responses" in operation:
                    for response_code, response_data in operation["responses"].items():
                        if isinstance(response_data, dict):
                            if "headers" not in response_data:
                                response_data["headers"] = {}
                            response_data["headers"].update(common_headers)

    @staticmethod
    def _add_webhook_documentation(openapi_schema: Dict[str, Any]) -> None:
        """Add webhook documentation."""
        webhook_info = {
            "x-webhooks": {
                "job_status_changed": {
                    "post": {
                        "summary": "Job Status Changed",
                        "description": "Triggered when a job status changes (queued -> processing -> completed/failed)",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "event": {"type": "string", "example": "job.status.changed"},
                                            "job_id": {"type": "string", "format": "uuid"},
                                            "user_id": {"type": "string"},
                                            "old_status": {"type": "string", "enum": ["queued", "processing", "completed", "failed", "cancelled"]},
                                            "new_status": {"type": "string", "enum": ["queued", "processing", "completed", "failed", "cancelled"]},
                                            "timestamp": {"type": "string", "format": "date-time"}
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Webhook received successfully"
                            }
                        }
                    }
                },
                "job_completed": {
                    "post": {
                        "summary": "Job Completed",
                        "description": "Triggered when a video generation job is completed successfully",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "event": {"type": "string", "example": "job.completed"},
                                            "job_id": {"type": "string", "format": "uuid"},
                                            "user_id": {"type": "string"},
                                            "video_id": {"type": "string", "format": "uuid"},
                                            "download_url": {"type": "string", "format": "uri"},
                                            "duration_seconds": {"type": "number"},
                                            "file_size": {"type": "integer"},
                                            "timestamp": {"type": "string", "format": "date-time"}
                                        }
                                    }
                                }
                            }
                        },
                        "responses": {
                            "200": {
                                "description": "Webhook received successfully"
                            }
                        }
                    }
                }
            }
        }
        
        openapi_schema.update(webhook_info)


def setup_openapi_documentation(app: FastAPI) -> None:
    """Set up comprehensive OpenAPI documentation for the FastAPI application."""
    OpenAPIConfig.customize_openapi_schema(app)