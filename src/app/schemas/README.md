# API Schemas Documentation

This directory contains Pydantic schemas for the FastAPI video generation backend. The schemas are organized into three main categories:

## Structure

- **`requests.py`** - Request validation schemas for API endpoints
- **`responses.py`** - Response formatting schemas for API endpoints  
- **`common.py`** - Shared schemas for pagination, filtering, and error handling
- **`examples.py`** - Comprehensive examples for API documentation
- **`__init__.py`** - Module exports and imports

## Request Schemas

### VideoGenerationRequest

Primary schema for video generation requests with comprehensive validation:

```python
from app.schemas.requests import VideoGenerationRequest

request = VideoGenerationRequest(
    topic="Machine Learning Basics",
    context="Comprehensive introduction to ML concepts...",
    quality="high",
    use_rag=True,
    tags=["ml", "education"]
)
```

**Key Features:**
- Field validation with custom validators
- Comprehensive examples for API documentation
- Support for advanced configuration options
- Automatic data cleaning and normalization

### BatchVideoGenerationRequest

Schema for creating multiple video generation jobs:

```python
from app.schemas.requests import BatchVideoGenerationRequest

batch_request = BatchVideoGenerationRequest(
    jobs=[request1, request2, request3],
    batch_priority="high",
    batch_name="Educational Series"
)
```

### JobFilterRequest

Schema for filtering and searching jobs:

```python
from app.schemas.requests import JobFilterRequest

filters = JobFilterRequest(
    status=["processing", "completed"],
    search="mathematics",
    created_after="2024-01-01T00:00:00Z"
)
```

## Response Schemas

### JobResponse

Standard response for job operations:

```python
from app.schemas.responses import JobResponse

response = JobResponse(
    job_id="550e8400-e29b-41d4-a716-446655440000",
    status="queued",
    priority="normal",
    progress=JobProgress(percentage=0.0),
    created_at=datetime.now()
)
```

### JobStatusResponse

Detailed job status information:

```python
from app.schemas.responses import JobStatusResponse

status_response = JobStatusResponse(
    job_id="550e8400-e29b-41d4-a716-446655440000",
    user_id="user_123",
    status="processing",
    progress=JobProgress(
        percentage=45.0,
        current_stage="video_generation"
    ),
    metrics=JobMetrics(
        processing_time_seconds=120.5,
        cpu_usage_percent=75.0
    )
)
```

### VideoDownloadResponse

Complete video information with download links:

```python
from app.schemas.responses import VideoDownloadResponse

video_response = VideoDownloadResponse(
    video_id="video_123",
    job_id="job_123",
    filename="educational_video.mp4",
    file_size=25165824,
    file_size_mb=24.0,
    download_url="https://api.example.com/download/video_123",
    thumbnail_urls=["thumb1.jpg", "thumb2.jpg"]
)
```

## Common Schemas

### PaginationRequest

Standardized pagination parameters:

```python
from app.schemas.common import PaginationRequest

pagination = PaginationRequest(
    page=1,
    items_per_page=20
)

# Access calculated values
offset = pagination.offset  # 0
limit = pagination.limit    # 20
```

### SortRequest

Sorting parameters with validation:

```python
from app.schemas.common import SortRequest

sort = SortRequest(
    sort_by="created_at",
    sort_order="desc"
)
```

### ErrorResponse

Consistent error formatting:

```python
from app.schemas.common import ErrorResponse
from app.models.common import ErrorDetail, ErrorCode

error = ErrorResponse(
    message="Job not found",
    error=ErrorDetail(
        message="The requested job was not found",
        code=ErrorCode.NOT_FOUND,
        details={"job_id": "123"}
    )
)
```

## Usage in FastAPI Endpoints

### Basic Endpoint with Request/Response Schemas

```python
from fastapi import APIRouter, HTTPException
from app.schemas.requests import VideoGenerationRequest
from app.schemas.responses import JobResponse
from app.schemas.common import ErrorResponse

router = APIRouter()

@router.post(
    "/videos/generate",
    response_model=JobResponse,
    responses={
        422: {"model": ValidationErrorResponse},
        401: {"model": UnauthorizedResponse},
        500: {"model": InternalServerErrorResponse}
    }
)
async def generate_video(request: VideoGenerationRequest):
    """
    Generate a new educational video.
    
    Creates a new video generation job with the provided configuration.
    Returns job information including ID and initial status.
    """
    # Business logic here
    pass
```

### List Endpoint with Pagination and Filtering

```python
from app.schemas.common import PaginationRequest, SortRequest
from app.schemas.requests import JobFilterRequest
from app.schemas.responses import JobListResponse

@router.get(
    "/jobs",
    response_model=JobListResponse
)
async def list_jobs(
    pagination: PaginationRequest = Depends(),
    sort: SortRequest = Depends(),
    filters: JobFilterRequest = Depends()
):
    """
    List jobs with pagination, sorting, and filtering.
    
    Supports comprehensive filtering by status, priority, date ranges,
    and text search across job topics and context.
    """
    # Implementation here
    pass
```

### Error Handling with Consistent Responses

```python
from app.schemas.common import NotFoundResponse, ValidationErrorResponse

@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    responses={
        404: {"model": NotFoundResponse},
        422: {"model": ValidationErrorResponse}
    }
)
async def get_job_status(job_id: str):
    """Get detailed job status information."""
    if not job_exists(job_id):
        raise HTTPException(
            status_code=404,
            detail=NotFoundResponse(
                resource="Job",
                resource_id=job_id
            ).dict()
        )
```

## Validation Features

### Custom Validators

The schemas include comprehensive validation:

```python
# Topic validation
@validator("topic")
def validate_topic(cls, v):
    if len(v.strip()) < 3:
        raise ValueError("Topic must be at least 3 characters long")
    return v.strip()

# Date range validation
@validator("created_before")
def validate_date_range(cls, v, values):
    created_after = values.get("created_after")
    if created_after and v and v <= created_after:
        raise ValueError("created_before must be after created_after")
    return v
```

### Field Constraints

- String length limits with `min_length` and `max_length`
- Numeric ranges with `ge`, `le`, `gt`, `lt`
- Pattern matching with `pattern` for formats
- List size limits with `min_items` and `max_items`
- Custom validation logic with `@validator`

## API Documentation Examples

The schemas include comprehensive examples for automatic API documentation:

```python
model_config = ConfigDict(
    json_schema_extra={
        "example": {
            "topic": "Pythagorean Theorem",
            "context": "Explain the mathematical proof...",
            "quality": "medium",
            "use_rag": True
        }
    }
)
```

These examples are automatically used by FastAPI to generate:
- Interactive Swagger UI documentation
- ReDoc documentation
- OpenAPI specification with examples
- Client code generation with proper examples

## Best Practices

1. **Consistent Naming**: Use clear, descriptive field names
2. **Comprehensive Validation**: Include both type and business logic validation
3. **Rich Examples**: Provide realistic examples for documentation
4. **Error Details**: Include specific error codes and field-level errors
5. **Backward Compatibility**: Use optional fields for new features
6. **Performance**: Keep validation efficient for high-throughput endpoints

## Testing Schemas

```python
def test_video_generation_request():
    # Valid request
    request = VideoGenerationRequest(
        topic="Test Topic",
        context="This is a valid context with sufficient length"
    )
    assert request.topic == "Test Topic"
    
    # Invalid request should raise ValidationError
    with pytest.raises(ValidationError):
        VideoGenerationRequest(
            topic="",  # Empty topic should fail
            context="short"  # Too short context should fail
        )
```

This schema system provides a robust foundation for API validation, documentation, and client generation while maintaining type safety and comprehensive error handling.