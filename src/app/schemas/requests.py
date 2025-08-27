"""
API request schemas for video generation system.

This module defines Pydantic schemas for validating incoming API requests,
including video generation requests, job management, and file uploads.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator, ConfigDict
from enum import Enum

from ..models.job import VideoQuality, JobPriority, JobStatus


class VideoGenerationRequest(BaseModel):
    """
    Request schema for video generation endpoint.
    
    This schema validates and documents the required and optional parameters
    for creating a new video generation job.
    """
    
    # Required fields
    topic: str = Field(
        ..., 
        min_length=1, 
        max_length=500,
        description="Video topic or title",
        example="Pythagorean Theorem"
    )
    context: str = Field(
        ..., 
        min_length=1, 
        max_length=2000,
        description="Detailed context or description for the video content",
        example="Explain the mathematical proof with visual demonstration and real-world applications"
    )
    
    # Optional configuration
    model: Optional[str] = Field(
        None,
        description="AI model to use for video generation",
        example="gemini/gemini-2.5-flash-preview-04-17"
    )
    quality: VideoQuality = Field(
        default=VideoQuality.MEDIUM,
        description="Video quality setting"
    )
    use_rag: bool = Field(
        default=False,
        description="Whether to use RAG (Retrieval-Augmented Generation) for enhanced content"
    )
    
    # Advanced options
    priority: JobPriority = Field(
        default=JobPriority.NORMAL,
        description="Job processing priority"
    )
    enable_subtitles: bool = Field(
        default=True,
        description="Generate subtitles for the video"
    )
    enable_thumbnails: bool = Field(
        default=True,
        description="Generate thumbnail images"
    )
    output_format: str = Field(
        default="mp4",
        pattern="^(mp4|avi|mov|webm)$",
        description="Output video format"
    )
    
    # Custom configuration
    custom_config: Optional[Dict[str, Any]] = Field(
        None,
        description="Additional custom configuration parameters"
    )
    template_id: Optional[str] = Field(
        None,
        description="Template ID to use for video generation"
    )
    style_preferences: Optional[Dict[str, str]] = Field(
        None,
        description="Style preferences for video generation"
    )
    
    # Metadata
    title: Optional[str] = Field(
        None,
        max_length=200,
        description="Custom title for the generated video"
    )
    description: Optional[str] = Field(
        None,
        max_length=1000,
        description="Custom description for the generated video"
    )
    tags: List[str] = Field(
        default_factory=list,
        max_items=10,
        description="Tags to associate with the video"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "topic": "Pythagorean Theorem",
                "context": "Explain the mathematical proof with visual demonstration, including the formula a² + b² = c² and show how it applies to right triangles. Include real-world examples like construction and navigation.",
                "model": "gemini/gemini-2.5-flash-preview-04-17",
                "quality": "medium",
                "use_rag": True,
                "priority": "normal",
                "enable_subtitles": True,
                "enable_thumbnails": True,
                "output_format": "mp4",
                "title": "Understanding the Pythagorean Theorem",
                "description": "Educational video explaining the Pythagorean theorem with visual proofs",
                "tags": ["mathematics", "geometry", "education", "theorem"]
            }
        }
    )
    
    @validator("topic")
    def validate_topic(cls, v):
        """Validate topic is not empty and contains meaningful content."""
        if not v or v.strip() == "":
            raise ValueError("Topic cannot be empty")
        if len(v.strip()) < 3:
            raise ValueError("Topic must be at least 3 characters long")
        return v.strip()
    
    @validator("context")
    def validate_context(cls, v):
        """Validate context provides sufficient detail."""
        if not v or v.strip() == "":
            raise ValueError("Context cannot be empty")
        if len(v.strip()) < 10:
            raise ValueError("Context must be at least 10 characters long")
        return v.strip()
    
    @validator("tags")
    def validate_tags(cls, v):
        """Validate tags are unique and properly formatted."""
        if not v:
            return v
        
        # Remove duplicates and empty tags
        unique_tags = []
        for tag in v:
            tag = tag.strip().lower()
            if tag and tag not in unique_tags:
                unique_tags.append(tag)
        
        if len(unique_tags) > 10:
            raise ValueError("Maximum 10 tags allowed")
        
        return unique_tags
    
    @validator("custom_config")
    def validate_custom_config(cls, v):
        """Validate custom configuration doesn't contain sensitive data."""
        if not v:
            return v
        
        # Check for potentially sensitive keys
        sensitive_keys = ["password", "secret", "key", "token", "credential"]
        for key in v.keys():
            if any(sensitive in key.lower() for sensitive in sensitive_keys):
                raise ValueError(f"Custom config cannot contain sensitive key: {key}")
        
        return v


class BatchVideoGenerationRequest(BaseModel):
    """
    Request schema for batch video generation.
    
    Allows creating multiple video generation jobs in a single request.
    """
    
    jobs: List[VideoGenerationRequest] = Field(
        ...,
        min_items=1,
        max_items=50,
        description="List of video generation requests"
    )
    batch_priority: JobPriority = Field(
        default=JobPriority.NORMAL,
        description="Priority for all jobs in the batch"
    )
    batch_name: Optional[str] = Field(
        None,
        max_length=100,
        description="Optional name for the batch"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "jobs": [
                    {
                        "topic": "Pythagorean Theorem",
                        "context": "Mathematical proof with visual demonstration",
                        "quality": "medium"
                    },
                    {
                        "topic": "Quadratic Formula",
                        "context": "Solving quadratic equations step by step",
                        "quality": "medium"
                    }
                ],
                "batch_priority": "normal",
                "batch_name": "Mathematics Series - Part 1"
            }
        }
    )
    
    @validator("jobs")
    def validate_jobs_count(cls, v):
        """Validate number of jobs in batch."""
        if len(v) > 50:
            raise ValueError("Maximum 50 jobs allowed per batch")
        if len(v) == 0:
            raise ValueError("At least 1 job required in batch")
        return v
    
    @validator("batch_name")
    def validate_batch_name(cls, v):
        """Validate batch name if provided."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) < 3:
                raise ValueError("Batch name must be at least 3 characters long")
        return v


class JobCancelRequest(BaseModel):
    """Request schema for job cancellation."""
    
    reason: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional reason for cancellation"
    )
    force: bool = Field(
        default=False,
        description="Force cancellation even if job is in critical stage"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "reason": "User requested cancellation",
                "force": False
            }
        }
    )


class JobFilterRequest(BaseModel):
    """Request schema for filtering jobs."""
    
    status: Optional[List[JobStatus]] = Field(
        None,
        description="Filter by job status"
    )
    priority: Optional[List[JobPriority]] = Field(
        None,
        description="Filter by job priority"
    )
    created_after: Optional[datetime] = Field(
        None,
        description="Filter jobs created after this date"
    )
    created_before: Optional[datetime] = Field(
        None,
        description="Filter jobs created before this date"
    )
    search: Optional[str] = Field(
        None,
        max_length=100,
        description="Search in job topic and context"
    )
    batch_id: Optional[str] = Field(
        None,
        description="Filter by batch ID"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "status": ["queued", "processing"],
                "priority": ["normal", "high"],
                "created_after": "2024-01-01T00:00:00Z",
                "search": "mathematics",
                "batch_id": "batch_123"
            }
        }
    )
    
    @validator("created_before")
    def validate_date_range(cls, v, values):
        """Validate date range is logical."""
        created_after = values.get("created_after")
        if created_after and v and v <= created_after:
            raise ValueError("created_before must be after created_after")
        return v
    
    @validator("search")
    def validate_search(cls, v):
        """Validate search query."""
        if v is not None:
            v = v.strip()
            if len(v) == 0:
                return None
            if len(v) < 2:
                raise ValueError("Search query must be at least 2 characters long")
        return v


class FileUploadRequest(BaseModel):
    """Request schema for file upload operations."""
    
    file_type: str = Field(
        ...,
        description="Type of file being uploaded",
        example="video"
    )
    filename: str = Field(
        ...,
        max_length=255,
        description="Original filename"
    )
    content_type: str = Field(
        ...,
        description="MIME type of the file"
    )
    file_size: int = Field(
        ...,
        gt=0,
        le=100 * 1024 * 1024,  # 100MB limit
        description="File size in bytes"
    )
    description: Optional[str] = Field(
        None,
        max_length=500,
        description="Optional file description"
    )
    tags: List[str] = Field(
        default_factory=list,
        max_items=5,
        description="File tags"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file_type": "video",
                "filename": "sample_video.mp4",
                "content_type": "video/mp4",
                "file_size": 15728640,
                "description": "Sample video for processing",
                "tags": ["sample", "test"]
            }
        }
    )
    
    @validator("filename")
    def validate_filename(cls, v):
        """Validate filename is safe and has proper extension."""
        import re
        
        # Remove path components for security
        v = v.split("/")[-1].split("\\")[-1]
        
        # Check for valid characters
        if not re.match(r'^[a-zA-Z0-9._-]+$', v):
            raise ValueError("Filename contains invalid characters")
        
        # Check length
        if len(v) > 255:
            raise ValueError("Filename too long")
        
        return v
    
    @validator("content_type")
    def validate_content_type(cls, v):
        """Validate content type is allowed."""
        allowed_types = [
            "video/mp4", "video/avi", "video/mov", "video/webm",
            "image/jpeg", "image/png", "image/gif",
            "text/plain", "application/json"
        ]
        
        if v not in allowed_types:
            raise ValueError(f"Content type {v} not allowed")
        
        return v


class UserPreferencesRequest(BaseModel):
    """Request schema for user preferences."""
    
    default_quality: VideoQuality = Field(
        default=VideoQuality.MEDIUM,
        description="Default video quality preference"
    )
    default_format: str = Field(
        default="mp4",
        pattern="^(mp4|avi|mov|webm)$",
        description="Default output format"
    )
    enable_notifications: bool = Field(
        default=True,
        description="Enable job completion notifications"
    )
    auto_generate_thumbnails: bool = Field(
        default=True,
        description="Automatically generate thumbnails"
    )
    auto_generate_subtitles: bool = Field(
        default=True,
        description="Automatically generate subtitles"
    )
    preferred_language: str = Field(
        default="en",
        pattern="^[a-z]{2}$",
        description="Preferred language code"
    )
    
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "default_quality": "medium",
                "default_format": "mp4",
                "enable_notifications": True,
                "auto_generate_thumbnails": True,
                "auto_generate_subtitles": True,
                "preferred_language": "en"
            }
        }
    )