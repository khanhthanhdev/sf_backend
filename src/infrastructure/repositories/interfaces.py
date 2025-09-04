"""
Repository interfaces for the domain layer.

This module defines abstract base classes for repositories that provide
data access abstraction for domain entities. Following the Repository pattern,
these interfaces define the contract for data operations without coupling
to specific persistence technologies.
"""

from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from ...domain import Result
from ...domain.entities import Video, User, Job, File
from ...domain.value_objects import (
    VideoId, UserId, JobId, FileId, VideoStatus, JobStatus, 
    JobPriority, VideoTopic, FileSize
)

# Type variables for generic repository
T = TypeVar('T')


class PaginationParams:
    """Parameters for pagination."""
    
    def __init__(
        self,
        page: int = 1,
        size: int = 20,
        sort_by: Optional[str] = None,
        sort_order: str = "asc"
    ):
        if page < 1:
            raise ValueError("Page must be >= 1")
        if size < 1 or size > 100:
            raise ValueError("Size must be between 1 and 100")
        if sort_order not in ["asc", "desc"]:
            raise ValueError("Sort order must be 'asc' or 'desc'")
            
        self.page = page
        self.size = size
        self.sort_by = sort_by
        self.sort_order = sort_order
        
    @property
    def offset(self) -> int:
        """Calculate offset for database queries."""
        return (self.page - 1) * self.size


class PaginatedResult(Generic[T]):
    """Result container for paginated queries."""
    
    def __init__(
        self,
        items: List[T],
        total_count: int,
        page: int,
        size: int,
        total_pages: int
    ):
        self.items = items
        self.total_count = total_count
        self.page = page
        self.size = size
        self.total_pages = total_pages
        
    @property
    def has_next(self) -> bool:
        """Check if there are more pages."""
        return self.page < self.total_pages
        
    @property
    def has_previous(self) -> bool:
        """Check if there are previous pages."""
        return self.page > 1


class BaseRepository(ABC, Generic[T]):
    """
    Abstract base repository providing common CRUD operations.
    
    Follows the Repository pattern to abstract data access operations
    and provide a consistent interface for domain entities.
    """
    
    @abstractmethod
    async def create(self, entity: T) -> Result[T]:
        """
        Create a new entity in the repository.
        
        Args:
            entity: The domain entity to create
            
        Returns:
            Result containing the created entity or error
        """
        pass
    
    @abstractmethod
    async def get_by_id(self, entity_id: UUID) -> Result[Optional[T]]:
        """
        Get an entity by its ID.
        
        Args:
            entity_id: The unique identifier of the entity
            
        Returns:
            Result containing the entity if found, None if not found, or error
        """
        pass
    
    @abstractmethod
    async def update(self, entity: T) -> Result[T]:
        """
        Update an existing entity in the repository.
        
        Args:
            entity: The domain entity to update
            
        Returns:
            Result containing the updated entity or error
        """
        pass
    
    @abstractmethod
    async def delete(self, entity_id: UUID) -> Result[bool]:
        """
        Delete an entity from the repository.
        
        Args:
            entity_id: The unique identifier of the entity to delete
            
        Returns:
            Result containing True if deleted, False if not found, or error
        """
        pass
    
    @abstractmethod
    async def list(
        self, 
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[T]]:
        """
        List entities with optional filtering and pagination.
        
        Args:
            filters: Optional filters to apply
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated list of entities or error
        """
        pass
    
    @abstractmethod
    async def exists(self, entity_id: UUID) -> Result[bool]:
        """
        Check if an entity exists in the repository.
        
        Args:
            entity_id: The unique identifier to check
            
        Returns:
            Result containing True if exists, False otherwise, or error
        """
        pass
    
    @abstractmethod
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> Result[int]:
        """
        Count entities matching the given filters.
        
        Args:
            filters: Optional filters to apply
            
        Returns:
            Result containing the count or error
        """
        pass


class IVideoRepository(BaseRepository[Video]):
    """Repository interface for Video entities."""
    
    @abstractmethod
    async def get_by_user_id(
        self, 
        user_id: UserId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Video]]:
        """
        Get videos for a specific user.
        
        Args:
            user_id: The user identifier
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated videos or error
        """
        pass
    
    @abstractmethod
    async def get_by_status(
        self,
        status: VideoStatus,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Video]]:
        """
        Get videos by status.
        
        Args:
            status: The video status to filter by
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated videos or error
        """
        pass
    
    @abstractmethod
    async def get_by_topic(
        self,
        topic: VideoTopic,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Video]]:
        """
        Get videos by topic.
        
        Args:
            topic: The video topic to filter by
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated videos or error
        """
        pass
    
    @abstractmethod
    async def get_videos_needing_processing(
        self,
        limit: int = 10
    ) -> Result[List[Video]]:
        """
        Get videos that need processing.
        
        Args:
            limit: Maximum number of videos to return
            
        Returns:
            Result containing list of videos or error
        """
        pass


class IUserRepository(BaseRepository[User]):
    """Repository interface for User entities."""
    
    @abstractmethod
    async def get_by_clerk_id(self, clerk_user_id: str) -> Result[Optional[User]]:
        """
        Get user by Clerk user ID.
        
        Args:
            clerk_user_id: The Clerk user identifier
            
        Returns:
            Result containing the user if found, None if not found, or error
        """
        pass
    
    @abstractmethod
    async def get_by_email(self, email: str) -> Result[Optional[User]]:
        """
        Get user by email address.
        
        Args:
            email: The email address
            
        Returns:
            Result containing the user if found, None if not found, or error
        """
        pass
    
    @abstractmethod
    async def get_active_users(
        self,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[User]]:
        """
        Get all active users.
        
        Args:
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated active users or error
        """
        pass
    
    @abstractmethod
    async def get_users_by_role(
        self,
        role: str,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[User]]:
        """
        Get users by role.
        
        Args:
            role: The user role to filter by
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated users or error
        """
        pass


class IJobRepository(BaseRepository[Job]):
    """Repository interface for Job entities."""
    
    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: UserId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Job]]:
        """
        Get jobs for a specific user.
        
        Args:
            user_id: The user identifier
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated jobs or error
        """
        pass
    
    @abstractmethod
    async def get_by_status(
        self,
        status: JobStatus,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Job]]:
        """
        Get jobs by status.
        
        Args:
            status: The job status to filter by
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated jobs or error
        """
        pass
    
    @abstractmethod
    async def get_by_priority(
        self,
        priority: JobPriority,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Job]]:
        """
        Get jobs by priority.
        
        Args:
            priority: The job priority to filter by
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated jobs or error
        """
        pass
    
    @abstractmethod
    async def get_pending_jobs(
        self,
        limit: int = 10
    ) -> Result[List[Job]]:
        """
        Get pending jobs ready for processing.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            Result containing list of pending jobs or error
        """
        pass
    
    @abstractmethod
    async def get_jobs_by_video_id(
        self,
        video_id: VideoId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Job]]:
        """
        Get jobs for a specific video.
        
        Args:
            video_id: The video identifier
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated jobs or error
        """
        pass


class IFileRepository(BaseRepository[File]):
    """Repository interface for File entities."""
    
    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: UserId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """
        Get files for a specific user.
        
        Args:
            user_id: The user identifier
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated files or error
        """
        pass
    
    @abstractmethod
    async def get_by_type(
        self,
        file_type: str,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """
        Get files by type.
        
        Args:
            file_type: The file type to filter by
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated files or error
        """
        pass
    
    @abstractmethod
    async def get_by_size_range(
        self,
        min_size: FileSize,
        max_size: FileSize,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """
        Get files within a size range.
        
        Args:
            min_size: Minimum file size
            max_size: Maximum file size
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated files or error
        """
        pass
    
    @abstractmethod
    async def get_orphaned_files(
        self,
        older_than: datetime,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """
        Get files that are orphaned (not referenced by any entity).
        
        Args:
            older_than: Files older than this datetime
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated orphaned files or error
        """
        pass
    
    @abstractmethod
    async def get_by_job_id(
        self,
        job_id: JobId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """
        Get files associated with a specific job.
        
        Args:
            job_id: The job identifier
            pagination: Optional pagination parameters
            
        Returns:
            Result containing paginated files or error
        """
        pass
