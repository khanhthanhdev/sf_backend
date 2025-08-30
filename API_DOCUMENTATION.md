# T2M API Documentation

## Overview

This document provides comprehensive documentation for the T2M (Text-to-Media) API endpoints. The API is organized into several modules: Authentication, Files, Jobs, System, and Videos.

## Base URL

```
https://your-api-domain.com/api/v1
```

## Authentication

Most endpoints require authentication. Include the authorization token in the request headers:

```
Authorization: Bearer <your-token>
```

**Public endpoints** (no authentication required):

- `GET /auth/health`
- `GET /system/health`

**Optional authentication** (enhanced data for authenticated users):

- All other `/system/*` endpoints

## Common Response Formats

### Success Response

```json
{
  "success": true,
  "data": {
    "id": "12345",
    "status": "completed"
  },
  "message": "Operation completed successfully"
}
```

### Error Response

```json
{
  "success": false,
  "error": {
    "code": "AUTH_INVALID",
    "details": "Token has expired or is malformed"
  }
}
```

### Pagination Format

```json
{
  "success": true,
  "data": {
    "items": [...],
    "pagination": {
      "page": 1,
      "items_per_page": 20,
      "total_items": 150,
      "total_pages": 8,
      "has_next": true,
      "has_previous": false,
      "next_page": 2,
      "previous_page": null
    }
  }
}
```

## Authentication Endpoints

### Health Check

- **Endpoint**: `GET /auth/health`
- **Description**: Check authentication service health
- **Authentication**: Not required
- **Response**: Service health status
- **Example Response**:

```json
{
  "status": "healthy",
  "clerk": {
    "status": "healthy",
    "response_time": "45ms",
    "last_check": "2024-01-15T10:30:00Z"
  },
  "message": "Authentication service health check completed"
}
```

### Get Authentication Status

- **Endpoint**: `GET /auth/status`
- **Description**: Get current user authentication status
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Authentication status and user info
- **Example Response (Authenticated)**:

```json
{
  "authenticated": true,
  "user_id": "user_12345",
  "email": "john@example.com",
  "email_verified": true,
  "request_context": {
    "path": "/auth/status",
    "method": "GET",
    "client_ip": "192.168.1.100"
  }
}
```

- **Example Response (Not Authenticated)**:

```json
{
  "authenticated": false,
  "message": "No authentication provided",
  "request_context": {
    "path": "/auth/status",
    "method": "GET",
    "client_ip": "192.168.1.100"
  }
}
```

### Get Current User Profile

- **Endpoint**: `GET /auth/me`
- **Description**: Get authenticated user's profile information
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Response**: User profile data
- **Example Response**:

```json
{
  "id": "user_12345",
  "username": "john_doe",
  "full_name": "John Doe",
  "email": "john@example.com",
  "image_url": "https://example.com/avatar.jpg",
  "email_verified": true,
  "created_at": "2024-01-01T00:00:00Z",
  "last_sign_in_at": "2024-01-15T10:30:00Z"
}
```

**Note**: `created_at` and `last_sign_in_at` fields may be `null` if not available from the authentication provider.

### Get User Permissions

- **Endpoint**: `GET /auth/permissions`
- **Description**: Get user's permissions and access levels
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Response**: User permissions and role information
- **Example Response**:

```json
{
  "user_id": "user_12345",
  "role": "USER",
  "permissions": [
    "read_files",
    "upload_files",
    "generate_videos"
  ],
  "access_level": "standard"
}
```

### Test Protected Endpoint

- **Endpoint**: `GET /auth/test-protected`
- **Description**: Test endpoint for authenticated users
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Response**: Test response with user ID
- **Example Response**:

```json
{
  "message": "Successfully accessed protected endpoint",
  "user_id": "user_12345",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Test Verified Endpoint

- **Endpoint**: `GET /auth/test-verified`
- **Description**: Test endpoint for verified users only
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Response**: Test response for verified users
- **Example Response**:

```json
{
  "message": "Successfully accessed verified user endpoint",
  "user_id": "user_12345",
  "email": "john@example.com",
  "email_verified": true,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Verify Token

- **Endpoint**: `POST /auth/verify`
- **Description**: Verify authentication token validity
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Response**: Token verification status
- **Example Response**:

```json
{
  "verified": true,
  "user_id": "user_12345",
  "email": "john@example.com",
  "email_verified": true,
  "message": "Token verified successfully"
}
```

## File Management Endpoints

### Upload Single File

- **Endpoint**: `POST /files/upload`
- **Description**: Upload a single file
- **Headers**:
  - `Authorization: Bearer <token>` (required)
  - `Content-Type: multipart/form-data`
- **Parameters**:
  - `file` (file, required): File to upload
  - `file_type` (string, optional): File type category
  - `subdirectory` (string, optional): Target subdirectory
  - `description` (string, optional): File description
- **Response**: File upload confirmation with file ID

### Batch Upload Files

- **Endpoint**: `POST /files/batch-upload`
- **Description**: Upload multiple files at once
- **Headers**:
  - `Authorization: Bearer <token>` (required)
  - `Content-Type: multipart/form-data`
- **Parameters**:
  - `files` (file[], required): Files to upload
  - `file_type` (string, optional): File type for all files
  - `subdirectory` (string, optional): Subdirectory for all files
  - `description` (string, optional): Description for all files
- **Response**: Batch upload results

### List Files

- **Endpoint**: `GET /files`
- **Description**: List user's files with pagination and filtering
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Query Parameters**:

| Name             | Type    | Required | Default | Description                                         |
| ---------------- | ------- | -------- | ------- | --------------------------------------------------- |
| `file_type`      | string  | no       | -       | Filter by file type (document, image, video, audio) |
| `page`           | integer | no       | 1       | Page number (≥1)                                    |
| `items_per_page` | integer | no       | 20      | Items per page (1-100)                              |

- **Response**: Paginated list of files
- **Example Response**:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": "file_123456",
        "filename": "document.pdf",
        "size": 2048576,
        "file_type": "document",
        "created_at": "2024-01-15T10:30:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "items_per_page": 20,
      "total_items": 150,
      "total_pages": 8,
      "has_next": true
    }
  }
}
```

### Get File Details

- **Endpoint**: `GET /files/{file_id}`
- **Description**: Get comprehensive file information including content details and metadata
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `file_id` (string, required): Unique file identifier
- **Response**: Complete file details
- **Example Response**:

```json
{
  "success": true,
  "data": {
    "id": "file_123456",
    "filename": "document.pdf",
    "size": 2048576,
    "content_type": "application/pdf",
    "file_type": "document",
    "subdirectory": "uploads/2024",
    "description": "Important document",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
    "download_count": 5,
    "metadata": {
      "pages": 10,
      "author": "John Doe",
      "creation_date": "2024-01-15"
    }
  }
}
```

### Get File Metadata

- **Endpoint**: `GET /files/{file_id}/metadata`
- **Description**: Get file metadata and technical information only
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `file_id` (string, required): Unique file identifier
- **Response**: File metadata only
- **Example Response**:

```json
{
  "success": true,
  "data": {
    "content_type": "application/pdf",
    "size": 2048576,
    "checksum": "sha256:abc123...",
    "metadata": {
      "pages": 10,
      "author": "John Doe",
      "creation_date": "2024-01-15"
    }
  }
}
```

### Download File

- **Endpoint**: `GET /files/{file_id}/download`
- **Description**: Download file content
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `file_id` (string, required): Unique file identifier
- **Query Parameters**:
  - `inline` (boolean, default: false): Serve inline instead of attachment
- **Response**: File content

### Stream File

- **Endpoint**: `GET /files/{file_id}/stream`
- **Description**: Stream file content
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `file_id` (string, required): Unique file identifier
- **Query Parameters**:
  - `quality` (string, default: "auto"): Stream quality
- **Response**: Streamed file content

### Get File Thumbnail

- **Endpoint**: `GET /files/{file_id}/thumbnail`
- **Description**: Get file thumbnail
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `file_id` (string, required): Unique file identifier
- **Query Parameters**:
  - `size` (string, default: "medium"): Thumbnail size (small|medium|large)
- **Response**: Thumbnail image

### Get File Analytics

- **Endpoint**: `GET /files/{file_id}/analytics`
- **Description**: Get file usage analytics
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `file_id` (string, required): Unique file identifier
- **Response**: File analytics data

### Delete File

- **Endpoint**: `DELETE /files/{file_id}`
- **Description**: Delete a file
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `file_id` (string, required): Unique file identifier
- **Response**: Deletion confirmation

### Get File Statistics

- **Endpoint**: `GET /files/stats`
- **Description**: Get user's file statistics
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Response**: File usage statistics

### Cleanup Files

- **Endpoint**: `POST /files/cleanup`
- **Description**: Cleanup files based on criteria
- **Headers**:
  - `Authorization: Bearer <token>` (required)
  - `Content-Type: application/json`
- **Request Body**: File cleanup criteria
- **Response**: Cleanup results

### Secure File Access

- **Endpoint**: `GET /files/secure/{file_id}`
- **Description**: Access files via signed URLs
- **Query Parameters**:
  - `user_id` (string, required): User ID from signed URL
  - `expires` (string, required): Expiration timestamp
  - `signature` (string, required): URL signature
  - `file_type` (string, optional): File type
  - `inline` (string, default: "false"): Serve inline
  - `size` (string, optional): Thumbnail size
  - `quality` (string, optional): Stream quality
- **Response**: Secure file access

## Job Management Endpoints

### List Jobs

- **Endpoint**: `GET /jobs`
- **Description**: List user's jobs with pagination and filtering
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Query Parameters**: Pagination and filtering parameters
- **Response**: Paginated list of jobs

### Get Job Details

- **Endpoint**: `GET /jobs/{job_id}`
- **Description**: Get comprehensive job information including status, progress, and results
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Response**: Complete job details and status
- **Example Response**:

```json
{
  "success": true,
  "data": {
    "id": "job_789012",
    "type": "video_generation",
    "status": "completed",
    "progress": 100,
    "created_at": "2024-01-15T10:30:00Z",
    "started_at": "2024-01-15T10:30:05Z",
    "completed_at": "2024-01-15T10:35:30Z",
    "duration": 325,
    "parameters": {
      "prompt": "A beautiful sunset over mountains",
      "duration": 10,
      "quality": "1080p"
    },
    "result": {
      "file_id": "video_456789",
      "file_size": 15728640,
      "thumbnail_url": "/videos/job_789012/thumbnail"
    },
    "error": null
  }
}
```

### Get Job Logs

- **Endpoint**: `GET /jobs/{job_id}/logs`
- **Description**: Get job execution logs with filtering and pagination
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Query Parameters**:

| Name     | Type    | Required | Default | Description                                       |
| -------- | ------- | -------- | ------- | ------------------------------------------------- |
| `limit`  | integer | no       | 100     | Maximum log entries (1-1000)                      |
| `offset` | integer | no       | 0       | Log entries to skip (≥0)                          |
| `level`  | string  | no       | -       | Filter by log level (DEBUG, INFO, WARNING, ERROR) |

- **Response**: Job logs with metadata
- **Example Response**:

```json
{
  "success": true,
  "data": {
    "logs": [
      {
        "timestamp": "2024-01-15T10:30:15Z",
        "level": "INFO",
        "message": "Video processing started",
        "details": {
          "step": "initialization",
          "progress": 0
        }
      },
      {
        "timestamp": "2024-01-15T10:30:45Z",
        "level": "INFO",
        "message": "Processing frame 100/1000",
        "details": {
          "step": "rendering",
          "progress": 10
        }
      }
    ],
    "total_logs": 250,
    "has_more": true
  }
}
```

### Cancel Job

- **Endpoint**: `POST /jobs/{job_id}/cancel`
- **Description**: Cancel a running job
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Response**: Cancellation confirmation

### Delete Job

- **Endpoint**: `DELETE /jobs/{job_id}`
- **Description**: Delete a job and its data
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Response**: Deletion confirmation

## System Monitoring Endpoints

### System Health Check

- **Endpoint**: `GET /system/health`
- **Description**: Get overall system health status
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: System health metrics

### System Metrics

- **Endpoint**: `GET /system/metrics`
- **Description**: Get detailed system metrics
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: System performance metrics

### Queue Status

- **Endpoint**: `GET /system/queue`
- **Description**: Get job queue status and statistics
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Queue status and metrics

### Cache Information

- **Endpoint**: `GET /system/cache`
- **Description**: Get cache status and information
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Cache metrics and status

### Cache Metrics

- **Endpoint**: `GET /system/cache/metrics`
- **Description**: Get detailed cache metrics
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Cache performance metrics

### Cache Report

- **Endpoint**: `GET /system/cache/report`
- **Description**: Get comprehensive cache report
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Detailed cache report

### Performance Summary

- **Endpoint**: `GET /system/performance`
- **Description**: Get system performance summary
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Query Parameters**:
  - `hours` (integer, default: 1): Time range in hours
- **Response**: Performance summary

### Connection Statistics

- **Endpoint**: `GET /system/connections`
- **Description**: Get connection statistics
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Connection metrics

### Async Statistics

- **Endpoint**: `GET /system/async`
- **Description**: Get asynchronous processing statistics
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Async processing metrics

### Deduplication Statistics

- **Endpoint**: `GET /system/deduplication`
- **Description**: Get deduplication statistics
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Deduplication metrics

### Invalidate Cache

- **Endpoint**: `POST /system/cache/invalidate`
- **Description**: Invalidate cache entries
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Query Parameters**:
  - `pattern` (string, optional): Cache key pattern
  - `user_id` (string, optional): User-specific cache
- **Response**: Cache invalidation results

### Warm Cache

- **Endpoint**: `POST /system/cache/warm`
- **Description**: Pre-warm cache with frequently accessed data
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Cache warming results

### Optimize Performance

- **Endpoint**: `POST /system/optimize`
- **Description**: Trigger system performance optimization
- **Headers**:
  - `Authorization: Bearer <token>` (optional)
- **Response**: Optimization results

## Video Processing Endpoints

### Generate Video

- **Endpoint**: `POST /videos/generate`
- **Description**: Create a new video generation job with automatic S3 upload
- **Headers**:
  - `Authorization: Bearer <token>` (required)
  - `Content-Type: application/json`
- **Request Body**: Job creation parameters
- **Response**: Job creation confirmation with job ID
- **Example Request**:

```json
{
  "configuration": {
    "topic": "Mathematical Functions",
    "description": "Educational video explaining quadratic functions",
    "quality": "high",
    "enable_s3_upload": true,
    "generate_thumbnails": true
  }
}
```

- **Example Response**:

```json
{
  "success": true,
  "data": {
    "job_id": "job_789012",
    "status": "queued",
    "progress": {
      "percentage": 0.0,
      "current_stage": null,
      "stages_completed": [],
      "estimated_completion": "2024-01-15T10:35:00Z"
    },
    "created_at": "2024-01-15T10:30:00Z",
    "storage_mode": "s3",
    "upload_enabled": true
  }
}
```

### Get Job Status

- **Endpoint**: `GET /videos/jobs/{job_id}/status`
- **Description**: Get video generation job status with S3 URLs
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Response**: Job status and progress with S3 URLs
- **Example Response**:

```json
{
  "success": true,
  "data": {
    "job_id": "job_789012",
    "status": "completed",
    "progress": {
      "percentage": 100.0,
      "current_stage": "completed",
      "stages_completed": ["validation", "content_preparation", "video_generation", "s3_upload", "post_processing"]
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:35:00Z",
    "completed_at": "2024-01-15T10:35:00Z",
    "video_urls": {
      "s3_url": "s3://t2m-videos-prod/users/user123/jobs/job_789012/output.mp4",
      "streaming_url": "https://t2m-videos-prod.s3.amazonaws.com/users/user123/jobs/job_789012/output.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&X-Amz-Credential=...",
      "download_url": "/api/v1/videos/jobs/job_789012/download"
    },
    "thumbnails": [
      {
        "size": "small",
        "s3_url": "s3://t2m-thumbnails-prod/users/user123/jobs/job_789012/thumb_small.jpg",
        "streaming_url": "https://t2m-thumbnails-prod.s3.amazonaws.com/users/user123/jobs/job_789012/thumb_small.jpg?..."
      },
      {
        "size": "medium", 
        "s3_url": "s3://t2m-thumbnails-prod/users/user123/jobs/job_789012/thumb_medium.jpg",
        "streaming_url": "https://t2m-thumbnails-prod.s3.amazonaws.com/users/user123/jobs/job_789012/thumb_medium.jpg?..."
      },
      {
        "size": "large",
        "s3_url": "s3://t2m-thumbnails-prod/users/user123/jobs/job_789012/thumb_large.jpg", 
        "streaming_url": "https://t2m-thumbnails-prod.s3.amazonaws.com/users/user123/jobs/job_789012/thumb_large.jpg?..."
      }
    ],
    "scene_files": [
      {
        "scene_number": 1,
        "video_s3_url": "s3://t2m-videos-prod/users/user123/jobs/job_789012/scenes/scene_001.mp4",
        "video_streaming_url": "https://t2m-videos-prod.s3.amazonaws.com/users/user123/jobs/job_789012/scenes/scene_001.mp4?...",
        "code_s3_url": "s3://t2m-code-prod/users/user123/jobs/job_789012/scenes/scene_001.py",
        "code_download_url": "/api/v1/videos/jobs/job_789012/scenes/1/code"
      }
    ],
    "metadata": {
      "total_scenes": 3,
      "duration_seconds": 45.2,
      "resolution": "1920x1080",
      "file_size_bytes": 15728640,
      "storage_mode": "s3"
    }
  }
}
```

### Download Video

- **Endpoint**: `GET /videos/jobs/{job_id}/download`
- **Description**: Download generated video (redirects to S3 streaming URL)
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Query Parameters**:
  - `inline` (boolean, default: false): Serve inline instead of attachment
- **Response**: 
  - **If S3 enabled**: HTTP 302 redirect to S3 streaming URL
  - **If local storage**: Direct file content
- **Example Response Headers**:

```http
HTTP/1.1 302 Found
Location: https://t2m-videos-prod.s3.amazonaws.com/users/user123/jobs/job_789012/output.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&...
Cache-Control: public, max-age=3600
```

### Stream Video

- **Endpoint**: `GET /videos/jobs/{job_id}/stream`
- **Description**: Stream generated video with range request support
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Query Parameters**:
  - `quality` (string, default: "auto"): Stream quality (auto|720p|1080p)
- **Response**: 
  - **If S3 enabled**: HTTP 302 redirect to S3 streaming URL with appropriate headers
  - **If local storage**: Streamed video content
- **Example Response**:

```http
HTTP/1.1 302 Found
Location: https://t2m-videos-prod.s3.amazonaws.com/users/user123/jobs/job_789012/output.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&...
Accept-Ranges: bytes
Content-Type: video/mp4
```

### Get Video Metadata

- **Endpoint**: `GET /videos/{job_id}/metadata`
- **Description**: Get comprehensive video metadata and technical information
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Response**: Detailed video metadata
- **Example Response**:

```json
{
  "success": true,
  "data": {
    "job_id": "job_789012",
    "video": {
      "duration": 10.5,
      "width": 1920,
      "height": 1080,
      "fps": 30,
      "bitrate": 5000000,
      "codec": "h264",
      "format": "mp4",
      "file_size": 15728640
    },
    "audio": {
      "codec": "aac",
      "bitrate": 128000,
      "sample_rate": 44100,
      "channels": 2
    },
    "generation": {
      "prompt": "A beautiful sunset over mountains",
      "model": "t2v-v2.1",
      "seed": 12345,
      "created_at": "2024-01-15T10:30:00Z"
    }
  }
}
```

### Get Video Thumbnail

- **Endpoint**: `GET /videos/{job_id}/thumbnail`
- **Description**: Get video thumbnail
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Query Parameters**:
  - `size` (string, default: "medium"): Thumbnail size (small|medium|large)
- **Response**: Video thumbnail image

## Error Handling

### Error Codes

| Code                  | HTTP Status | Description                     |
| --------------------- | ----------- | ------------------------------- |
| `AUTH_REQUIRED`       | 401         | Authentication required         |
| `AUTH_INVALID`        | 401         | Invalid authentication token    |
| `AUTH_EXPIRED`        | 401         | Authentication token expired    |
| `PERMISSION_DENIED`   | 403         | Insufficient permissions        |
| `RESOURCE_NOT_FOUND`  | 404         | Requested resource not found    |
| `VALIDATION_ERROR`    | 400         | Request validation failed       |
| `RATE_LIMIT_EXCEEDED` | 429         | Rate limit exceeded             |
| `SERVER_ERROR`        | 500         | Internal server error           |
| `SERVICE_UNAVAILABLE` | 503         | Service temporarily unavailable |

### Error Response Examples

**Invalid Authentication (401)**

```json
{
  "success": false,
  "error": {
    "code": "AUTH_INVALID",
    "details": "Token has expired or is malformed"
  }
}
```

**Resource Not Found (404)**

```json
{
  "success": false,
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "File not found",
    "details": "File with ID 'file_123456' does not exist or you don't have access"
  }
}
```

**Validation Error (400)**

```json
{
  "success": false,
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Request validation failed",
    "details": {
      "file_type": [
        "Invalid file type. Must be one of: document, image, video, audio"
      ],
      "page": ["Page must be greater than 0"]
    }
  }
}
```

**Rate Limit Exceeded (429)**

```json
{
  "success": false,
  "error": {
    "code": "RATE_LIMIT_EXCEEDED",
    "message": "Rate limit exceeded",
    "details": "You have exceeded the limit of 100 uploads per hour. Try again in 45 minutes."
  }
}
```

## Rate Limits

- **General API**: 1000 requests per hour per user
- **File Upload**: 100 uploads per hour per user
- **Video Generation**: 10 jobs per hour per user
- **System Endpoints**: 500 requests per hour per user

## Code Examples

### cURL Examples

**Upload a file**

```bash
curl -X POST "https://api.example.com/api/v1/files/upload" \
  -H "Authorization: Bearer your-token-here" \
  -F "file=@example.txt" \
  -F "file_type=document" \
  -F "description=Sample document"
```

**Generate video with S3 upload**

```bash
curl -X POST "https://api.example.com/api/v1/videos/generate" \
  -H "Authorization: Bearer your-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "configuration": {
      "topic": "Mathematical Functions",
      "description": "Educational video explaining quadratic functions",
      "quality": "high",
      "enable_s3_upload": true,
      "generate_thumbnails": true
    }
  }'
```

**Get job status with S3 URLs**

```bash
curl -X GET "https://api.example.com/api/v1/videos/jobs/job_789012/status" \
  -H "Authorization: Bearer your-token-here"
```

**Download scene code file**

```bash
curl -X GET "https://api.example.com/api/v1/videos/jobs/job_789012/scenes/1/code" \
  -H "Authorization: Bearer your-token-here" \
  -o scene_1_code.py
```

### JavaScript/TypeScript Examples

**Generate video and poll for completion**

```typescript
interface VideoGenerationResponse {
  job_id: string;
  status: string;
  video_urls?: {
    s3_url: string;
    streaming_url: string;
    download_url: string;
  };
  thumbnails?: Array<{
    size: string;
    s3_url: string;
    streaming_url: string;
  }>;
}

// Generate video
const generateVideo = async (config: any): Promise<string> => {
  const response = await fetch('/api/v1/videos/generate', {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${token}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({ configuration: config })
  });
  
  const result = await response.json();
  return result.data.job_id;
};

// Poll for job completion
const pollJobStatus = async (jobId: string): Promise<VideoGenerationResponse> => {
  while (true) {
    const response = await fetch(`/api/v1/videos/jobs/${jobId}/status`, {
      headers: { 'Authorization': `Bearer ${token}` }
    });
    
    const result = await response.json();
    
    if (result.data.status === 'completed') {
      return result.data;
    } else if (result.data.status === 'failed') {
      throw new Error('Video generation failed');
    }
    
    // Wait 5 seconds before next poll
    await new Promise(resolve => setTimeout(resolve, 5000));
  }
};

// Complete workflow
const generateAndWaitForVideo = async () => {
  const jobId = await generateVideo({
    topic: "Mathematical Functions",
    description: "Educational video explaining quadratic functions",
    quality: "high",
    enable_s3_upload: true,
    generate_thumbnails: true
  });
  
  const result = await pollJobStatus(jobId);
  
  // Use S3 streaming URL for video player
  const videoElement = document.getElementById('video-player') as HTMLVideoElement;
  videoElement.src = result.video_urls.streaming_url;
  
  // Display thumbnails
  const thumbnailContainer = document.getElementById('thumbnails');
  result.thumbnails?.forEach(thumb => {
    const img = document.createElement('img');
    img.src = thumb.streaming_url;
    img.alt = `Thumbnail ${thumb.size}`;
    thumbnailContainer?.appendChild(img);
  });
};
```

### React Component Example

```tsx
import React, { useState, useEffect } from 'react';

interface VideoPlayerProps {
  jobId: string;
  authToken: string;
}

const VideoPlayer: React.FC<VideoPlayerProps> = ({ jobId, authToken }) => {
  const [videoData, setVideoData] = useState<VideoGenerationResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchVideoData = async () => {
      try {
        const response = await fetch(`/api/v1/videos/jobs/${jobId}/status`, {
          headers: { 'Authorization': `Bearer ${authToken}` }
        });
        
        const result = await response.json();
        
        if (result.success && result.data.status === 'completed') {
          setVideoData(result.data);
        } else if (result.data.status === 'failed') {
          setError('Video generation failed');
        }
      } catch (err) {
        setError('Failed to fetch video data');
      } finally {
        setLoading(false);
      }
    };

    fetchVideoData();
  }, [jobId, authToken]);

  if (loading) return <div>Loading video...</div>;
  if (error) return <div>Error: {error}</div>;
  if (!videoData) return <div>No video data available</div>;

  return (
    <div className="video-player-container">
      <video 
        controls 
        width="800" 
        height="450"
        src={videoData.video_urls?.streaming_url}
        poster={videoData.thumbnails?.find(t => t.size === 'medium')?.streaming_url}
      >
        Your browser does not support the video tag.
      </video>
      
      <div className="thumbnails">
        {videoData.thumbnails?.map((thumb, index) => (
          <img 
            key={index}
            src={thumb.streaming_url} 
            alt={`Thumbnail ${thumb.size}`}
            className={`thumbnail thumbnail-${thumb.size}`}
          />
        ))}
      </div>
      
      <div className="video-info">
        <p>Duration: {videoData.metadata?.duration_seconds}s</p>
        <p>Resolution: {videoData.metadata?.resolution}</p>
        <p>File Size: {(videoData.metadata?.file_size_bytes / 1024 / 1024).toFixed(2)} MB</p>
      </div>
    </div>
  );
};

export default VideoPlayer;
```

## Additional Video Endpoints

### Get Scene Code File

- **Endpoint**: `GET /videos/jobs/{job_id}/scenes/{scene_number}/code`
- **Description**: Download the generated Manim code for a specific scene
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
  - `scene_number` (integer, required): Scene number (1-based)
- **Query Parameters**:
  - `format` (string, default: "raw"): Code format (raw|formatted)
- **Response**: Scene code file
- **Example Response**:

```http
HTTP/1.1 200 OK
Content-Type: text/x-python
Content-Disposition: attachment; filename="scene_001.py"
X-S3-URL: s3://t2m-code-prod/users/user123/jobs/job_789012/scenes/scene_001.py

from manim import *

class Scene001(Scene):
    def construct(self):
        # Generated Manim code for mathematical functions
        title = Text("Quadratic Functions", font_size=48)
        self.play(Write(title))
        self.wait(1)
        
        # Add quadratic equation
        equation = MathTex(r"f(x) = ax^2 + bx + c")
        equation.next_to(title, DOWN, buff=1)
        self.play(Write(equation))
        self.wait(2)
```

### List Scene Files

- **Endpoint**: `GET /videos/jobs/{job_id}/scenes`
- **Description**: List all scene files for a job (videos and code)
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Path Parameters**:
  - `job_id` (string, required): Unique job identifier
- **Response**: List of scene files with S3 URLs
- **Example Response**:

```json
{
  "success": true,
  "data": {
    "job_id": "job_789012",
    "total_scenes": 3,
    "scenes": [
      {
        "scene_number": 1,
        "title": "Introduction to Quadratic Functions",
        "video": {
          "s3_url": "s3://t2m-videos-prod/users/user123/jobs/job_789012/scenes/scene_001.mp4",
          "streaming_url": "https://t2m-videos-prod.s3.amazonaws.com/users/user123/jobs/job_789012/scenes/scene_001.mp4?...",
          "duration_seconds": 15.2,
          "file_size_bytes": 5242880
        },
        "code": {
          "s3_url": "s3://t2m-code-prod/users/user123/jobs/job_789012/scenes/scene_001.py",
          "download_url": "/api/v1/videos/jobs/job_789012/scenes/1/code",
          "file_size_bytes": 2048
        }
      },
      {
        "scene_number": 2,
        "title": "Graphing Quadratic Functions",
        "video": {
          "s3_url": "s3://t2m-videos-prod/users/user123/jobs/job_789012/scenes/scene_002.mp4",
          "streaming_url": "https://t2m-videos-prod.s3.amazonaws.com/users/user123/jobs/job_789012/scenes/scene_002.mp4?...",
          "duration_seconds": 18.7,
          "file_size_bytes": 6291456
        },
        "code": {
          "s3_url": "s3://t2m-code-prod/users/user123/jobs/job_789012/scenes/scene_002.py",
          "download_url": "/api/v1/videos/jobs/job_789012/scenes/2/code",
          "file_size_bytes": 3072
        }
      }
    ]
  }
}
```

### Upload Custom Assets

- **Endpoint**: `POST /videos/assets/upload`
- **Description**: Upload custom assets (images, audio) for use in video generation
- **Headers**:
  - `Authorization: Bearer <token>` (required)
  - `Content-Type: multipart/form-data`
- **Parameters**:
  - `file` (file, required): Asset file to upload
  - `asset_type` (string, required): Asset type (image|audio|font|data)
  - `description` (string, optional): Asset description
  - `public` (boolean, default: false): Make asset publicly accessible
- **Response**: Asset upload confirmation with S3 URLs
- **Example Response**:

```json
{
  "success": true,
  "data": {
    "asset_id": "asset_456789",
    "filename": "custom_background.jpg",
    "asset_type": "image",
    "s3_url": "s3://t2m-assets-prod/users/user123/assets/asset_456789.jpg",
    "public_url": "https://t2m-assets-prod.s3.amazonaws.com/public/asset_456789.jpg",
    "file_size_bytes": 1048576,
    "metadata": {
      "width": 1920,
      "height": 1080,
      "format": "JPEG"
    },
    "created_at": "2024-01-15T10:30:00Z"
  }
}
```

### List User Assets

- **Endpoint**: `GET /videos/assets`
- **Description**: List user's uploaded assets
- **Headers**:
  - `Authorization: Bearer <token>` (required)
- **Query Parameters**:
  - `asset_type` (string, optional): Filter by asset type
  - `page` (integer, default: 1): Page number
  - `items_per_page` (integer, default: 20): Items per page
- **Response**: Paginated list of assets with S3 URLs

## Database Schema for S3 Integration

To support the S3 integration, you'll need to update your database schema to store S3 URLs and metadata. Here's the recommended schema:

### Video Jobs Table

```sql
-- Update existing jobs table
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS storage_mode VARCHAR(20) DEFAULT 'local';
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS s3_bucket VARCHAR(255);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS s3_key_prefix VARCHAR(500);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS upload_completed_at TIMESTAMP;

-- Add index for S3-related queries
CREATE INDEX IF NOT EXISTS idx_jobs_storage_mode ON jobs(storage_mode);
CREATE INDEX IF NOT EXISTS idx_jobs_s3_bucket ON jobs(s3_bucket);
```

### Video Files Table

```sql
CREATE TABLE IF NOT EXISTS video_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    scene_number INTEGER,
    file_type VARCHAR(50) NOT NULL, -- 'video', 'thumbnail', 'code', 'asset'
    
    -- Local file information
    local_path VARCHAR(1000),
    
    -- S3 information
    s3_bucket VARCHAR(255),
    s3_key VARCHAR(1000),
    s3_url VARCHAR(2000),
    s3_etag VARCHAR(255),
    
    -- File metadata
    filename VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT,
    content_type VARCHAR(255),
    checksum_sha256 VARCHAR(64),
    
    -- Video-specific metadata
    duration_seconds DECIMAL(10,3),
    width INTEGER,
    height INTEGER,
    fps DECIMAL(8,3),
    bitrate BIGINT,
    codec VARCHAR(50),
    
    -- Access tracking
    download_count INTEGER DEFAULT 0,
    view_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,
    
    -- Upload tracking
    upload_started_at TIMESTAMP,
    upload_completed_at TIMESTAMP,
    upload_duration_seconds DECIMAL(10,3),
    upload_status VARCHAR(20) DEFAULT 'pending', -- 'pending', 'uploading', 'completed', 'failed'
    upload_error TEXT,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(job_id, scene_number, file_type),
    CHECK (file_type IN ('video', 'thumbnail', 'code', 'asset')),
    CHECK (upload_status IN ('pending', 'uploading', 'completed', 'failed'))
);

-- Indexes for performance
CREATE INDEX idx_video_files_job_id ON video_files(job_id);
CREATE INDEX idx_video_files_user_id ON video_files(user_id);
CREATE INDEX idx_video_files_s3_bucket_key ON video_files(s3_bucket, s3_key);
CREATE INDEX idx_video_files_type_status ON video_files(file_type, upload_status);
CREATE INDEX idx_video_files_created_at ON video_files(created_at);
```

### Thumbnails Table

```sql
CREATE TABLE IF NOT EXISTS video_thumbnails (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    video_file_id UUID NOT NULL REFERENCES video_files(id) ON DELETE CASCADE,
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    
    -- Thumbnail specifications
    size VARCHAR(20) NOT NULL, -- 'small', 'medium', 'large'
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    timestamp_seconds DECIMAL(8,3) DEFAULT 0,
    
    -- File information
    filename VARCHAR(255) NOT NULL,
    file_size_bytes BIGINT,
    
    -- S3 information
    s3_bucket VARCHAR(255),
    s3_key VARCHAR(1000),
    s3_url VARCHAR(2000),
    streaming_url VARCHAR(2000),
    
    -- Access tracking
    view_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(video_file_id, size),
    CHECK (size IN ('small', 'medium', 'large'))
);

-- Indexes
CREATE INDEX idx_thumbnails_video_file_id ON video_thumbnails(video_file_id);
CREATE INDEX idx_thumbnails_job_id ON video_thumbnails(job_id);
CREATE INDEX idx_thumbnails_user_id ON video_thumbnails(user_id);
```

### Scene Code Files Table

```sql
CREATE TABLE IF NOT EXISTS scene_code_files (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    user_id VARCHAR(255) NOT NULL,
    scene_number INTEGER NOT NULL,
    
    -- Code information
    filename VARCHAR(255) NOT NULL,
    code_content TEXT,
    file_size_bytes BIGINT,
    
    -- S3 information
    s3_bucket VARCHAR(255),
    s3_key VARCHAR(1000),
    s3_url VARCHAR(2000),
    
    -- Code metadata
    language VARCHAR(50) DEFAULT 'python',
    manim_version VARCHAR(50),
    dependencies JSONB,
    
    -- Access tracking
    download_count INTEGER DEFAULT 0,
    last_accessed_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(job_id, scene_number)
);

-- Indexes
CREATE INDEX idx_scene_code_job_id ON scene_code_files(job_id);
CREATE INDEX idx_scene_code_user_id ON scene_code_files(user_id);
CREATE INDEX idx_scene_code_scene_number ON scene_code_files(job_id, scene_number);
```

### User Assets Table

```sql
CREATE TABLE IF NOT EXISTS user_assets (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(255) NOT NULL,
    
    -- Asset information
    filename VARCHAR(255) NOT NULL,
    asset_type VARCHAR(50) NOT NULL, -- 'image', 'audio', 'font', 'data'
    description TEXT,
    file_size_bytes BIGINT,
    
    -- S3 information
    s3_bucket VARCHAR(255),
    s3_key VARCHAR(1000),
    s3_url VARCHAR(2000),
    public_url VARCHAR(2000), -- For publicly accessible assets
    
    -- Asset metadata
    content_type VARCHAR(255),
    metadata JSONB, -- Store asset-specific metadata (dimensions, duration, etc.)
    
    -- Access control
    is_public BOOLEAN DEFAULT false,
    
    -- Usage tracking
    usage_count INTEGER DEFAULT 0,
    last_used_at TIMESTAMP,
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CHECK (asset_type IN ('image', 'audio', 'font', 'data'))
);

-- Indexes
CREATE INDEX idx_user_assets_user_id ON user_assets(user_id);
CREATE INDEX idx_user_assets_type ON user_assets(asset_type);
CREATE INDEX idx_user_assets_public ON user_assets(is_public);
```

### S3 Upload Tracking Table

```sql
CREATE TABLE IF NOT EXISTS s3_upload_logs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    job_id UUID REFERENCES jobs(id),
    user_id VARCHAR(255) NOT NULL,
    file_id UUID, -- References video_files.id or other file tables
    
    -- Upload details
    file_path VARCHAR(1000),
    s3_bucket VARCHAR(255),
    s3_key VARCHAR(1000),
    file_size_bytes BIGINT,
    
    -- Upload tracking
    upload_method VARCHAR(50), -- 'single', 'multipart'
    started_at TIMESTAMP NOT NULL,
    completed_at TIMESTAMP,
    duration_seconds DECIMAL(10,3),
    
    -- Status tracking
    status VARCHAR(20) NOT NULL, -- 'started', 'progress', 'completed', 'failed'
    progress_percentage DECIMAL(5,2) DEFAULT 0,
    bytes_uploaded BIGINT DEFAULT 0,
    
    -- Error handling
    retry_count INTEGER DEFAULT 0,
    error_message TEXT,
    error_code VARCHAR(100),
    
    -- Timestamps
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    CHECK (status IN ('started', 'progress', 'completed', 'failed')),
    CHECK (progress_percentage >= 0 AND progress_percentage <= 100)
);

-- Indexes
CREATE INDEX idx_s3_upload_logs_job_id ON s3_upload_logs(job_id);
CREATE INDEX idx_s3_upload_logs_user_id ON s3_upload_logs(user_id);
CREATE INDEX idx_s3_upload_logs_status ON s3_upload_logs(status);
CREATE INDEX idx_s3_upload_logs_created_at ON s3_upload_logs(created_at);
```

This database schema provides:

1. **Complete S3 URL storage** for videos, thumbnails, code files, and assets
2. **Metadata tracking** for file sizes, dimensions, durations, etc.
3. **Upload progress tracking** for monitoring S3 uploads
4. **Access analytics** with download/view counts
5. **Error handling** for failed uploads
6. **Performance optimization** with appropriate indexes
7. **Data integrity** with foreign key constraints and check constraints

The frontend can now retrieve S3 URLs from the database and access files directly from S3, with the API handling authentication and access control through presigned URLs.
    "quality": "1080p"
  }'
```

**Get job status**

```bash
curl -X GET "https://api.example.com/api/v1/jobs/job_789012" \
  -H "Authorization: Bearer your-token-here"
```

**Get system metrics**

```bash
curl -X GET "https://api.example.com/api/v1/system/metrics" \
  -H "Authorization: Bearer your-token-here"
```

### Python Examples

**File Management**

```python
import requests

headers = {"Authorization": "Bearer your-token-here"}
base_url = "https://api.example.com/api/v1"

# Upload file
with open("example.txt", "rb") as f:
    files = {"file": f}
    data = {"file_type": "document", "description": "Sample document"}
    response = requests.post(f"{base_url}/files/upload", headers=headers, files=files, data=data)
    file_data = response.json()
    print(f"File uploaded: {file_data['data']['id']}")

# List files
response = requests.get(f"{base_url}/files", headers=headers, params={"page": 1, "items_per_page": 10})
files = response.json()
print(f"Found {files['data']['pagination']['total_items']} files")
```

**Job Management**

```python
# Get job logs
job_id = "job_789012"
response = requests.get(f"{base_url}/jobs/{job_id}/logs", headers=headers, params={"limit": 50, "level": "INFO"})
logs = response.json()
print(f"Retrieved {len(logs['data']['logs'])} log entries")

# Cancel job
response = requests.post(f"{base_url}/jobs/{job_id}/cancel", headers=headers)
if response.json()['success']:
    print("Job cancelled successfully")
```

**Video Processing**

```python
# Generate video
job_data = {
    "prompt": "A beautiful sunset over mountains",
    "duration": 10,
    "quality": "1080p"
}
response = requests.post(f"{base_url}/videos/generate", headers=headers, json=job_data)
job = response.json()
job_id = job['data']['job_id']
print(f"Video generation started: {job_id}")

# Check status
response = requests.get(f"{base_url}/videos/{job_id}/status", headers=headers)
status = response.json()
print(f"Job status: {status['data']['status']} ({status['data']['progress']}%)")
```

**System Monitoring**

```python
# Get system metrics
response = requests.get(f"{base_url}/system/metrics", headers=headers)
metrics = response.json()
print(f"CPU usage: {metrics['data']['cpu_usage']}%")
print(f"Memory usage: {metrics['data']['memory_usage']}%")

# Get queue status
response = requests.get(f"{base_url}/system/queue", headers=headers)
queue = response.json()
print(f"Jobs in queue: {queue['data']['pending_jobs']}")
```

### JavaScript Examples

**File Management**

```javascript
const headers = {
  Authorization: "Bearer your-token-here",
};
const baseUrl = "https://api.example.com/api/v1";

// Upload file
const formData = new FormData();
formData.append("file", fileInput.files[0]);
formData.append("file_type", "document");
formData.append("description", "Sample document");

fetch(`${baseUrl}/files/upload`, {
  method: "POST",
  headers: headers,
  body: formData,
})
  .then((response) => response.json())
  .then((data) => console.log("File uploaded:", data.data.id));

// List files with pagination
fetch(`${baseUrl}/files?page=1&items_per_page=10`, {
  headers: headers,
})
  .then((response) => response.json())
  .then((data) =>
    console.log(`Found ${data.data.pagination.total_items} files`)
  );
```

**Job Management**

```javascript
// Get job logs
const jobId = "job_789012";
fetch(`${baseUrl}/jobs/${jobId}/logs?limit=50&level=INFO`, {
  headers: headers,
})
  .then((response) => response.json())
  .then((data) =>
    console.log(`Retrieved ${data.data.logs.length} log entries`)
  );

// Cancel job
fetch(`${baseUrl}/jobs/${jobId}/cancel`, {
  method: "POST",
  headers: headers,
})
  .then((response) => response.json())
  .then((data) => {
    if (data.success) console.log("Job cancelled successfully");
  });
```

**Video Processing**

```javascript
// Generate video
const jobData = {
  prompt: "A beautiful sunset over mountains",
  duration: 10,
  quality: "1080p",
};

fetch(`${baseUrl}/videos/generate`, {
  method: "POST",
  headers: { ...headers, "Content-Type": "application/json" },
  body: JSON.stringify(jobData),
})
  .then((response) => response.json())
  .then((data) => {
    const jobId = data.data.job_id;
    console.log("Video generation started:", jobId);

    // Poll for status
    const checkStatus = () => {
      fetch(`${baseUrl}/videos/${jobId}/status`, { headers })
        .then((response) => response.json())
        .then((status) => {
          console.log(
            `Status: ${status.data.status} (${status.data.progress}%)`
          );
          if (status.data.status === "processing") {
            setTimeout(checkStatus, 5000); // Check again in 5 seconds
          }
        });
    };
    checkStatus();
  });
```

**System Monitoring**

```javascript
// Get system metrics
fetch(`${baseUrl}/system/metrics`, { headers })
  .then((response) => response.json())
  .then((data) => {
    console.log(`CPU usage: ${data.data.cpu_usage}%`);
    console.log(`Memory usage: ${data.data.memory_usage}%`);
  });

// Get queue status
fetch(`${baseUrl}/system/queue`, { headers })
  .then((response) => response.json())
  .then((data) => console.log(`Jobs in queue: ${data.data.pending_jobs}`));
```

## Support

For API support and questions, please contact:

- Email: api-support@example.com
- Documentation: https://docs.example.com
- Status Page: https://status.example.com

## Webhooks

The T2M API supports webhook notifications for long-running operations like video generation.

### Webhook Configuration

Configure webhook URLs in your account settings or via the API:

```bash
curl -X POST "https://api.example.com/api/v1/webhooks" \
  -H "Authorization: Bearer your-token-here" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://your-app.com/webhooks/t2m",
    "events": ["job.completed", "job.failed"],
    "secret": "your-webhook-secret"
  }'
```

### Webhook Events

| Event           | Description                     |
| --------------- | ------------------------------- |
| `job.started`   | Job processing has begun        |
| `job.progress`  | Job progress update (every 10%) |
| `job.completed` | Job completed successfully      |
| `job.failed`    | Job failed with error           |
| `job.cancelled` | Job was cancelled               |

### Webhook Payload Example

**Job Completed**

```json
{
  "event": "job.completed",
  "timestamp": "2024-01-15T10:35:30Z",
  "data": {
    "job_id": "job_789012",
    "type": "video_generation",
    "status": "completed",
    "result": {
      "file_id": "video_456789",
      "download_url": "https://api.example.com/api/v1/videos/job_789012/download",
      "thumbnail_url": "https://api.example.com/api/v1/videos/job_789012/thumbnail"
    }
  }
}
```

### Webhook Security

Verify webhook authenticity using the signature header:

```python
import hmac
import hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)

# In your webhook handler
signature = request.headers.get('X-T2M-Signature')
if verify_webhook(request.body, signature, webhook_secret):
    # Process webhook
    pass
```

## Advanced Features

### Batch Operations

**Batch File Upload**

```bash
curl -X POST "https://api.example.com/api/v1/files/batch-upload" \
  -H "Authorization: Bearer your-token-here" \
  -F "files=@file1.txt" \
  -F "files=@file2.txt" \
  -F "files=@file3.txt" \
  -F "file_type=document"
```

### Signed URLs for Secure Access

Generate temporary signed URLs for file access without authentication:

```python
# Request signed URL
response = requests.post(f"{base_url}/files/{file_id}/signed-url",
                        headers=headers,
                        json={"expires_in": 3600})  # 1 hour
signed_url = response.json()['data']['url']

# Use signed URL (no auth required)
file_response = requests.get(signed_url)
```

### Streaming and Quality Options

**Video Streaming with Quality Selection**

```bash
# Stream in different qualities
curl "https://api.example.com/api/v1/videos/job_789012/stream?quality=720p" \
  -H "Authorization: Bearer your-token-here"
```

**Thumbnail Sizes**

```bash
# Get different thumbnail sizes
curl "https://api.example.com/api/v1/videos/job_789012/thumbnail?size=large" \
  -H "Authorization: Bearer your-token-here"
```

## Performance Optimization

### Caching

The API implements intelligent caching. Use these endpoints to manage cache:

```bash
# Warm cache for better performance
curl -X POST "https://api.example.com/api/v1/system/cache/warm" \
  -H "Authorization: Bearer your-token-here"

# Invalidate specific cache patterns
curl -X POST "https://api.example.com/api/v1/system/cache/invalidate" \
  -H "Authorization: Bearer your-token-here" \
  -d "pattern=user:123:*"
```

### Request Optimization

- Use pagination for large datasets
- Implement client-side caching for frequently accessed data
- Use appropriate quality settings for streaming
- Batch operations when possible

## Monitoring and Analytics

### System Health Monitoring

```bash
# Check overall system health
curl "https://api.example.com/api/v1/system/health"

# Get detailed performance metrics
curl "https://api.example.com/api/v1/system/performance?hours=24" \
  -H "Authorization: Bearer your-token-here"
```

### File Analytics

Track file usage and performance:

```bash
curl "https://api.example.com/api/v1/files/file_123456/analytics" \
  -H "Authorization: Bearer your-token-here"
```

## Migration Guide

### From v1.0 to v1.1

**Breaking Changes:**

- `GET /files/{id}/info` is now `GET /files/{id}` (consolidated endpoints)
- Error response format now includes `details` field
- Pagination format standardized across all endpoints

**New Features:**

- Webhook support for job notifications
- Batch file operations
- Enhanced error details
- Signed URL support

**Migration Steps:**

1. Update endpoint URLs for file info
2. Update error handling to use new format
3. Implement webhook handlers for better UX
4. Use batch operations for improved performance

## Changelog

### v1.1.0 (2024-01-15)

- Added webhook support
- Introduced batch file operations
- Enhanced error responses with details
- Added signed URL generation
- Improved pagination format
- Added system performance endpoints

### v1.0.0 (2023-12-01)

- Initial API release
- Basic CRUD operations for files
- Video generation capabilities
- Job management system
- System monitoring endpoints
