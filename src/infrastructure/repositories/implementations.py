"""
SQLAlchemy-based repository implementations.

This module provides concrete implementations of repository interfaces
using SQLAlchemy for data persistence. Each repository handles the mapping
between domain entities and database models.
"""

import logging
from typing import Optional, List, Dict, Any
from uuid import UUID
from datetime import datetime

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, func, and_, or_
from sqlalchemy.orm import selectinload

from ...app.database.models import User as UserModel, Job as JobModel, FileMetadata as FileModel
from ...domain import Result
from ...domain.entities import User, Video, Job, File
from ...domain.value_objects import (
    UserId, VideoId, JobId, FileId, VideoStatus, JobStatus, 
    JobPriority, VideoTopic, FileSize
)

from .interfaces import (
    IUserRepository, IVideoRepository, IJobRepository, IFileRepository,
    PaginationParams, PaginatedResult
)
from .mappers import UserMapper, JobMapper, FileMapper, VideoMapper

logger = logging.getLogger(__name__)


class BaseSQLAlchemyRepository:
    """Base repository with common SQLAlchemy operations."""
    
    def __init__(self, session: AsyncSession):
        self.session = session
    
    async def _execute_count(self, query) -> int:
        """Execute a count query."""
        result = await self.session.execute(query)
        return result.scalar() or 0
    
    def _apply_pagination(self, query, pagination: Optional[PaginationParams]):
        """Apply pagination to a query."""
        if pagination:
            query = query.offset(pagination.offset).limit(pagination.size)
        return query
    
    async def _get_paginated_result(
        self,
        query,
        count_query,
        pagination: Optional[PaginationParams],
        mapper_func
    ) -> Result[PaginatedResult]:
        """Get paginated results with mapping."""
        try:
            # Get total count
            total_count = await self._execute_count(count_query)
            
            # Apply pagination
            if pagination:
                query = self._apply_pagination(query, pagination)
                page = pagination.page
                size = pagination.size
            else:
                page = 1
                size = total_count
            
            # Execute query
            result = await self.session.execute(query)
            db_items = result.scalars().all()
            
            # Map to domain entities
            mapped_items = []
            for db_item in db_items:
                mapped_result = mapper_func(db_item)
                if mapped_result.is_success:
                    mapped_items.append(mapped_result.value)
                else:
                    logger.warning(f"Failed to map item: {mapped_result.error}")
            
            # Calculate total pages
            total_pages = (total_count + size - 1) // size if size > 0 else 1
            
            paginated_result = PaginatedResult(
                items=mapped_items,
                total_count=total_count,
                page=page,
                size=size,
                total_pages=total_pages
            )
            
            return Result.ok(paginated_result)
            
        except Exception as e:
            logger.error(f"Failed to get paginated result: {e}")
            return Result.fail(f"Database query failed: {str(e)}")


class UserRepository(BaseSQLAlchemyRepository, IUserRepository):
    """SQLAlchemy implementation of user repository."""
    
    async def create(self, entity: User) -> Result[User]:
        """Create a new user."""
        try:
            db_data = UserMapper.to_database(entity)
            db_user = UserModel(**db_data)
            
            self.session.add(db_user)
            await self.session.commit()
            await self.session.refresh(db_user)
            
            return UserMapper.to_domain(db_user)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create user: {e}")
            return Result.fail(f"Failed to create user: {str(e)}")
    
    async def get_by_id(self, entity_id: UUID) -> Result[Optional[User]]:
        """Get user by ID."""
        try:
            query = select(UserModel).where(
                and_(UserModel.id == entity_id, UserModel.is_deleted == False)
            )
            result = await self.session.execute(query)
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                return Result.ok(None)
            
            return UserMapper.to_domain(db_user)
            
        except Exception as e:
            logger.error(f"Failed to get user by ID: {e}")
            return Result.fail(f"Failed to get user: {str(e)}")
    
    async def get_by_clerk_id(self, clerk_user_id: str) -> Result[Optional[User]]:
        """Get user by Clerk ID."""
        try:
            query = select(UserModel).where(
                and_(
                    UserModel.clerk_user_id == clerk_user_id,
                    UserModel.is_deleted == False
                )
            )
            result = await self.session.execute(query)
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                return Result.ok(None)
            
            return UserMapper.to_domain(db_user)
            
        except Exception as e:
            logger.error(f"Failed to get user by Clerk ID: {e}")
            return Result.fail(f"Failed to get user: {str(e)}")
    
    async def get_by_email(self, email: str) -> Result[Optional[User]]:
        """Get user by email address."""
        try:
            query = select(UserModel).where(
                and_(
                    UserModel.primary_email == email,
                    UserModel.is_deleted == False
                )
            )
            result = await self.session.execute(query)
            db_user = result.scalar_one_or_none()
            
            if not db_user:
                return Result.ok(None)
            
            return UserMapper.to_domain(db_user)
            
        except Exception as e:
            logger.error(f"Failed to get user by email: {e}")
            return Result.fail(f"Failed to get user: {str(e)}")
    
    async def update(self, entity: User) -> Result[User]:
        """Update an existing user."""
        try:
            db_data = UserMapper.to_database(entity)
            db_data['updated_at'] = datetime.utcnow()
            
            stmt = update(UserModel).where(
                UserModel.id == UUID(entity.user_id.value)
            ).values(**db_data)
            
            await self.session.execute(stmt)
            await self.session.commit()
            
            # Fetch updated user
            return await self.get_by_id(UUID(entity.user_id.value))
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update user: {e}")
            return Result.fail(f"Failed to update user: {str(e)}")
    
    async def delete(self, entity_id: UUID) -> Result[bool]:
        """Soft delete a user."""
        try:
            stmt = update(UserModel).where(
                UserModel.id == entity_id
            ).values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            return Result.ok(result.rowcount > 0)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete user: {e}")
            return Result.fail(f"Failed to delete user: {str(e)}")
    
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[User]]:
        """List users with optional filtering and pagination."""
        try:
            query = select(UserModel).where(UserModel.is_deleted == False)
            count_query = select(func.count(UserModel.id)).where(UserModel.is_deleted == False)
            
            # Apply filters
            if filters:
                if 'role' in filters:
                    query = query.where(UserModel.role == filters['role'])
                    count_query = count_query.where(UserModel.role == filters['role'])
                
                if 'status' in filters:
                    query = query.where(UserModel.status == filters['status'])
                    count_query = count_query.where(UserModel.status == filters['status'])
                
                if 'email_verified' in filters:
                    query = query.where(UserModel.email_verified == filters['email_verified'])
                    count_query = count_query.where(UserModel.email_verified == filters['email_verified'])
            
            # Apply sorting
            if pagination and pagination.sort_by:
                sort_column = getattr(UserModel, pagination.sort_by, None)
                if sort_column:
                    if pagination.sort_order == 'desc':
                        query = query.order_by(sort_column.desc())
                    else:
                        query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(UserModel.created_at.desc())
            
            return await self._get_paginated_result(
                query, count_query, pagination, UserMapper.to_domain
            )
            
        except Exception as e:
            logger.error(f"Failed to list users: {e}")
            return Result.fail(f"Failed to list users: {str(e)}")
    
    async def exists(self, entity_id: UUID) -> Result[bool]:
        """Check if user exists."""
        try:
            query = select(func.count(UserModel.id)).where(
                and_(UserModel.id == entity_id, UserModel.is_deleted == False)
            )
            count = await self._execute_count(query)
            return Result.ok(count > 0)
            
        except Exception as e:
            logger.error(f"Failed to check user existence: {e}")
            return Result.fail(f"Failed to check user existence: {str(e)}")
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> Result[int]:
        """Count users matching filters."""
        try:
            query = select(func.count(UserModel.id)).where(UserModel.is_deleted == False)
            
            if filters:
                if 'role' in filters:
                    query = query.where(UserModel.role == filters['role'])
                if 'status' in filters:
                    query = query.where(UserModel.status == filters['status'])
            
            count = await self._execute_count(query)
            return Result.ok(count)
            
        except Exception as e:
            logger.error(f"Failed to count users: {e}")
            return Result.fail(f"Failed to count users: {str(e)}")
    
    async def get_active_users(
        self,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[User]]:
        """Get all active users."""
        return await self.list(
            filters={'status': 'active'},
            pagination=pagination
        )
    
    async def get_users_by_role(
        self,
        role: str,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[User]]:
        """Get users by role."""
        return await self.list(
            filters={'role': role},
            pagination=pagination
        )


class JobRepository(BaseSQLAlchemyRepository, IJobRepository):
    """SQLAlchemy implementation of job repository."""
    
    async def create(self, entity: Job) -> Result[Job]:
        """Create a new job."""
        try:
            db_data = JobMapper.to_database(entity)
            db_job = JobModel(**db_data)
            
            self.session.add(db_job)
            await self.session.commit()
            await self.session.refresh(db_job)
            
            return JobMapper.to_domain(db_job)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create job: {e}")
            return Result.fail(f"Failed to create job: {str(e)}")
    
    async def get_by_id(self, entity_id: UUID) -> Result[Optional[Job]]:
        """Get job by ID."""
        try:
            query = select(JobModel).where(
                and_(JobModel.id == entity_id, JobModel.is_deleted == False)
            )
            result = await self.session.execute(query)
            db_job = result.scalar_one_or_none()
            
            if not db_job:
                return Result.ok(None)
            
            return JobMapper.to_domain(db_job)
            
        except Exception as e:
            logger.error(f"Failed to get job by ID: {e}")
            return Result.fail(f"Failed to get job: {str(e)}")
    
    async def update(self, entity: Job) -> Result[Job]:
        """Update an existing job."""
        try:
            db_data = JobMapper.to_database(entity)
            db_data['updated_at'] = datetime.utcnow()
            
            stmt = update(JobModel).where(
                JobModel.id == UUID(entity.job_id.value)
            ).values(**db_data)
            
            await self.session.execute(stmt)
            await self.session.commit()
            
            # Fetch updated job
            return await self.get_by_id(UUID(entity.job_id.value))
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update job: {e}")
            return Result.fail(f"Failed to update job: {str(e)}")
    
    async def delete(self, entity_id: UUID) -> Result[bool]:
        """Soft delete a job."""
        try:
            stmt = update(JobModel).where(
                JobModel.id == entity_id
            ).values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            return Result.ok(result.rowcount > 0)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete job: {e}")
            return Result.fail(f"Failed to delete job: {str(e)}")
    
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Job]]:
        """List jobs with optional filtering and pagination."""
        try:
            query = select(JobModel).where(JobModel.is_deleted == False)
            count_query = select(func.count(JobModel.id)).where(JobModel.is_deleted == False)
            
            # Apply filters
            if filters:
                if 'user_id' in filters:
                    user_uuid = UUID(filters['user_id'])
                    query = query.where(JobModel.user_id == user_uuid)
                    count_query = count_query.where(JobModel.user_id == user_uuid)
                
                if 'status' in filters:
                    query = query.where(JobModel.status == filters['status'])
                    count_query = count_query.where(JobModel.status == filters['status'])
                
                if 'job_type' in filters:
                    query = query.where(JobModel.job_type == filters['job_type'])
                    count_query = count_query.where(JobModel.job_type == filters['job_type'])
                
                if 'priority' in filters:
                    query = query.where(JobModel.priority == filters['priority'])
                    count_query = count_query.where(JobModel.priority == filters['priority'])
            
            # Apply sorting
            if pagination and pagination.sort_by:
                sort_column = getattr(JobModel, pagination.sort_by, None)
                if sort_column:
                    if pagination.sort_order == 'desc':
                        query = query.order_by(sort_column.desc())
                    else:
                        query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(JobModel.created_at.desc())
            
            return await self._get_paginated_result(
                query, count_query, pagination, JobMapper.to_domain
            )
            
        except Exception as e:
            logger.error(f"Failed to list jobs: {e}")
            return Result.fail(f"Failed to list jobs: {str(e)}")
    
    async def exists(self, entity_id: UUID) -> Result[bool]:
        """Check if job exists."""
        try:
            query = select(func.count(JobModel.id)).where(
                and_(JobModel.id == entity_id, JobModel.is_deleted == False)
            )
            count = await self._execute_count(query)
            return Result.ok(count > 0)
            
        except Exception as e:
            logger.error(f"Failed to check job existence: {e}")
            return Result.fail(f"Failed to check job existence: {str(e)}")
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> Result[int]:
        """Count jobs matching filters."""
        try:
            query = select(func.count(JobModel.id)).where(JobModel.is_deleted == False)
            
            if filters:
                if 'user_id' in filters:
                    query = query.where(JobModel.user_id == UUID(filters['user_id']))
                if 'status' in filters:
                    query = query.where(JobModel.status == filters['status'])
                if 'job_type' in filters:
                    query = query.where(JobModel.job_type == filters['job_type'])
            
            count = await self._execute_count(query)
            return Result.ok(count)
            
        except Exception as e:
            logger.error(f"Failed to count jobs: {e}")
            return Result.fail(f"Failed to count jobs: {str(e)}")
    
    async def get_by_user_id(
        self,
        user_id: UserId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Job]]:
        """Get jobs for a specific user."""
        return await self.list(
            filters={'user_id': user_id.value},
            pagination=pagination
        )
    
    async def get_by_status(
        self,
        status: JobStatus,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Job]]:
        """Get jobs by status."""
        return await self.list(
            filters={'status': status.value},
            pagination=pagination
        )
    
    async def get_by_priority(
        self,
        priority: JobPriority,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Job]]:
        """Get jobs by priority."""
        return await self.list(
            filters={'priority': priority.value},
            pagination=pagination
        )
    
    async def get_pending_jobs(self, limit: int = 10) -> Result[List[Job]]:
        """Get pending jobs ready for processing."""
        try:
            query = select(JobModel).where(
                and_(
                    JobModel.is_deleted == False,
                    JobModel.status.in_(['queued', 'pending'])
                )
            ).order_by(
                JobModel.priority.desc(),
                JobModel.created_at.asc()
            ).limit(limit)
            
            result = await self.session.execute(query)
            db_jobs = result.scalars().all()
            
            jobs = []
            for db_job in db_jobs:
                job_result = JobMapper.to_domain(db_job)
                if job_result.is_success:
                    jobs.append(job_result.value)
                else:
                    logger.warning(f"Failed to map job: {job_result.error}")
            
            return Result.ok(jobs)
            
        except Exception as e:
            logger.error(f"Failed to get pending jobs: {e}")
            return Result.fail(f"Failed to get pending jobs: {str(e)}")
    
    async def get_jobs_by_video_id(
        self,
        video_id: VideoId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Job]]:
        """Get jobs for a specific video (using job ID as video ID)."""
        try:
            # Since video ID corresponds to job ID in our current implementation
            job_result = await self.get_by_id(UUID(video_id.value))
            
            if not job_result.is_success:
                return Result.fail(job_result.error)
            
            if job_result.value is None:
                # Return empty paginated result
                empty_result = PaginatedResult(
                    items=[],
                    total_count=0,
                    page=pagination.page if pagination else 1,
                    size=pagination.size if pagination else 0,
                    total_pages=0
                )
                return Result.ok(empty_result)
            
            # Return single job as paginated result
            paginated_result = PaginatedResult(
                items=[job_result.value],
                total_count=1,
                page=pagination.page if pagination else 1,
                size=pagination.size if pagination else 1,
                total_pages=1
            )
            
            return Result.ok(paginated_result)
            
        except Exception as e:
            logger.error(f"Failed to get jobs by video ID: {e}")
            return Result.fail(f"Failed to get jobs by video ID: {str(e)}")


class FileRepository(BaseSQLAlchemyRepository, IFileRepository):
    """SQLAlchemy implementation of file repository."""
    
    async def create(self, entity: File) -> Result[File]:
        """Create a new file."""
        try:
            db_data = FileMapper.to_database(entity)
            db_file = FileModel(**db_data)
            
            self.session.add(db_file)
            await self.session.commit()
            await self.session.refresh(db_file)
            
            return FileMapper.to_domain(db_file)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to create file: {e}")
            return Result.fail(f"Failed to create file: {str(e)}")
    
    async def get_by_id(self, entity_id: UUID) -> Result[Optional[File]]:
        """Get file by ID."""
        try:
            query = select(FileModel).where(
                and_(FileModel.id == entity_id, FileModel.is_deleted == False)
            )
            result = await self.session.execute(query)
            db_file = result.scalar_one_or_none()
            
            if not db_file:
                return Result.ok(None)
            
            return FileMapper.to_domain(db_file)
            
        except Exception as e:
            logger.error(f"Failed to get file by ID: {e}")
            return Result.fail(f"Failed to get file: {str(e)}")
    
    async def update(self, entity: File) -> Result[File]:
        """Update an existing file."""
        try:
            db_data = FileMapper.to_database(entity)
            db_data['updated_at'] = datetime.utcnow()
            
            stmt = update(FileModel).where(
                FileModel.id == UUID(entity.file_id.value)
            ).values(**db_data)
            
            await self.session.execute(stmt)
            await self.session.commit()
            
            # Fetch updated file
            return await self.get_by_id(UUID(entity.file_id.value))
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to update file: {e}")
            return Result.fail(f"Failed to update file: {str(e)}")
    
    async def delete(self, entity_id: UUID) -> Result[bool]:
        """Soft delete a file."""
        try:
            stmt = update(FileModel).where(
                FileModel.id == entity_id
            ).values(
                is_deleted=True,
                deleted_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            return Result.ok(result.rowcount > 0)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Failed to delete file: {e}")
            return Result.fail(f"Failed to delete file: {str(e)}")
    
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """List files with optional filtering and pagination."""
        try:
            query = select(FileModel).where(FileModel.is_deleted == False)
            count_query = select(func.count(FileModel.id)).where(FileModel.is_deleted == False)
            
            # Apply filters
            if filters:
                if 'user_id' in filters:
                    user_uuid = UUID(filters['user_id'])
                    query = query.where(FileModel.user_id == user_uuid)
                    count_query = count_query.where(FileModel.user_id == user_uuid)
                
                if 'job_id' in filters:
                    job_uuid = UUID(filters['job_id'])
                    query = query.where(FileModel.job_id == job_uuid)
                    count_query = count_query.where(FileModel.job_id == job_uuid)
                
                if 'file_type' in filters:
                    query = query.where(FileModel.file_type == filters['file_type'])
                    count_query = count_query.where(FileModel.file_type == filters['file_type'])
                
                if 'min_size' in filters:
                    query = query.where(FileModel.file_size >= filters['min_size'])
                    count_query = count_query.where(FileModel.file_size >= filters['min_size'])
                
                if 'max_size' in filters:
                    query = query.where(FileModel.file_size <= filters['max_size'])
                    count_query = count_query.where(FileModel.file_size <= filters['max_size'])
            
            # Apply sorting
            if pagination and pagination.sort_by:
                sort_column = getattr(FileModel, pagination.sort_by, None)
                if sort_column:
                    if pagination.sort_order == 'desc':
                        query = query.order_by(sort_column.desc())
                    else:
                        query = query.order_by(sort_column.asc())
            else:
                query = query.order_by(FileModel.created_at.desc())
            
            return await self._get_paginated_result(
                query, count_query, pagination, FileMapper.to_domain
            )
            
        except Exception as e:
            logger.error(f"Failed to list files: {e}")
            return Result.fail(f"Failed to list files: {str(e)}")
    
    async def exists(self, entity_id: UUID) -> Result[bool]:
        """Check if file exists."""
        try:
            query = select(func.count(FileModel.id)).where(
                and_(FileModel.id == entity_id, FileModel.is_deleted == False)
            )
            count = await self._execute_count(query)
            return Result.ok(count > 0)
            
        except Exception as e:
            logger.error(f"Failed to check file existence: {e}")
            return Result.fail(f"Failed to check file existence: {str(e)}")
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> Result[int]:
        """Count files matching filters."""
        try:
            query = select(func.count(FileModel.id)).where(FileModel.is_deleted == False)
            
            if filters:
                if 'user_id' in filters:
                    query = query.where(FileModel.user_id == UUID(filters['user_id']))
                if 'file_type' in filters:
                    query = query.where(FileModel.file_type == filters['file_type'])
                if 'job_id' in filters:
                    query = query.where(FileModel.job_id == UUID(filters['job_id']))
            
            count = await self._execute_count(query)
            return Result.ok(count)
            
        except Exception as e:
            logger.error(f"Failed to count files: {e}")
            return Result.fail(f"Failed to count files: {str(e)}")
    
    async def get_by_user_id(
        self,
        user_id: UserId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """Get files for a specific user."""
        return await self.list(
            filters={'user_id': user_id.value},
            pagination=pagination
        )
    
    async def get_by_type(
        self,
        file_type: str,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """Get files by type."""
        return await self.list(
            filters={'file_type': file_type},
            pagination=pagination
        )
    
    async def get_by_size_range(
        self,
        min_size: FileSize,
        max_size: FileSize,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """Get files within a size range."""
        return await self.list(
            filters={
                'min_size': min_size.bytes,
                'max_size': max_size.bytes
            },
            pagination=pagination
        )
    
    async def get_orphaned_files(
        self,
        older_than: datetime,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """Get files that are orphaned (not referenced by any entity)."""
        try:
            query = select(FileModel).where(
                and_(
                    FileModel.is_deleted == False,
                    FileModel.job_id.is_(None),  # No associated job
                    FileModel.created_at < older_than
                )
            ).order_by(FileModel.created_at.asc())
            
            count_query = select(func.count(FileModel.id)).where(
                and_(
                    FileModel.is_deleted == False,
                    FileModel.job_id.is_(None),
                    FileModel.created_at < older_than
                )
            )
            
            return await self._get_paginated_result(
                query, count_query, pagination, FileMapper.to_domain
            )
            
        except Exception as e:
            logger.error(f"Failed to get orphaned files: {e}")
            return Result.fail(f"Failed to get orphaned files: {str(e)}")
    
    async def get_by_job_id(
        self,
        job_id: JobId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[File]]:
        """Get files associated with a specific job."""
        return await self.list(
            filters={'job_id': job_id.value},
            pagination=pagination
        )


class VideoRepository(BaseSQLAlchemyRepository, IVideoRepository):
    """SQLAlchemy implementation of video repository using jobs as video storage."""
    
    async def create(self, entity: Video) -> Result[Video]:
        """Create a new video by creating a corresponding job."""
        try:
            # Convert video to job configuration
            job_config = VideoMapper.video_to_job_config(entity)
            
            # Create job configuration domain object
            from ...domain.value_objects import JobConfiguration, JobType, JobPriority
            config_result = JobConfiguration.create(job_config)
            if not config_result.is_success:
                return Result.fail(f"Invalid video configuration: {config_result.error}")
            
            # Create job entity
            from ...domain.entities import Job
            from ...domain.value_objects import JobStatus, JobProgress
            
            job = Job(
                job_id=JobId(entity.video_id.value),  # Use video ID as job ID
                user_id=entity.user_id,
                job_type=JobType('video_generation'),
                priority=JobPriority('normal'),
                configuration=config_result.value,
                status=JobStatus('queued'),
                progress=JobProgress(0),
                created_at=entity.created_at
            )
            
            # Use job repository to create
            job_repo = JobRepository(self.session)
            job_result = await job_repo.create(job)
            
            if not job_result.is_success:
                return Result.fail(f"Failed to create video job: {job_result.error}")
            
            # Extract video from created job
            video_result = VideoMapper.extract_video_from_job(job_result.value)
            if not video_result.is_success:
                return Result.fail(f"Failed to extract video: {video_result.error}")
            
            return Result.ok(video_result.value)
            
        except Exception as e:
            logger.error(f"Failed to create video: {e}")
            return Result.fail(f"Failed to create video: {str(e)}")
    
    async def get_by_id(self, entity_id: UUID) -> Result[Optional[Video]]:
        """Get video by ID (via job lookup)."""
        try:
            # Get job by ID
            job_repo = JobRepository(self.session)
            job_result = await job_repo.get_by_id(entity_id)
            
            if not job_result.is_success:
                return Result.fail(job_result.error)
            
            if job_result.value is None:
                return Result.ok(None)
            
            # Extract video from job
            video_result = VideoMapper.extract_video_from_job(job_result.value)
            if not video_result.is_success:
                return Result.fail(video_result.error)
            
            return Result.ok(video_result.value)
            
        except Exception as e:
            logger.error(f"Failed to get video by ID: {e}")
            return Result.fail(f"Failed to get video: {str(e)}")
    
    async def update(self, entity: Video) -> Result[Video]:
        """Update an existing video by updating the corresponding job."""
        try:
            # Get existing job
            job_repo = JobRepository(self.session)
            job_result = await job_repo.get_by_id(UUID(entity.video_id.value))
            
            if not job_result.is_success:
                return Result.fail(job_result.error)
            
            if job_result.value is None:
                return Result.fail("Video not found")
            
            job = job_result.value
            
            # Update job configuration with video data
            new_config = VideoMapper.video_to_job_config(entity)
            
            # Update job entity
            job._configuration = job.configuration.update(new_config)
            job._updated_at = datetime.utcnow()
            
            # Map video status to job status
            status_map = {
                'CREATED': 'queued',
                'UPLOADED': 'queued',
                'PROCESSING': 'processing',
                'COMPLETED': 'completed',
                'FAILED': 'failed'
            }
            
            new_status = status_map.get(entity.status.value, 'queued')
            if new_status != job.status.value:
                from ...domain.value_objects import JobStatus
                job._status = JobStatus(new_status)
            
            # Update job
            updated_job_result = await job_repo.update(job)
            if not updated_job_result.is_success:
                return Result.fail(updated_job_result.error)
            
            # Extract updated video
            video_result = VideoMapper.extract_video_from_job(updated_job_result.value)
            if not video_result.is_success:
                return Result.fail(video_result.error)
            
            return Result.ok(video_result.value)
            
        except Exception as e:
            logger.error(f"Failed to update video: {e}")
            return Result.fail(f"Failed to update video: {str(e)}")
    
    async def delete(self, entity_id: UUID) -> Result[bool]:
        """Delete a video by deleting the corresponding job."""
        try:
            job_repo = JobRepository(self.session)
            return await job_repo.delete(entity_id)
            
        except Exception as e:
            logger.error(f"Failed to delete video: {e}")
            return Result.fail(f"Failed to delete video: {str(e)}")
    
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Video]]:
        """List videos with optional filtering and pagination."""
        try:
            # Apply video-specific filters to job queries
            job_filters = {'job_type': 'video_generation'}
            
            if filters:
                if 'user_id' in filters:
                    job_filters['user_id'] = filters['user_id']
                if 'status' in filters:
                    # Map video status to job status
                    status_map = {
                        'CREATED': 'queued',
                        'UPLOADED': 'queued',
                        'PROCESSING': 'processing',
                        'COMPLETED': 'completed',
                        'FAILED': 'failed'
                    }
                    job_status = status_map.get(filters['status'], 'queued')
                    job_filters['status'] = job_status
            
            # Get jobs
            job_repo = JobRepository(self.session)
            jobs_result = await job_repo.list(job_filters, pagination)
            
            if not jobs_result.is_success:
                return Result.fail(jobs_result.error)
            
            # Convert jobs to videos
            videos = []
            for job in jobs_result.value.items:
                video_result = VideoMapper.extract_video_from_job(job)
                if video_result.is_success and video_result.value:
                    videos.append(video_result.value)
            
            # Create paginated result for videos
            video_result = PaginatedResult(
                items=videos,
                total_count=jobs_result.value.total_count,
                page=jobs_result.value.page,
                size=jobs_result.value.size,
                total_pages=jobs_result.value.total_pages
            )
            
            return Result.ok(video_result)
            
        except Exception as e:
            logger.error(f"Failed to list videos: {e}")
            return Result.fail(f"Failed to list videos: {str(e)}")
    
    async def exists(self, entity_id: UUID) -> Result[bool]:
        """Check if video exists."""
        try:
            job_repo = JobRepository(self.session)
            return await job_repo.exists(entity_id)
            
        except Exception as e:
            logger.error(f"Failed to check video existence: {e}")
            return Result.fail(f"Failed to check video existence: {str(e)}")
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> Result[int]:
        """Count videos matching filters."""
        try:
            job_filters = {'job_type': 'video_generation'}
            
            if filters:
                if 'user_id' in filters:
                    job_filters['user_id'] = filters['user_id']
                if 'status' in filters:
                    status_map = {
                        'CREATED': 'queued',
                        'UPLOADED': 'queued', 
                        'PROCESSING': 'processing',
                        'COMPLETED': 'completed',
                        'FAILED': 'failed'
                    }
                    job_status = status_map.get(filters['status'], 'queued')
                    job_filters['status'] = job_status
            
            job_repo = JobRepository(self.session)
            return await job_repo.count(job_filters)
            
        except Exception as e:
            logger.error(f"Failed to count videos: {e}")
            return Result.fail(f"Failed to count videos: {str(e)}")
    
    async def get_by_user_id(
        self,
        user_id: UserId,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Video]]:
        """Get videos for a specific user."""
        return await self.list(
            filters={'user_id': user_id.value},
            pagination=pagination
        )
    
    async def get_by_status(
        self,
        status: VideoStatus,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Video]]:
        """Get videos by status."""
        return await self.list(
            filters={'status': status.value},
            pagination=pagination
        )
    
    async def get_by_topic(
        self,
        topic: VideoTopic,
        pagination: Optional[PaginationParams] = None
    ) -> Result[PaginatedResult[Video]]:
        """Get videos by topic."""
        try:
            # This requires filtering by job configuration content
            job_repo = JobRepository(self.session)
            jobs_result = await job_repo.list(
                filters={'job_type': 'video_generation'},
                pagination=pagination
            )
            
            if not jobs_result.is_success:
                return Result.fail(jobs_result.error)
            
            # Filter jobs by topic in configuration
            videos = []
            for job in jobs_result.value.items:
                video_result = VideoMapper.extract_video_from_job(job)
                if (video_result.is_success and video_result.value and 
                    video_result.value.topic.value == topic.value):
                    videos.append(video_result.value)
            
            # Note: This is not optimal for large datasets as it filters in memory
            # In production, you might want to use database-level JSON queries
            
            video_result = PaginatedResult(
                items=videos,
                total_count=len(videos),  # This is approximate
                page=pagination.page if pagination else 1,
                size=len(videos),
                total_pages=1
            )
            
            return Result.ok(video_result)
            
        except Exception as e:
            logger.error(f"Failed to get videos by topic: {e}")
            return Result.fail(f"Failed to get videos by topic: {str(e)}")
    
    async def get_videos_needing_processing(self, limit: int = 10) -> Result[List[Video]]:
        """Get videos that need processing."""
        try:
            job_repo = JobRepository(self.session)
            jobs_result = await job_repo.get_pending_jobs(limit)
            
            if not jobs_result.is_success:
                return Result.fail(jobs_result.error)
            
            videos = []
            for job in jobs_result.value:
                if job.job_type.value == 'video_generation':
                    video_result = VideoMapper.extract_video_from_job(job)
                    if video_result.is_success and video_result.value:
                        videos.append(video_result.value)
            
            return Result.ok(videos)
            
        except Exception as e:
            logger.error(f"Failed to get videos needing processing: {e}")
            return Result.fail(f"Failed to get videos needing processing: {str(e)}")
