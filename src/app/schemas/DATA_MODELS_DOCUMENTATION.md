# Data Models & Types Documentation

## Overview

This document provides comprehensive documentation for all data models and types used in the video generation system. It includes TypeScript interfaces, JSON schemas, example responses, and validation rules to help frontend developers understand the API structure and implement proper data handling.

## Table of Contents

1. [Core Data Models](#core-data-models)
2. [API Response Patterns](#api-response-patterns)
3. [Status Enums & States](#status-enums--states)
4. [Example API Responses](#example-api-responses)
5. [Validation Rules](#validation-rules)
6. [Error Handling](#error-handling)

---

## Core Data Models

### Job Models

#### JobStatus Enum
```typescript
enum JobStatus {
  QUEUED = "queued",
  PROCESSING = "processing", 
  COMPLETED = "completed",
  FAILED = "failed",
  CANCELLED = "cancelled"
}
```

#### JobType Enum
```typescript
enum JobType {
  VIDEO_GENERATION = "video_generation",
  BATCH_VIDEO_GENERATION = "batch_video_generation",
  FILE_PROCESSING = "file_processing"
}
```

#### JobPriority Enum
```typescript
enum JobPriority {
  LOW = "low",
  NORMAL = "normal", 
  HIGH = "high",
  URGENT = "urgent"
}
```

#### VideoQuality Enum
```typescript
enum VideoQuality {
  LOW = "low",
  MEDIUM = "medium",
  HIGH = "high", 
  ULTRA = "ultra"
}
```

#### JobConfiguration Interface
```typescript
interface JobConfiguration {
  // Video generation parameters
  topic: string;                    // 1-500 characters
  context: string;                  // 1-2000 characters
  model?: string;                   // AI model to use
  quality: VideoQuality;            // Default: "medium"
  use_rag: boolean;                 // Default: false
  
  // Advanced configuration
  custom_config?: Record<string, any>;
  template_id?: string;
  style_preferences?: Record<string, string>;
  
  // Processing options
  enable_subtitles: boolean;        // Default: true
  enable_thumbnails: boolean;       // Default: true
  output_format: string;            // Default: "mp4"
}
```

#### JobProgress Interface
```typescript
interface JobProgress {
  percentage: number;               // 0.0 to 100.0
  current_stage?: string;           // Current processing stage
  stages_completed: string[];       // List of completed stages
  estimated_completion?: string;    // ISO datetime string
  processing_time_seconds?: number; // Processing time so far
}
```

#### JobError Interface
```typescript
interface JobError {
  error_code: string;
  error_message: string;
  error_details?: Record<string, any>;
  stack_trace?: string;             // For debugging
  retry_count: number;              // Default: 0
  max_retries: number;              // Default: 3
}
```

#### Job Interface
```typescript
interface Job {
  // Basic information
  id: string;                       // UUID
  user_id: string;                  // Clerk user ID
  job_type: JobType;                // Default: "video_generation"
  priority: JobPriority;            // Default: "normal"
  
  // Configuration and status
  configuration: JobConfiguration;
  status: JobStatus;                // Default: "queued"
  progress: JobProgress;
  error?: JobError;
  
  // Timestamps
  created_at: string;               // ISO datetime
  updated_at: string;               // ISO datetime
  started_at?: string;              // ISO datetime
  completed_at?: string;            // ISO datetime
  
  // Batch support
  batch_id?: string;
  parent_job_id?: string;
  
  // Soft delete
  is_deleted: boolean;              // Default: false
  deleted_at?: string;              // ISO datetime
}
```

### Video Models

#### VideoFormat Enum
```typescript
enum VideoFormat {
  MP4 = "mp4",
  AVI = "avi", 
  MOV = "mov",
  WMV = "wmv",
  FLV = "flv",
  WEBM = "webm"
}
```

#### VideoResolution Enum
```typescript
enum VideoResolution {
  SD_480P = "480p",
  HD_720P = "720p",
  FHD_1080P = "1080p", 
  QHD_1440P = "1440p",
  UHD_4K = "4k"
}
```

#### VideoStatus Enum
```typescript
enum VideoStatus {
  PROCESSING = "processing",
  READY = "ready",
  FAILED = "failed",
  DELETED = "deleted"
}
```

#### ThumbnailMetadata Interface
```typescript
interface ThumbnailMetadata {
  id: string;                       // UUID
  filename: string;
  file_path: string;
  file_size: number;                // Bytes
  width: number;                    // Pixels
  height: number;                   // Pixels
  format: string;                   // jpg, png, etc.
  timestamp_seconds: number;        // Video timestamp
  created_at: string;               // ISO datetime
}
```

#### SubtitleTrack Interface
```typescript
interface SubtitleTrack {
  id: string;                       // UUID
  language: string;                 // Language code (e.g., 'en', 'es')
  language_name: string;            // Human-readable name
  filename: string;
  file_path: string;
  file_size: number;                // Bytes
  format: string;                   // srt, vtt, etc.
  is_auto_generated: boolean;       // Default: true
  created_at: string;               // ISO datetime
}
```

#### VideoMetadata Interface
```typescript
interface VideoMetadata {
  // Basic information
  id: string;                       // UUID
  job_id: string;                   // Associated job ID
  user_id: string;                  // Clerk user ID
  
  // File information
  filename: string;
  original_filename?: string;
  file_path: string;
  file_size: number;                // Bytes
  file_hash?: string;               // For integrity checking
  
  // Video properties
  duration_seconds?: number;
  width?: number;                   // Pixels
  height?: number;                  // Pixels
  resolution?: VideoResolution;
  format: VideoFormat;
  status: VideoStatus;              // Default: "processing"
  
  // Associated assets
  thumbnails: ThumbnailMetadata[];
  subtitle_tracks: SubtitleTrack[];
  
  // Metadata
  title?: string;                   // Max 200 characters
  description?: string;             // Max 1000 characters
  tags: string[];
  custom_metadata?: Record<string, any>;
  
  // Timestamps
  created_at: string;               // ISO datetime
  updated_at: string;               // ISO datetime
  processed_at?: string;            // ISO datetime
  
  // Access and sharing
  is_public: boolean;               // Default: false
  download_count: number;           // Default: 0
  view_count: number;               // Default: 0
  
  // Soft delete
  is_deleted: boolean;              // Default: false
  deleted_at?: string;              // ISO datetime
}
```

### File Models

#### FileType Enum
```typescript
enum FileType {
  IMAGE = "image",
  VIDEO = "video",
  AUDIO = "audio", 
  DOCUMENT = "document",
  ARCHIVE = "archive"
}
```

#### FileMetadata Interface
```typescript
interface FileMetadata {
  id: string;                       // File identifier
  filename: string;                 // Stored filename
  original_filename: string;        // Original filename
  file_type: FileType;
  mime_type: string;
  file_size: number;                // Bytes
  checksum: string;                 // File checksum
  created_at: string;               // ISO datetime
  download_url?: string;
  metadata: Record<string, any>;    // File-specific metadata
}
```

### User Models

#### UserStatus Enum
```typescript
enum UserStatus {
  ACTIVE = "active",
  INACTIVE = "inactive",
  SUSPENDED = "suspended", 
  PENDING_VERIFICATION = "pending_verification"
}
```

#### UserRole Enum
```typescript
enum UserRole {
  USER = "user",
  ADMIN = "admin",
  MODERATOR = "moderator"
}
```

#### UserProfile Interface
```typescript
interface UserProfile {
  id: string;                       // Clerk user ID
  username?: string;
  full_name: string;
  email?: string;                   // Primary email
  image_url?: string;               // Profile image URL
  email_verified: boolean;          // Default: false
  created_at: string;               // ISO datetime
  last_sign_in_at?: string;         // ISO datetime
}
```

#### UserPermissions Interface
```typescript
interface UserPermissions {
  user_id: string;
  role: UserRole;                   // Default: "user"
  permissions: string[];
  
  // Video generation permissions
  can_generate_videos: boolean;     // Default: true
  can_upload_files: boolean;        // Default: true
  can_access_premium_features: boolean; // Default: false
  
  // Administrative permissions
  can_view_all_jobs: boolean;       // Default: false
  can_cancel_any_job: boolean;      // Default: false
  can_access_system_metrics: boolean; // Default: false
  
  // Rate limits
  max_concurrent_jobs: number;      // Default: 3
  max_daily_jobs: number;           // Default: 50
  max_file_size_mb: number;         // Default: 100
}
```

### System Models

#### HealthStatus Enum
```typescript
enum HealthStatus {
  HEALTHY = "healthy",
  UNHEALTHY = "unhealthy", 
  DEGRADED = "degraded",
  UNKNOWN = "unknown"
}
```

#### SystemHealth Interface
```typescript
interface SystemHealth {
  status: HealthStatus;
  timestamp: string;                // ISO datetime
  uptime_seconds: number;
  components: Record<string, ComponentHealth>;
  version: string;
  environment: string;              // development/staging/production
}
```

#### ComponentHealth Interface
```typescript
interface ComponentHealth {
  status: string;                   // healthy/unhealthy
  response_time_ms?: number;
  error?: string;
  details?: Record<string, any>;
  last_check?: string;              // ISO datetime
}
```

---

## API Response Patterns

### Standard Response Wrapper
```typescript
interface APIResponse<T> {
  status: "success" | "error" | "warning" | "info";
  message: string;
  data?: T;
  error?: ErrorDetail;
  timestamp: string;                // ISO datetime
  request_id?: string;
}
```

### Paginated Response
```typescript
interface PaginatedResponse<T> {
  items: T[];
  pagination: {
    page: number;                   // Current page (1-based)
    items_per_page: number;         // Items per page
    total_items: number;            // Total items available
    total_pages: number;            // Total pages
    has_next: boolean;              // Has next page
    has_previous: boolean;          // Has previous page
  };
}
```

### Error Detail
```typescript
interface ErrorDetail {
  message: string;                  // Human-readable error message
  code: string;                     // Machine-readable error code
  details?: Record<string, any>;    // Additional error details
  field_errors?: FieldError[];      // Field-level validation errors
  timestamp: string;                // ISO datetime
  request_id?: string;              // Request ID for tracking
}
```

### Field Error
```typescript
interface FieldError {
  field: string;                    // Field name that caused error
  message: string;                  // Error message for field
  code: string;                     // Error code for field
  value?: any;                      // Invalid value that caused error
}
```

---

## Status Enums & States

### Job Status Flow
```
queued → processing → completed
                   → failed
                   → cancelled
```

**Status Descriptions:**
- `queued`: Job is waiting in the queue to be processed
- `processing`: Job is currently being processed
- `completed`: Job finished successfully
- `failed`: Job encountered an error and could not complete
- `cancelled`: Job was cancelled by user or system

### Video Status Flow
```
processing → ready
          → failed
          → deleted
```

**Status Descriptions:**
- `processing`: Video is being generated/processed
- `ready`: Video is ready for download/viewing
- `failed`: Video processing failed
- `deleted`: Video has been deleted (soft delete)

### User Status States
- `active`: User account is active and can use the system
- `inactive`: User account is inactive (not deleted)
- `suspended`: User account is suspended due to violations
- `pending_verification`: User needs to verify their account

### Health Status States
- `healthy`: Component/system is functioning normally
- `degraded`: Component/system is functioning but with reduced performance
- `unhealthy`: Component/system is not functioning properly
- `unknown`: Component/system status cannot be determined

---

## Example API Responses

### Job Creation Response
```json
{
  "status": "success",
  "message": "Job created successfully",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "queued",
    "progress": {
      "percentage": 0.0,
      "current_stage": null,
      "stages_completed": [],
      "estimated_completion": "2024-01-15T10:35:00Z"
    },
    "created_at": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

### Job Status Response (Processing)
```json
{
  "status": "success",
  "message": "Job status retrieved",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "processing",
    "progress": {
      "percentage": 45.5,
      "current_stage": "video_generation",
      "stages_completed": ["content_analysis", "script_generation"],
      "estimated_completion": "2024-01-15T10:33:00Z",
      "processing_time_seconds": 120.5
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:32:00Z",
    "started_at": "2024-01-15T10:30:30Z"
  },
  "timestamp": "2024-01-15T10:32:00Z"
}
```

### Job Status Response (Completed)
```json
{
  "status": "success", 
  "message": "Job completed successfully",
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "completed",
    "progress": {
      "percentage": 100.0,
      "current_stage": "completed",
      "stages_completed": [
        "content_analysis",
        "script_generation", 
        "video_generation",
        "thumbnail_generation",
        "subtitle_generation"
      ],
      "processing_time_seconds": 285.2
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:34:45Z",
    "started_at": "2024-01-15T10:30:30Z",
    "completed_at": "2024-01-15T10:34:45Z"
  },
  "timestamp": "2024-01-15T10:34:45Z"
}
```

### Job Status Response (Failed)
```json
{
  "status": "success",
  "message": "Job status retrieved", 
  "data": {
    "job_id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "failed",
    "progress": {
      "percentage": 25.0,
      "current_stage": "script_generation",
      "stages_completed": ["content_analysis"],
      "processing_time_seconds": 45.8
    },
    "error": {
      "error_code": "CONTENT_GENERATION_FAILED",
      "error_message": "Failed to generate content for the given topic",
      "error_details": {
        "reason": "Topic too vague or inappropriate",
        "suggestions": ["Be more specific", "Provide more context"]
      },
      "retry_count": 1,
      "max_retries": 3
    },
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:31:15Z",
    "started_at": "2024-01-15T10:30:30Z",
    "completed_at": "2024-01-15T10:31:15Z"
  },
  "timestamp": "2024-01-15T10:31:15Z"
}
```

### Job List Response (Paginated)
```json
{
  "status": "success",
  "message": "Jobs retrieved successfully",
  "data": {
    "items": [
      {
        "job_id": "550e8400-e29b-41d4-a716-446655440000",
        "status": "completed",
        "progress": {
          "percentage": 100.0,
          "current_stage": "completed"
        },
        "created_at": "2024-01-15T10:30:00Z",
        "estimated_completion": null
      },
      {
        "job_id": "550e8400-e29b-41d4-a716-446655440001", 
        "status": "processing",
        "progress": {
          "percentage": 65.0,
          "current_stage": "video_generation"
        },
        "created_at": "2024-01-15T10:25:00Z",
        "estimated_completion": "2024-01-15T10:35:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "items_per_page": 10,
      "total_items": 25,
      "total_pages": 3,
      "has_next": true,
      "has_previous": false
    }
  },
  "timestamp": "2024-01-15T10:35:00Z"
}
```

### Video Metadata Response
```json
{
  "status": "success",
  "message": "Video metadata retrieved",
  "data": {
    "video_id": "550e8400-e29b-41d4-a716-446655440000",
    "job_id": "job_550e8400-e29b-41d4-a716-446655440000",
    "filename": "pythagorean_theorem_video.mp4",
    "file_size": 15728640,
    "file_size_mb": 15.0,
    "duration_seconds": 120.5,
    "duration_formatted": "02:00",
    "width": 1920,
    "height": 1080,
    "resolution": "1080p",
    "format": "mp4",
    "status": "ready",
    "title": "Pythagorean Theorem Explanation",
    "description": "Educational video explaining the Pythagorean theorem",
    "download_url": "https://api.example.com/videos/download/550e8400-e29b-41d4-a716-446655440000",
    "thumbnail_urls": [
      "https://api.example.com/thumbnails/550e8400-e29b-41d4-a716-446655440000_1.jpg",
      "https://api.example.com/thumbnails/550e8400-e29b-41d4-a716-446655440000_2.jpg"
    ],
    "subtitle_tracks": [
      {
        "id": "sub_123",
        "language": "en",
        "language_name": "English",
        "filename": "subtitles_en.srt",
        "format": "srt",
        "is_auto_generated": true
      }
    ],
    "created_at": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:35:00Z"
}
```

### System Health Response
```json
{
  "status": "success",
  "message": "System health check completed",
  "data": {
    "status": "healthy",
    "timestamp": "2024-01-15T10:30:00Z",
    "uptime_seconds": 86400,
    "components": {
      "redis": {
        "status": "healthy",
        "response_time_ms": 2.5,
        "details": {
          "connected_clients": 5,
          "used_memory": "10MB"
        }
      },
      "authentication": {
        "status": "healthy",
        "details": {
          "initialized": true
        }
      },
      "job_queue": {
        "status": "healthy", 
        "details": {
          "queue_length": 15
        }
      }
    },
    "version": "1.0.0",
    "environment": "production"
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### System Metrics Response
```json
{
  "status": "success",
  "message": "System metrics retrieved",
  "data": {
    "timestamp": "2024-01-15T10:30:00Z",
    "system_resources": {
      "cpu_percent": 45.2,
      "memory_total_gb": 16.0,
      "memory_used_gb": 8.5,
      "memory_percent": 53.1,
      "disk_total_gb": 500.0,
      "disk_used_gb": 125.0,
      "disk_percent": 25.0
    },
    "redis_metrics": {
      "memory_used_mb": 128.5,
      "connected_clients": 10,
      "commands_processed": 1500000,
      "keyspace_hits": 950000,
      "keyspace_misses": 50000
    },
    "job_metrics": {
      "queue_length": 25,
      "jobs_by_status": {
        "queued": 25,
        "processing": 3,
        "completed": 1250,
        "failed": 15
      },
      "processing_metrics": {
        "avg_processing_time_minutes": 4.5,
        "success_rate_percent": 98.8
      }
    },
    "performance_metrics": {
      "error_rate_percent": 1.2,
      "avg_response_time_ms": 150.0,
      "requests_per_minute": 45.0
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

---

## Validation Rules

### Job Configuration Validation
- `topic`: Required, 1-500 characters
- `context`: Required, 1-2000 characters  
- `model`: Optional string
- `quality`: Must be one of: "low", "medium", "high", "ultra"
- `use_rag`: Boolean, default false
- `enable_subtitles`: Boolean, default true
- `enable_thumbnails`: Boolean, default true
- `output_format`: String, default "mp4"

### File Upload Validation
- `file_size`: Maximum varies by user role (100MB default, 500MB admin)
- `file_type`: Must be supported MIME type
- `filename`: No path traversal characters (/, \, ..)
- `tags`: Maximum 10 tags per file
- `subdirectory`: No path traversal characters

### Pagination Validation
- `page`: Minimum 1
- `items_per_page`: 1-100 range
- `sort_order`: Must be "asc" or "desc"

### User Permissions Validation
- `max_concurrent_jobs`: 1-10 range (role-dependent)
- `max_daily_jobs`: 1-1000 range (role-dependent)
- `max_file_size_mb`: 1-500 range (role-dependent)

---

## Error Handling

### Common Error Codes
```typescript
enum ErrorCode {
  // Validation errors
  VALIDATION_ERROR = "VALIDATION_ERROR",
  INVALID_INPUT = "INVALID_INPUT", 
  MISSING_FIELD = "MISSING_FIELD",
  
  // Authentication errors
  UNAUTHORIZED = "UNAUTHORIZED",
  FORBIDDEN = "FORBIDDEN",
  TOKEN_EXPIRED = "TOKEN_EXPIRED",
  
  // Resource errors
  NOT_FOUND = "NOT_FOUND",
  ALREADY_EXISTS = "ALREADY_EXISTS",
  CONFLICT = "CONFLICT",
  
  // Rate limiting
  RATE_LIMIT_EXCEEDED = "RATE_LIMIT_EXCEEDED",
  QUOTA_EXCEEDED = "QUOTA_EXCEEDED",
  
  // System errors
  INTERNAL_ERROR = "INTERNAL_ERROR",
  SERVICE_UNAVAILABLE = "SERVICE_UNAVAILABLE",
  
  // Business logic errors
  JOB_NOT_FOUND = "JOB_NOT_FOUND",
  JOB_ALREADY_COMPLETED = "JOB_ALREADY_COMPLETED",
  JOB_CANNOT_BE_CANCELLED = "JOB_CANNOT_BE_CANCELLED",
  VIDEO_NOT_READY = "VIDEO_NOT_READY",
  FILE_TOO_LARGE = "FILE_TOO_LARGE",
  UNSUPPORTED_FILE_TYPE = "UNSUPPORTED_FILE_TYPE"
}
```

### Error Response Examples

#### Validation Error (422)
```json
{
  "status": "error",
  "message": "Validation failed",
  "error": {
    "message": "The request contains invalid data",
    "code": "VALIDATION_ERROR",
    "field_errors": [
      {
        "field": "topic",
        "message": "Topic is required",
        "code": "MISSING_FIELD"
      },
      {
        "field": "context", 
        "message": "Context must be between 1 and 2000 characters",
        "code": "INVALID_LENGTH",
        "value": ""
      }
    ],
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

#### Not Found Error (404)
```json
{
  "status": "error",
  "message": "Job not found",
  "error": {
    "message": "The requested job was not found",
    "code": "JOB_NOT_FOUND",
    "details": {
      "job_id": "550e8400-e29b-41d4-a716-446655440000"
    },
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

#### Rate Limit Error (429)
```json
{
  "status": "error",
  "message": "Rate limit exceeded",
  "error": {
    "message": "Too many requests. Please try again later.",
    "code": "RATE_LIMIT_EXCEEDED",
    "details": {
      "retry_after": 60,
      "limit": 100,
      "remaining": 0,
      "reset_at": "2024-01-15T11:00:00Z"
    },
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

#### Internal Server Error (500)
```json
{
  "status": "error",
  "message": "Internal server error",
  "error": {
    "message": "An unexpected error occurred. Please try again later.",
    "code": "INTERNAL_ERROR",
    "timestamp": "2024-01-15T10:30:00Z"
  },
  "timestamp": "2024-01-15T10:30:00Z",
  "request_id": "req_123456789"
}
```

---

## Frontend Implementation Notes

### State Management Recommendations

1. **Job Status Polling**: Poll job status every 2-5 seconds for active jobs (queued/processing)
2. **Error Handling**: Always check the `status` field and handle `error` objects appropriately
3. **Pagination**: Use the `pagination` metadata to implement proper pagination controls
4. **File Downloads**: Check `video.status === "ready"` before showing download links
5. **Real-time Updates**: Consider WebSocket connections for real-time job progress updates

### UI Display Guidelines

1. **Job Status Icons**:
   - `queued`: Clock/waiting icon
   - `processing`: Spinner/progress icon  
   - `completed`: Checkmark/success icon
   - `failed`: X/error icon
   - `cancelled`: Stop/cancelled icon

2. **Progress Display**: Use `progress.percentage` for progress bars and `progress.current_stage` for status text

3. **Error Messages**: Display `error.error_message` to users, log `error.error_code` for debugging

4. **File Sizes**: Use `file_size_mb` for user-friendly display, `file_size` for precise calculations

5. **Timestamps**: All timestamps are in ISO format, convert to local time for display

This documentation provides a comprehensive reference for frontend developers to understand the data structures and implement proper handling of all system states and responses.