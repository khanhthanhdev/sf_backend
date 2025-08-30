# User Relationship Management

This document describes the user relationship management functionality that provides user-file associations, access control, job history tracking, and data cleanup procedures.

## Overview

The User Relationship Management system extends the existing user service to provide:

1. **User-File Associations**: Track relationships between users and files with access control
2. **Job History Tracking**: Comprehensive job statistics and trend analysis
3. **Data Cleanup Procedures**: Automated cleanup of old data based on retention policies

## Architecture

### Components

- **UserRelationshipService**: Core service for relationship management
- **Pydantic Models**: Data models for relationships, statistics, and policies
- **API Endpoints**: REST API for accessing relationship functionality
- **Database Integration**: Async database operations with RDS

### Key Models

#### UserFileAssociation
Manages user-file relationships with access levels:
- `owner`: Full access (read, write, delete)
- `read`: Read-only access
- `write`: Read and write access
- `admin`: Administrative access (all permissions)

#### UserJobHistory
Tracks comprehensive job statistics:
- Total jobs by status
- Processing time metrics
- Job type distribution
- Recent activity timeline

#### DataRetentionPolicy
Defines cleanup policies:
- Job retention period (default: 90 days)
- File retention period (default: 365 days)
- Log retention period (default: 30 days)
- Inactive user threshold (default: 180 days)

## API Endpoints

### File Access Management

#### GET /api/v1/user-relationships/files
Get user files with access control information.

**Parameters:**
- `file_type` (optional): Filter by file type
- `access_level` (optional): Filter by access level
- `limit` (default: 100): Maximum files to return
- `offset` (default: 0): Number of files to skip

**Response:**
```json
[
  {
    "file_id": "uuid",
    "filename": "document.pdf",
    "file_type": "document",
    "file_size": 1024000,
    "created_at": "2024-01-15T10:30:00Z",
    "access_level": "owner",
    "can_read": true,
    "can_write": true,
    "can_delete": true,
    "last_accessed_at": "2024-01-15T11:00:00Z"
  }
]
```

#### GET /api/v1/user-relationships/files/{file_id}/access
Check user access to a specific file.

**Parameters:**
- `required_access` (default: read): Required access level

**Response:**
```json
{
  "file_id": "uuid",
  "user_id": "user_123",
  "access_level": "read",
  "has_access": true,
  "accessed_at": "2024-01-15T11:00:00Z"
}
```

### Job History and Analytics

#### GET /api/v1/user-relationships/job-history
Get comprehensive job history and statistics.

**Parameters:**
- `include_stats` (default: true): Include detailed statistics

**Response:**
```json
{
  "user_id": "uuid",
  "stats": {
    "total_jobs": 50,
    "completed_jobs": 45,
    "failed_jobs": 3,
    "cancelled_jobs": 1,
    "active_jobs": 1,
    "success_rate": 90.0,
    "avg_processing_time": 120.5,
    "job_types_count": {
      "video_generation": 40,
      "file_processing": 10
    }
  },
  "recent_activity": [
    {
      "job_id": "uuid",
      "status": "completed",
      "job_type": "video_generation",
      "created_at": "2024-01-15T10:00:00Z",
      "completed_at": "2024-01-15T10:05:00Z"
    }
  ]
}
```

#### GET /api/v1/user-relationships/job-trends
Get job trends over specified period.

**Parameters:**
- `days` (default: 30): Number of days to analyze

**Response:**
```json
{
  "user_id": "user_123",
  "period_days": 30,
  "daily_counts": {
    "2024-01-15": 5,
    "2024-01-14": 3
  },
  "status_trends": {
    "completed": {
      "2024-01-15": 4,
      "2024-01-14": 3
    }
  },
  "total_jobs_in_period": 8,
  "avg_jobs_per_day": 0.27,
  "trend_direction": "increasing"
}
```

### Data Management

#### GET /api/v1/user-relationships/data-summary
Get comprehensive user data summary.

**Response:**
```json
{
  "user_id": "user_123",
  "account_created": "2023-06-01T00:00:00Z",
  "account_age_days": 228,
  "last_active": "2024-01-15T10:00:00Z",
  "status": "active",
  "role": "user",
  "total_files": 25,
  "total_file_size_mb": 150.5,
  "total_jobs": 50,
  "completed_jobs": 45,
  "storage_usage_level": "medium",
  "cleanup_recommended": false
}
```

#### POST /api/v1/user-relationships/cleanup
Clean up user data based on retention policies.

**Parameters:**
- `dry_run` (default: true): Perform simulation without actual cleanup
- `retention_policy` (optional): Custom retention policy

**Request Body:**
```json
{
  "job_retention_days": 90,
  "file_retention_days": 365,
  "cleanup_enabled": true
}
```

**Response:**
```json
{
  "user_id": "user_123",
  "dry_run": true,
  "cleanup_date": "2024-01-15T12:00:00Z",
  "jobs_cleaned": 5,
  "files_cleaned": 3,
  "total_space_freed": 1024000,
  "space_freed_mb": 1.0,
  "jobs_by_status": {
    "completed": 4,
    "failed": 1
  },
  "files_by_type": {
    "document": 2,
    "image": 1
  }
}
```

#### GET /api/v1/user-relationships/cleanup-recommendations
Get cleanup recommendations for the user.

**Response:**
```json
{
  "user_id": "user_123",
  "cleanup_recommended": true,
  "recommendations": [
    "Consider cleaning up old completed jobs to free up database space",
    "Review and remove unnecessary files to reduce storage usage"
  ],
  "estimated_savings_mb": 15.0,
  "retention_policy": {
    "job_retention_days": 90,
    "file_retention_days": 365,
    "cleanup_enabled": true
  }
}
```

### Administrative Functions

#### POST /api/v1/user-relationships/bulk-cleanup
Perform bulk cleanup of inactive users (Admin only).

**Parameters:**
- `inactive_days` (default: 180): Days to consider user inactive
- `dry_run` (default: true): Perform simulation

**Response:**
```json
{
  "inactive_days": 180,
  "dry_run": true,
  "users_processed": 25,
  "total_jobs_cleaned": 150,
  "total_files_cleaned": 75,
  "total_space_freed": 1073741824,
  "average_cleanup_per_user": {
    "jobs": 6.0,
    "files": 3.0,
    "space_mb": 40.96
  }
}
```

## Usage Examples

### Python Client Usage

```python
import httpx
from datetime import datetime

# Get user files with access control
async def get_user_files():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "/api/v1/user-relationships/files",
            params={"file_type": "document", "limit": 50},
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()

# Check file access
async def check_file_access(file_id: str):
    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"/api/v1/user-relationships/files/{file_id}/access",
            params={"required_access": "write"},
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()

# Get job history
async def get_job_history():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "/api/v1/user-relationships/job-history",
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()

# Perform cleanup (dry run)
async def cleanup_user_data():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "/api/v1/user-relationships/cleanup",
            params={"dry_run": True},
            json={
                "job_retention_days": 60,
                "file_retention_days": 180
            },
            headers={"Authorization": "Bearer <token>"}
        )
        return response.json()
```

### Service Integration

```python
from src.app.services.user_relationship_service import get_user_relationship_service
from src.app.database import get_connection_manager

async def example_service_usage():
    # Get service instance
    connection_manager = await get_connection_manager()
    relationship_service = await get_user_relationship_service(connection_manager)
    
    user_id = UUID("user-uuid-here")
    
    # Get user files with access control
    files = await relationship_service.get_user_files_with_access(
        user_id=user_id,
        file_type="document",
        limit=100
    )
    
    # Get job history
    job_history = await relationship_service.get_user_job_history(
        user_id=user_id,
        include_stats=True
    )
    
    # Get data summary
    data_summary = await relationship_service.get_user_data_summary(user_id)
    
    # Perform cleanup
    cleanup_result = await relationship_service.cleanup_user_data(
        user_id=user_id,
        dry_run=True
    )
```

## Database Schema

The user relationship management system uses the existing database schema with additional queries and relationships:

### Key Tables
- `users`: User information and metadata
- `jobs`: Job records with user relationships
- `file_metadata`: File records with user and job relationships
- `job_queue`: Job processing queue

### Indexes
The system relies on existing indexes for performance:
- `idx_jobs_user_id`: Jobs by user
- `idx_files_user_id`: Files by user
- `idx_jobs_status`: Jobs by status
- `idx_files_type`: Files by type

## Configuration

### Retention Policies
Default retention policies can be configured:

```python
# Default retention settings
DEFAULT_JOB_RETENTION_DAYS = 90
DEFAULT_FILE_RETENTION_DAYS = 365
DEFAULT_LOG_RETENTION_DAYS = 30
DEFAULT_INACTIVE_USER_DAYS = 180
```

### Access Control
File access levels are configurable:

```python
class AccessLevel(str, Enum):
    OWNER = "owner"      # Full access
    READ = "read"        # Read-only
    WRITE = "write"      # Read and write
    ADMIN = "admin"      # Administrative access
```

## Security Considerations

1. **Access Control**: Users can only access their own files by default
2. **Admin Functions**: Bulk operations require admin permissions
3. **Data Privacy**: Cleanup operations respect user data privacy
4. **Audit Trail**: All access and cleanup operations are logged

## Performance Considerations

1. **Database Queries**: Optimized queries with proper indexing
2. **Pagination**: Large result sets are paginated
3. **Async Operations**: All database operations are asynchronous
4. **Caching**: Consider caching frequently accessed statistics

## Error Handling

The system provides comprehensive error handling:

- **404 Not Found**: User or file not found
- **403 Forbidden**: Insufficient permissions
- **422 Validation Error**: Invalid input parameters
- **500 Internal Server Error**: System errors

## Testing

Comprehensive test suite covers:

- Unit tests for models and services
- Integration tests for database operations
- API endpoint tests
- Performance tests for large datasets

Run tests with:
```bash
pytest tests/test_user_relationships.py -v
```

## Future Enhancements

Potential future improvements:

1. **File Sharing**: Share files between users with permissions
2. **Advanced Analytics**: More detailed usage analytics
3. **Automated Cleanup**: Scheduled cleanup jobs
4. **Data Export**: Export user data for compliance
5. **Real-time Notifications**: Notify users of cleanup actions