"""
API documentation examples for OpenAPI schema generation.

This module contains comprehensive examples for all API schemas to enhance
the automatically generated API documentation.
"""

from datetime import datetime
from typing import Dict, Any

# Request Examples

VIDEO_GENERATION_REQUEST_EXAMPLES = {
    "basic_request": {
        "summary": "Basic video generation request",
        "description": "A simple video generation request with minimal parameters",
        "value": {
            "topic": "Introduction to Python Programming",
            "context": "Create an educational video explaining Python basics including variables, data types, and simple operations. Target audience is beginners with no programming experience.",
            "quality": "medium",
            "use_rag": False
        }
    },
    "advanced_request": {
        "summary": "Advanced video generation request",
        "description": "A comprehensive request with all optional parameters",
        "value": {
            "topic": "Machine Learning Fundamentals",
            "context": "Comprehensive overview of machine learning concepts including supervised learning, unsupervised learning, and neural networks. Include practical examples and real-world applications.",
            "model": "gemini/gemini-2.5-flash-preview-04-17",
            "quality": "high",
            "use_rag": True,
            "priority": "high",
            "enable_subtitles": True,
            "enable_thumbnails": True,
            "output_format": "mp4",
            "title": "Machine Learning 101: A Beginner's Guide",
            "description": "Educational video covering the fundamentals of machine learning",
            "tags": ["machine-learning", "ai", "education", "programming"],
            "custom_config": {
                "animation_style": "modern",
                "voice_speed": "normal",
                "include_code_examples": True
            },
            "style_preferences": {
                "color_scheme": "blue",
                "font_style": "professional"
            }
        }
    },
    "mathematics_request": {
        "summary": "Mathematics education video",
        "description": "Request for creating a mathematics educational video",
        "value": {
            "topic": "Pythagorean Theorem",
            "context": "Explain the Pythagorean theorem with visual proof, formula derivation, and practical applications in construction and navigation. Include interactive examples.",
            "quality": "high",
            "use_rag": True,
            "enable_subtitles": True,
            "title": "Understanding the Pythagorean Theorem",
            "tags": ["mathematics", "geometry", "theorem", "education"]
        }
    }
}

BATCH_REQUEST_EXAMPLES = {
    "mathematics_series": {
        "summary": "Mathematics video series",
        "description": "Create a series of mathematics educational videos",
        "value": {
            "jobs": [
                {
                    "topic": "Pythagorean Theorem",
                    "context": "Explain the theorem with visual proofs and applications",
                    "quality": "medium",
                    "tags": ["mathematics", "geometry"]
                },
                {
                    "topic": "Quadratic Formula",
                    "context": "Step-by-step solution of quadratic equations",
                    "quality": "medium", 
                    "tags": ["mathematics", "algebra"]
                },
                {
                    "topic": "Trigonometric Functions",
                    "context": "Introduction to sine, cosine, and tangent functions",
                    "quality": "medium",
                    "tags": ["mathematics", "trigonometry"]
                }
            ],
            "batch_priority": "normal",
            "batch_name": "High School Mathematics Series"
        }
    }
}

JOB_FILTER_EXAMPLES = {
    "status_filter": {
        "summary": "Filter by job status",
        "description": "Get jobs with specific status values",
        "value": {
            "status": ["processing", "completed"],
            "created_after": "2024-01-01T00:00:00Z"
        }
    },
    "search_filter": {
        "summary": "Search and filter jobs",
        "description": "Search jobs by topic and filter by date range",
        "value": {
            "search": "mathematics",
            "created_after": "2024-01-01T00:00:00Z",
            "created_before": "2024-12-31T23:59:59Z",
            "priority": ["normal", "high"]
        }
    }
}

# Response Examples

JOB_RESPONSE_EXAMPLES = {
    "queued_job": {
        "summary": "Newly created job",
        "description": "Response for a newly created job in queue",
        "value": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "queued",
            "priority": "normal",
            "progress": {
                "percentage": 0.0,
                "current_stage": None,
                "stages_completed": [],
                "estimated_completion": "2024-01-15T10:35:00Z",
                "processing_time_seconds": None
            },
            "created_at": "2024-01-15T10:30:00Z",
            "estimated_completion": "2024-01-15T10:35:00Z",
            "batch_id": None
        }
    },
    "processing_job": {
        "summary": "Job in progress",
        "description": "Response for a job currently being processed",
        "value": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "status": "processing",
            "priority": "normal",
            "progress": {
                "percentage": 65.0,
                "current_stage": "video_generation",
                "stages_completed": ["content_planning", "script_generation", "asset_creation"],
                "estimated_completion": "2024-01-15T10:33:00Z",
                "processing_time_seconds": 180.5
            },
            "created_at": "2024-01-15T10:30:00Z",
            "estimated_completion": "2024-01-15T10:33:00Z",
            "batch_id": None
        }
    }
}

JOB_STATUS_RESPONSE_EXAMPLES = {
    "completed_job": {
        "summary": "Completed job with video",
        "description": "Detailed status of a successfully completed job",
        "value": {
            "job_id": "550e8400-e29b-41d4-a716-446655440000",
            "user_id": "user_2NiWoZK2iKDvEFEHaakTrHVfcrq",
            "status": "completed",
            "priority": "normal",
            "progress": {
                "percentage": 100.0,
                "current_stage": "completed",
                "stages_completed": ["content_planning", "script_generation", "asset_creation", "video_generation", "post_processing"],
                "estimated_completion": None,
                "processing_time_seconds": 245.8
            },
            "topic": "Pythagorean Theorem",
            "quality": "medium",
            "error": None,
            "metrics": {
                "queue_time_seconds": 12.3,
                "processing_time_seconds": 245.8,
                "cpu_usage_percent": 78.5,
                "memory_usage_mb": 1024.0,
                "disk_usage_mb": 150.0,
                "network_usage_mb": 25.6
            },
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:34:05Z",
            "started_at": "2024-01-15T10:30:12Z",
            "completed_at": "2024-01-15T10:34:05Z",
            "batch_id": None,
            "video_id": "video_550e8400-e29b-41d4-a716-446655440000",
            "download_url": "https://api.example.com/api/v1/videos/jobs/550e8400-e29b-41d4-a716-446655440000/download"
        }
    },
    "failed_job": {
        "summary": "Failed job with error details",
        "description": "Status of a job that failed during processing",
        "value": {
            "job_id": "550e8400-e29b-41d4-a716-446655440001",
            "user_id": "user_2NiWoZK2iKDvEFEHaakTrHVfcrq",
            "status": "failed",
            "priority": "normal",
            "progress": {
                "percentage": 35.0,
                "current_stage": "script_generation",
                "stages_completed": ["content_planning"],
                "estimated_completion": None,
                "processing_time_seconds": 89.2
            },
            "topic": "Advanced Quantum Physics",
            "quality": "high",
            "error": {
                "error_code": "CONTENT_GENERATION_FAILED",
                "error_message": "Failed to generate content due to insufficient context",
                "error_details": {
                    "stage": "script_generation",
                    "reason": "Topic too complex for current model capabilities"
                },
                "retry_count": 2,
                "max_retries": 3
            },
            "metrics": {
                "queue_time_seconds": 8.1,
                "processing_time_seconds": 89.2,
                "cpu_usage_percent": 45.2,
                "memory_usage_mb": 512.0
            },
            "created_at": "2024-01-15T10:30:00Z",
            "updated_at": "2024-01-15T10:31:29Z",
            "started_at": "2024-01-15T10:30:08Z",
            "completed_at": "2024-01-15T10:31:29Z",
            "batch_id": None,
            "video_id": None,
            "download_url": None
        }
    }
}

VIDEO_DOWNLOAD_RESPONSE_EXAMPLES = {
    "ready_video": {
        "summary": "Video ready for download",
        "description": "Complete video information with download links",
        "value": {
            "video_id": "video_550e8400-e29b-41d4-a716-446655440000",
            "job_id": "job_550e8400-e29b-41d4-a716-446655440000",
            "filename": "pythagorean_theorem_explained.mp4",
            "file_size": 25165824,
            "file_size_mb": 24.0,
            "duration_seconds": 180.5,
            "duration_formatted": "03:00",
            "resolution": "1080p",
            "format": "mp4",
            "download_url": "https://api.example.com/api/v1/videos/download/video_550e8400-e29b-41d4-a716-446655440000",
            "streaming_url": "https://stream.example.com/video_550e8400-e29b-41d4-a716-446655440000",
            "expires_at": "2024-01-16T10:30:00Z",
            "thumbnail_urls": [
                "https://api.example.com/thumbnails/video_550e8400_thumb_001.jpg",
                "https://api.example.com/thumbnails/video_550e8400_thumb_002.jpg",
                "https://api.example.com/thumbnails/video_550e8400_thumb_003.jpg"
            ],
            "subtitle_urls": [
                {
                    "language": "en",
                    "language_name": "English",
                    "url": "https://api.example.com/subtitles/video_550e8400_en.srt"
                },
                {
                    "language": "es",
                    "language_name": "Spanish",
                    "url": "https://api.example.com/subtitles/video_550e8400_es.srt"
                }
            ],
            "created_at": "2024-01-15T10:34:05Z",
            "download_count": 0
        }
    }
}

SYSTEM_HEALTH_RESPONSE_EXAMPLES = {
    "healthy_system": {
        "summary": "Healthy system status",
        "description": "All system components are functioning normally",
        "value": {
            "overall_status": "healthy",
            "timestamp": "2024-01-15T10:30:00Z",
            "version": "1.0.0",
            "uptime_seconds": 86400.0,
            "services": [
                {
                    "name": "redis",
                    "status": "healthy",
                    "response_time_ms": 2.1,
                    "last_check": "2024-01-15T10:30:00Z",
                    "details": {
                        "connected_clients": 15,
                        "memory_usage_mb": 128.5
                    }
                },
                {
                    "name": "queue",
                    "status": "healthy",
                    "response_time_ms": 1.8,
                    "last_check": "2024-01-15T10:30:00Z",
                    "details": {
                        "queue_length": 5,
                        "processing_rate": 2.5
                    }
                },
                {
                    "name": "storage",
                    "status": "healthy",
                    "response_time_ms": 15.2,
                    "last_check": "2024-01-15T10:30:00Z",
                    "details": {
                        "available_space_gb": 500.0,
                        "used_space_gb": 125.3
                    }
                }
            ],
            "queue_length": 5,
            "active_jobs": 3,
            "completed_jobs_24h": 247,
            "failed_jobs_24h": 3,
            "cpu_usage_percent": 45.2,
            "memory_usage_percent": 67.8,
            "disk_usage_percent": 23.1
        }
    },
    "degraded_system": {
        "summary": "System with performance issues",
        "description": "System is functional but experiencing performance degradation",
        "value": {
            "overall_status": "degraded",
            "timestamp": "2024-01-15T10:30:00Z",
            "version": "1.0.0",
            "uptime_seconds": 86400.0,
            "services": [
                {
                    "name": "redis",
                    "status": "healthy",
                    "response_time_ms": 2.1,
                    "last_check": "2024-01-15T10:30:00Z"
                },
                {
                    "name": "queue",
                    "status": "degraded",
                    "response_time_ms": 45.8,
                    "last_check": "2024-01-15T10:30:00Z",
                    "details": {
                        "queue_length": 25,
                        "processing_rate": 0.8,
                        "warning": "High queue length detected"
                    }
                }
            ],
            "queue_length": 25,
            "active_jobs": 15,
            "completed_jobs_24h": 180,
            "failed_jobs_24h": 12,
            "cpu_usage_percent": 85.7,
            "memory_usage_percent": 92.3,
            "disk_usage_percent": 78.9
        }
    }
}

ERROR_RESPONSE_EXAMPLES = {
    "validation_error": {
        "summary": "Validation error response",
        "description": "Response when request validation fails",
        "value": {
            "status": "error",
            "message": "Validation failed",
            "error": {
                "message": "The request contains invalid data",
                "code": "VALIDATION_ERROR",
                "field_errors": [
                    {
                        "field": "topic",
                        "message": "Topic cannot be empty",
                        "code": "REQUIRED_FIELD",
                        "value": ""
                    },
                    {
                        "field": "context",
                        "message": "Context must be at least 10 characters long",
                        "code": "MIN_LENGTH",
                        "value": "short"
                    }
                ],
                "timestamp": "2024-01-15T10:30:00Z"
            },
            "timestamp": "2024-01-15T10:30:00Z",
            "request_id": "req_123456789"
        }
    },
    "not_found_error": {
        "summary": "Resource not found",
        "description": "Response when requested resource doesn't exist",
        "value": {
            "status": "error",
            "message": "Job not found",
            "error": {
                "message": "The requested job was not found",
                "code": "NOT_FOUND",
                "details": {
                    "resource_type": "Job",
                    "resource_id": "550e8400-e29b-41d4-a716-446655440000"
                },
                "timestamp": "2024-01-15T10:30:00Z"
            },
            "timestamp": "2024-01-15T10:30:00Z",
            "request_id": "req_123456789"
        }
    },
    "rate_limit_error": {
        "summary": "Rate limit exceeded",
        "description": "Response when API rate limit is exceeded",
        "value": {
            "status": "error",
            "message": "Rate limit exceeded",
            "error": {
                "message": "Too many requests. Please try again later.",
                "code": "RATE_LIMIT_EXCEEDED",
                "details": {
                    "retry_after_seconds": 60,
                    "rate_limit": 100
                },
                "timestamp": "2024-01-15T10:30:00Z"
            },
            "timestamp": "2024-01-15T10:30:00Z",
            "request_id": "req_123456789"
        }
    }
}

# Pagination Examples

PAGINATION_EXAMPLES = {
    "first_page": {
        "summary": "First page of results",
        "description": "Request for the first page with default page size",
        "value": {
            "page": 1,
            "items_per_page": 10
        }
    },
    "large_page": {
        "summary": "Large page size",
        "description": "Request for more items per page",
        "value": {
            "page": 1,
            "items_per_page": 50
        }
    }
}

SORT_EXAMPLES = {
    "newest_first": {
        "summary": "Sort by creation date (newest first)",
        "description": "Sort results by creation date in descending order",
        "value": {
            "sort_by": "created_at",
            "sort_order": "desc"
        }
    },
    "priority_sort": {
        "summary": "Sort by priority",
        "description": "Sort results by priority level",
        "value": {
            "sort_by": "priority",
            "sort_order": "desc"
        }
    }
}

# Export all examples for use in API documentation
ALL_EXAMPLES = {
    "requests": {
        "video_generation": VIDEO_GENERATION_REQUEST_EXAMPLES,
        "batch_generation": BATCH_REQUEST_EXAMPLES,
        "job_filter": JOB_FILTER_EXAMPLES,
        "pagination": PAGINATION_EXAMPLES,
        "sort": SORT_EXAMPLES,
    },
    "responses": {
        "job": JOB_RESPONSE_EXAMPLES,
        "job_status": JOB_STATUS_RESPONSE_EXAMPLES,
        "video_download": VIDEO_DOWNLOAD_RESPONSE_EXAMPLES,
        "system_health": SYSTEM_HEALTH_RESPONSE_EXAMPLES,
        "errors": ERROR_RESPONSE_EXAMPLES,
    }
}