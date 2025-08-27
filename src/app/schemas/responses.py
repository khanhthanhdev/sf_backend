"""
API response schemas for video generation system.

This module defines Pydantic schemas for API responses, ensuring consistent
response formats and comprehensive API documentation.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict

from ..models.job import JobStatus, JobPriority, JobProgress, JobError, JobMetrics
from ..models.video import VideoStatus, VideoFormat, VideoResolution
from ..models.system import HealthStatus, ServiceHealth, SystemMetrics
from ..models.common import PaginationMeta


class JobResponse(BaseModel):
    """
    Response schema for job creation and basic job information.
    
    Returns essential job information after creation or when querying job details.
    """
    
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    priority: JobPriority = Field(..., description="Job priority level")
    progress: JobProgress = Field(..., description="Job progress information")
    created_at: datetime = Field(..., description="Job creation timestamp")
    estimated_completion: Optional[datetime] = Field(
        None, 
        description="Estimated completion time"
    )
    batch_id: Optional[str] = Field(
        None, 
        description="Batch ID if job is part of a batch"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "queued",
                "priority": "normal",
                "progress": {
                    "percentage": 0.0,
                    "current_stage": None,
                    "stages_completed": [],
                    "estimated_completion": None,
                    "processing_time_seconds": None
                },
                "created_at": "2024-01-15T10:30:00Z",
                "estimated_completion": "2024-01-15T10:35:00Z",
                "batch_id": None
            }
        }
    )


class JobStatusResponse(BaseModel):
    """
    Response schema for detailed job status queries.
    
    Provides comprehensive information about job status, progress, and any errors.
    """
    
    job_id: str = Field(..., description="Unique job identifier")
    user_id: str = Field(..., description="User ID who created the job")
    status: JobStatus = Field(..., description="Current job status")
    priority: JobPriority = Field(..., description="Job priority level")
    progress: JobProgress = Field(..., description="Detailed progress information")
    
    # Configuration summary
    topic: str = Field(..., description="Video topic")
    quality: str = Field(..., description="Video quality setting")
    
    # Error information
    error: Optional[JobError] = Field(None, description="Error details if job failed")
    
    # Performance metrics
    metrics: Optional[JobMetrics] = Field(None, description="Job performance metrics")
    
    # Timestamps
    created_at: datetime = Field(..., description="Job creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    started_at: Optional[datetime] = Field(None, description="Job start timestamp")
    completed_at: Optional[datetime] = Field(None, description="Job completion timestamp")
    
    # Batch information
    batch_id: Optional[str] = Field(None, description="Batch ID if part of batch")
    
    # Video information (if completed)
    video_id: Optional[str] = Field(None, description="Generated video ID")
    download_url: Optional[str] = Field(None, description="Video download URL")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_2NiWoZK2iKDvEFEHaakTrHVfcrq",
                "status": "processing",
                "priority": "normal",
                "progress": {
                    "percentage": 45.0,
                    "current_stage": "video_generation",
                    "stages_completed": ["content_planning", "script_generation"],
                    "estimated_completion": "2024-01-15T10:35:00Z",
                    "processing_time_seconds": 120.5
                },
                "topic": "Pythagorean Theorem",
                "quality": "medium",
                "error": None,
                "metrics": {
                    "queue_time_seconds": 15.2,
                    "processing_time_seconds": 120.5,
                    "cpu_usage_percent": 75.0,
                    "memory_usage_mb": 512.0
                },
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:32:00Z",
                "started_at": "2024-01-15T10:30:15Z",
                "completed_at": None,
                "batch_id": None,
                "video_id": None,
                "download_url": None
            }
        }
    )


class JobListResponse(BaseModel):
    """
    Response schema for paginated job lists.
    
    Returns a paginated list of jobs with metadata.
    """
    
    jobs: List[JobResponse] = Field(..., description="List of jobs")
    pagination: PaginationMeta = Field(..., description="Pagination information")
    filters_applied: Optional[Dict[str, Any]] = Field(
        None, 
        description="Summary of applied filters"
    )
    total_by_status: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of jobs by status"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jobs": [
                    {
                        "job_id": "550e8400-e29b-41d4-a716-446655440000",
                        "status": "completed",
                        "priority": "normal",
                        "progress": {"percentage": 100.0},
                        "created_at": "2024-01-15T10:30:00Z"
                    }
                ],
                "pagination": {
                    "page": 1,
                    "items_per_page": 10,
                    "total_items": 25,
                    "total_pages": 3,
                    "has_next": True,
                    "has_previous": False
                },
                "filters_applied": {
                    "status": ["completed", "processing"],
                    "created_after": "2024-01-01T00:00:00Z"
                },
                "total_by_status": {
                    "queued": 5,
                    "processing": 3,
                    "completed": 15,
                    "failed": 2
                }
            }
        }
    )


class BatchJobResponse(BaseModel):
    """
    Response schema for batch job operations.
    
    Returns information about a batch of jobs created together.
    """
    
    batch_id: str = Field(..., description="Unique batch identifier")
    job_ids: List[str] = Field(..., description="List of created job IDs")
    total_jobs: int = Field(..., ge=1, description="Total number of jobs in batch")
    batch_priority: JobPriority = Field(..., description="Priority for all jobs in batch")
    batch_name: Optional[str] = Field(None, description="Optional batch name")
    created_at: datetime = Field(..., description="Batch creation timestamp")
    estimated_completion: Optional[datetime] = Field(
        None, 
        description="Estimated completion time for entire batch"
    )
    
    # Status summary
    status_summary: Dict[str, int] = Field(
        default_factory=dict,
        description="Count of jobs by status in this batch"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "batch_id": "batch_550e8400-e29b-41d4-a716-446655440000",
                "job_ids": [
                    "job_550e8400-e29b-41d4-a716-446655440001",
                    "job_550e8400-e29b-41d4-a716-446655440002"
                ],
                "total_jobs": 2,
                "batch_priority": "normal",
                "batch_name": "Mathematics Series - Part 1",
                "created_at": "2024-01-15T10:30:00Z",
                "estimated_completion": "2024-01-15T10:45:00Z",
                "status_summary": {
                    "queued": 2,
                    "processing": 0,
                    "completed": 0,
                    "failed": 0
                }
            }
        }
    )


class VideoDownloadResponse(BaseModel):
    """
    Response schema for video download information.
    
    Provides download URLs and video metadata for completed videos.
    """
    
    video_id: str = Field(..., description="Video identifier")
    job_id: str = Field(..., description="Associated job ID")
    filename: str = Field(..., description="Video filename")
    file_size: int = Field(..., description="File size in bytes")
    file_size_mb: float = Field(..., description="File size in megabytes")
    
    # Video properties
    duration_seconds: Optional[float] = Field(None, description="Video duration")
    duration_formatted: Optional[str] = Field(None, description="Formatted duration (MM:SS)")
    resolution: Optional[VideoResolution] = Field(None, description="Video resolution")
    format: VideoFormat = Field(..., description="Video format")
    
    # Download information
    download_url: str = Field(..., description="Direct download URL")
    streaming_url: Optional[str] = Field(None, description="Streaming URL if available")
    expires_at: Optional[datetime] = Field(None, description="URL expiration time")
    
    # Additional assets
    thumbnail_urls: List[str] = Field(
        default_factory=list, 
        description="Thumbnail image URLs"
    )
    subtitle_urls: List[Dict[str, str]] = Field(
        default_factory=list,
        description="Subtitle file URLs with language info"
    )
    
    # Metadata
    created_at: datetime = Field(..., description="Video creation timestamp")
    download_count: int = Field(default=0, description="Number of times downloaded")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "video_id": "video_550e8400-e29b-41d4-a716-446655440000",
                "job_id": "job_550e8400-e29b-41d4-a716-446655440000",
                "filename": "pythagorean_theorem_video.mp4",
                "file_size": 15728640,
                "file_size_mb": 15.0,
                "duration_seconds": 120.5,
                "duration_formatted": "02:00",
                "resolution": "1080p",
                "format": "mp4",
                "download_url": "https://api.example.com/videos/download/video_550e8400-e29b-41d4-a716-446655440000",
                "streaming_url": "https://stream.example.com/video_550e8400-e29b-41d4-a716-446655440000",
                "expires_at": "2024-01-15T22:30:00Z",
                "thumbnail_urls": [
                    "https://api.example.com/thumbnails/thumb_001.jpg",
                    "https://api.example.com/thumbnails/thumb_002.jpg"
                ],
                "subtitle_urls": [
                    {
                        "language": "en",
                        "language_name": "English",
                        "url": "https://api.example.com/subtitles/video_en.srt"
                    }
                ],
                "created_at": "2024-01-15T10:35:00Z",
                "download_count": 3
            }
        }
    )


class VideoMetadataResponse(BaseModel):
    """
    Response schema for detailed video metadata.
    
    Provides comprehensive information about a generated video.
    """
    
    video_id: str = Field(..., description="Video identifier")
    job_id: str = Field(..., description="Associated job ID")
    user_id: str = Field(..., description="User who created the video")
    
    # File information
    filename: str = Field(..., description="Video filename")
    file_size: int = Field(..., description="File size in bytes")
    file_size_mb: float = Field(..., description="File size in megabytes")
    file_hash: Optional[str] = Field(None, description="File integrity hash")
    
    # Video properties
    duration_seconds: Optional[float] = Field(None, description="Video duration")
    width: Optional[int] = Field(None, description="Video width in pixels")
    height: Optional[int] = Field(None, description="Video height in pixels")
    resolution: Optional[VideoResolution] = Field(None, description="Video resolution")
    format: VideoFormat = Field(..., description="Video format")
    aspect_ratio: Optional[str] = Field(None, description="Video aspect ratio")
    
    # Status and processing
    status: VideoStatus = Field(..., description="Video processing status")
    
    # Content metadata
    title: Optional[str] = Field(None, description="Video title")
    description: Optional[str] = Field(None, description="Video description")
    tags: List[str] = Field(default_factory=list, description="Video tags")
    
    # Quality metrics
    bitrate_kbps: Optional[int] = Field(None, description="Video bitrate")
    frame_rate: Optional[float] = Field(None, description="Video frame rate")
    codec: Optional[str] = Field(None, description="Video codec")
    
    # Processing information
    processing_time_seconds: Optional[float] = Field(
        None, 
        description="Total processing time"
    )
    
    # Assets
    thumbnail_count: int = Field(default=0, description="Number of thumbnails")
    subtitle_count: int = Field(default=0, description="Number of subtitle tracks")
    
    # Access information
    is_public: bool = Field(default=False, description="Whether video is public")
    download_count: int = Field(default=0, description="Download count")
    view_count: int = Field(default=0, description="View count")
    
    # Timestamps
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: datetime = Field(..., description="Last update timestamp")
    processed_at: Optional[datetime] = Field(None, description="Processing completion timestamp")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "video_id": "video_550e8400-e29b-41d4-a716-446655440000",
                "job_id": "job_550e8400-e29b-41d4-a716-446655440000",
                "user_id": "user_2NiWoZK2iKDvEFEHaakTrHVfcrq",
                "filename": "pythagorean_theorem_video.mp4",
                "file_size": 15728640,
                "file_size_mb": 15.0,
                "duration_seconds": 120.5,
                "width": 1920,
                "height": 1080,
                "resolution": "1080p",
                "format": "mp4",
                "aspect_ratio": "16:9",
                "status": "ready",
                "title": "Understanding the Pythagorean Theorem",
                "description": "Educational video explaining the Pythagorean theorem",
                "tags": ["mathematics", "geometry", "education"],
                "bitrate_kbps": 2500,
                "frame_rate": 30.0,
                "codec": "h264",
                "processing_time_seconds": 180.5,
                "thumbnail_count": 3,
                "subtitle_count": 1,
                "is_public": False,
                "download_count": 5,
                "view_count": 12,
                "created_at": "2024-01-15T10:30:00Z",
                "updated_at": "2024-01-15T10:35:00Z",
                "processed_at": "2024-01-15T10:35:00Z"
            }
        }
    )


class SystemHealthResponse(BaseModel):
    """
    Response schema for system health checks.
    
    Provides information about the health of various system components.
    """
    
    overall_status: HealthStatus = Field(..., description="Overall system health status")
    timestamp: datetime = Field(..., description="Health check timestamp")
    version: str = Field(..., description="Application version")
    uptime_seconds: float = Field(..., description="System uptime in seconds")
    
    # Component health
    services: List[ServiceHealth] = Field(..., description="Individual service health status")
    
    # System metrics summary
    queue_length: int = Field(..., description="Current job queue length")
    active_jobs: int = Field(..., description="Number of active jobs")
    completed_jobs_24h: int = Field(..., description="Jobs completed in last 24 hours")
    failed_jobs_24h: int = Field(..., description="Jobs failed in last 24 hours")
    
    # Resource usage
    cpu_usage_percent: Optional[float] = Field(None, description="CPU usage percentage")
    memory_usage_percent: Optional[float] = Field(None, description="Memory usage percentage")
    disk_usage_percent: Optional[float] = Field(None, description="Disk usage percentage")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "overall_status": "healthy",
                "timestamp": "2024-01-15T10:30:00Z",
                "version": "1.0.0",
                "uptime_seconds": 86400.0,
                "services": [
                    {
                        "name": "redis",
                        "status": "healthy",
                        "response_time_ms": 2.5,
                        "last_check": "2024-01-15T10:30:00Z"
                    },
                    {
                        "name": "queue",
                        "status": "healthy",
                        "response_time_ms": 1.2,
                        "last_check": "2024-01-15T10:30:00Z"
                    }
                ],
                "queue_length": 5,
                "active_jobs": 3,
                "completed_jobs_24h": 150,
                "failed_jobs_24h": 2,
                "cpu_usage_percent": 45.2,
                "memory_usage_percent": 67.8,
                "disk_usage_percent": 23.1
            }
        }
    )


class SystemMetricsResponse(BaseModel):
    """
    Response schema for detailed system metrics.
    
    Provides comprehensive system performance and usage metrics.
    """
    
    timestamp: datetime = Field(..., description="Metrics collection timestamp")
    time_range_hours: int = Field(..., description="Time range for metrics in hours")
    
    # Job metrics
    job_metrics: Dict[str, Any] = Field(..., description="Job processing metrics")
    
    # Performance metrics
    performance_metrics: Dict[str, Any] = Field(..., description="System performance metrics")
    
    # Resource usage
    resource_usage: Dict[str, Any] = Field(..., description="Resource usage metrics")
    
    # Error rates
    error_rates: Dict[str, float] = Field(..., description="Error rates by category")
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": "2024-01-15T10:30:00Z",
                "time_range_hours": 24,
                "job_metrics": {
                    "total_jobs": 150,
                    "completed_jobs": 145,
                    "failed_jobs": 3,
                    "cancelled_jobs": 2,
                    "average_processing_time_seconds": 180.5,
                    "jobs_per_hour": 6.25
                },
                "performance_metrics": {
                    "average_response_time_ms": 125.5,
                    "p95_response_time_ms": 250.0,
                    "requests_per_second": 15.2,
                    "cache_hit_rate_percent": 85.3
                },
                "resource_usage": {
                    "cpu_usage_percent": 45.2,
                    "memory_usage_percent": 67.8,
                    "disk_usage_percent": 23.1,
                    "network_io_mbps": 12.5
                },
                "error_rates": {
                    "validation_errors": 0.02,
                    "system_errors": 0.001,
                    "timeout_errors": 0.005
                }
            }
        }
    )