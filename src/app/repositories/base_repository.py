"""
Repository Pattern Implementation for Data Access Layer.

This module provides abstract base repositories and concrete implementations
following the Repository pattern to abstract data access operations from
business logic, enabling easier testing and database switching.
"""

import logging
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, Optional, List, Dict, Any
from datetime import datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete, and_, or_, desc, asc
from sqlalchemy.orm import selectinload

from ..models.base import BaseModel
from ..schemas.common import PaginationRequest
from ..interfaces.base import ServiceResult

logger = logging.getLogger(__name__)

T = TypeVar('T', bound=BaseModel)
EntityType = TypeVar('EntityType')


class PaginatedResult(Generic[T]):
    """Result container for paginated queries."""
    
    def __init__(
        self,
        items: List[T],
        total_count: int,
        page: int,
        page_size: int,
        has_next: bool = False,
        has_previous: bool = False
    ):
        self.items = items
        self.total_count = total_count
        self.page = page
        self.page_size = page_size
        self.has_next = has_next
        self.has_previous = has_previous
        self.total_pages = (total_count + page_size - 1) // page_size if page_size > 0 else 0


class IRepository(ABC, Generic[T]):
    """Abstract base repository interface."""
    
    @abstractmethod
    async def create(self, entity: T) -> ServiceResult[T]:
        """Create a new entity."""
        pass
    
    @abstractmethod
    async def get_by_id(self, entity_id: str) -> ServiceResult[Optional[T]]:
        """Get entity by ID."""
        pass
    
    @abstractmethod
    async def update(self, entity: T) -> ServiceResult[T]:
        """Update existing entity."""
        pass
    
    @abstractmethod
    async def delete(self, entity_id: str) -> ServiceResult[bool]:
        """Delete entity by ID."""
        pass
    
    @abstractmethod
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[PaginationRequest] = None,
        order_by: Optional[List[str]] = None
    ) -> ServiceResult[PaginatedResult[T]]:
        """List entities with optional filtering, pagination, and ordering."""
        pass
    
    @abstractmethod
    async def exists(self, entity_id: str) -> ServiceResult[bool]:
        """Check if entity exists."""
        pass
    
    @abstractmethod
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> ServiceResult[int]:
        """Count entities with optional filtering."""
        pass


class BaseRepository(IRepository[T], ABC):
    """Base repository implementation with common functionality."""
    
    def __init__(self, session: AsyncSession, model_class: type):
        """
        Initialize base repository.
        
        Args:
            session: Async database session
            model_class: SQLAlchemy model class
        """
        self.session = session
        self.model_class = model_class
    
    async def create(self, entity: T) -> ServiceResult[T]:
        """Create a new entity."""
        try:
            # Convert domain model to database model if needed
            db_entity = await self._to_db_model(entity)
            
            self.session.add(db_entity)
            await self.session.commit()
            await self.session.refresh(db_entity)
            
            # Convert back to domain model
            domain_entity = await self._to_domain_model(db_entity)
            
            logger.debug(f"Created {self.model_class.__name__} with ID: {db_entity.id}")
            return ServiceResult.success(domain_entity)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error creating {self.model_class.__name__}: {e}")
            return ServiceResult.error(
                error=f"Failed to create entity: {str(e)}",
                error_code="REPOSITORY_CREATE_ERROR"
            )
    
    async def get_by_id(self, entity_id: str) -> ServiceResult[Optional[T]]:
        """Get entity by ID."""
        try:
            stmt = select(self.model_class).where(self.model_class.id == entity_id)
            result = await self.session.execute(stmt)
            db_entity = result.scalar_one_or_none()
            
            if db_entity is None:
                return ServiceResult.success(None)
            
            domain_entity = await self._to_domain_model(db_entity)
            return ServiceResult.success(domain_entity)
            
        except Exception as e:
            logger.error(f"Error getting {self.model_class.__name__} by ID {entity_id}: {e}")
            return ServiceResult.error(
                error=f"Failed to get entity: {str(e)}",
                error_code="REPOSITORY_GET_ERROR"
            )
    
    async def update(self, entity: T) -> ServiceResult[T]:
        """Update existing entity."""
        try:
            # Convert domain model to database model
            db_entity = await self._to_db_model(entity)
            
            # Update timestamp
            db_entity.updated_at = datetime.utcnow()
            
            await self.session.merge(db_entity)
            await self.session.commit()
            await self.session.refresh(db_entity)
            
            # Convert back to domain model
            domain_entity = await self._to_domain_model(db_entity)
            
            logger.debug(f"Updated {self.model_class.__name__} with ID: {db_entity.id}")
            return ServiceResult.success(domain_entity)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error updating {self.model_class.__name__}: {e}")
            return ServiceResult.error(
                error=f"Failed to update entity: {str(e)}",
                error_code="REPOSITORY_UPDATE_ERROR"
            )
    
    async def delete(self, entity_id: str) -> ServiceResult[bool]:
        """Delete entity by ID."""
        try:
            stmt = delete(self.model_class).where(self.model_class.id == entity_id)
            result = await self.session.execute(stmt)
            await self.session.commit()
            
            deleted = result.rowcount > 0
            
            if deleted:
                logger.debug(f"Deleted {self.model_class.__name__} with ID: {entity_id}")
            else:
                logger.warning(f"{self.model_class.__name__} with ID {entity_id} not found for deletion")
            
            return ServiceResult.success(deleted)
            
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Error deleting {self.model_class.__name__} with ID {entity_id}: {e}")
            return ServiceResult.error(
                error=f"Failed to delete entity: {str(e)}",
                error_code="REPOSITORY_DELETE_ERROR"
            )
    
    async def list(
        self,
        filters: Optional[Dict[str, Any]] = None,
        pagination: Optional[PaginationRequest] = None,
        order_by: Optional[List[str]] = None
    ) -> ServiceResult[PaginatedResult[T]]:
        """List entities with optional filtering, pagination, and ordering."""
        try:
            # Base query
            stmt = select(self.model_class)
            
            # Apply filters
            if filters:
                stmt = self._apply_filters(stmt, filters)
            
            # Count total items (before pagination)
            count_stmt = select(self.model_class.id)
            if filters:
                count_stmt = self._apply_filters(count_stmt, filters)
            
            count_result = await self.session.execute(count_stmt)
            total_count = len(count_result.all())
            
            # Apply ordering
            if order_by:
                stmt = self._apply_ordering(stmt, order_by)
            
            # Apply pagination
            page = 1
            page_size = 50
            if pagination:
                page = pagination.page
                page_size = pagination.page_size
                offset = (page - 1) * page_size
                stmt = stmt.offset(offset).limit(page_size)
            
            # Execute query
            result = await self.session.execute(stmt)
            db_entities = result.scalars().all()
            
            # Convert to domain models
            domain_entities = []
            for db_entity in db_entities:
                domain_entity = await self._to_domain_model(db_entity)
                domain_entities.append(domain_entity)
            
            # Create paginated result
            has_next = (page * page_size) < total_count
            has_previous = page > 1
            
            paginated_result = PaginatedResult(
                items=domain_entities,
                total_count=total_count,
                page=page,
                page_size=page_size,
                has_next=has_next,
                has_previous=has_previous
            )
            
            return ServiceResult.success(paginated_result)
            
        except Exception as e:
            logger.error(f"Error listing {self.model_class.__name__}: {e}")
            return ServiceResult.error(
                error=f"Failed to list entities: {str(e)}",
                error_code="REPOSITORY_LIST_ERROR"
            )
    
    async def exists(self, entity_id: str) -> ServiceResult[bool]:
        """Check if entity exists."""
        try:
            stmt = select(self.model_class.id).where(self.model_class.id == entity_id)
            result = await self.session.execute(stmt)
            exists = result.scalar_one_or_none() is not None
            
            return ServiceResult.success(exists)
            
        except Exception as e:
            logger.error(f"Error checking existence of {self.model_class.__name__} with ID {entity_id}: {e}")
            return ServiceResult.error(
                error=f"Failed to check entity existence: {str(e)}",
                error_code="REPOSITORY_EXISTS_ERROR"
            )
    
    async def count(self, filters: Optional[Dict[str, Any]] = None) -> ServiceResult[int]:
        """Count entities with optional filtering."""
        try:
            stmt = select(self.model_class.id)
            
            if filters:
                stmt = self._apply_filters(stmt, filters)
            
            result = await self.session.execute(stmt)
            count = len(result.all())
            
            return ServiceResult.success(count)
            
        except Exception as e:
            logger.error(f"Error counting {self.model_class.__name__}: {e}")
            return ServiceResult.error(
                error=f"Failed to count entities: {str(e)}",
                error_code="REPOSITORY_COUNT_ERROR"
            )
    
    def _apply_filters(self, stmt, filters: Dict[str, Any]):
        """Apply filters to query statement."""
        conditions = []
        
        for field, value in filters.items():
            if hasattr(self.model_class, field):
                column = getattr(self.model_class, field)
                
                if isinstance(value, dict):
                    # Handle complex filters like {"gte": 100} or {"in": [1, 2, 3]}
                    for operator, op_value in value.items():
                        if operator == 'eq':
                            conditions.append(column == op_value)
                        elif operator == 'ne':
                            conditions.append(column != op_value)
                        elif operator == 'gt':
                            conditions.append(column > op_value)
                        elif operator == 'gte':
                            conditions.append(column >= op_value)
                        elif operator == 'lt':
                            conditions.append(column < op_value)
                        elif operator == 'lte':
                            conditions.append(column <= op_value)
                        elif operator == 'in':
                            conditions.append(column.in_(op_value))
                        elif operator == 'not_in':
                            conditions.append(~column.in_(op_value))
                        elif operator == 'like':
                            conditions.append(column.like(f"%{op_value}%"))
                        elif operator == 'ilike':
                            conditions.append(column.ilike(f"%{op_value}%"))
                else:
                    # Simple equality filter
                    conditions.append(column == value)
        
        if conditions:
            stmt = stmt.where(and_(*conditions))
        
        return stmt
    
    def _apply_ordering(self, stmt, order_by: List[str]):
        """Apply ordering to query statement."""
        order_clauses = []
        
        for order_field in order_by:
            if order_field.startswith('-'):
                # Descending order
                field = order_field[1:]
                if hasattr(self.model_class, field):
                    column = getattr(self.model_class, field)
                    order_clauses.append(desc(column))
            else:
                # Ascending order
                if hasattr(self.model_class, order_field):
                    column = getattr(self.model_class, order_field)
                    order_clauses.append(asc(column))
        
        if order_clauses:
            stmt = stmt.order_by(*order_clauses)
        
        return stmt
    
    @abstractmethod
    async def _to_domain_model(self, db_entity) -> T:
        """Convert database model to domain model."""
        pass
    
    @abstractmethod
    async def _to_db_model(self, domain_entity: T):
        """Convert domain model to database model."""
        pass


class IUserRepository(IRepository[EntityType]):
    """User repository interface."""
    
    @abstractmethod
    async def get_by_clerk_id(self, clerk_id: str) -> ServiceResult[Optional[EntityType]]:
        """Get user by Clerk ID."""
        pass
    
    @abstractmethod
    async def get_by_email(self, email: str) -> ServiceResult[Optional[EntityType]]:
        """Get user by email."""
        pass


class IJobRepository(IRepository[EntityType]):
    """Job repository interface."""
    
    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: str,
        pagination: Optional[PaginationRequest] = None,
        status_filter: Optional[str] = None
    ) -> ServiceResult[PaginatedResult[EntityType]]:
        """Get jobs by user ID."""
        pass
    
    @abstractmethod
    async def get_pending_jobs(
        self,
        limit: Optional[int] = None
    ) -> ServiceResult[List[EntityType]]:
        """Get pending jobs for processing."""
        pass
    
    @abstractmethod
    async def update_status(self, job_id: str, status: str) -> ServiceResult[bool]:
        """Update job status."""
        pass


class IVideoRepository(IRepository[EntityType]):
    """Video repository interface."""
    
    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: str,
        pagination: Optional[PaginationRequest] = None
    ) -> ServiceResult[PaginatedResult[EntityType]]:
        """Get videos by user ID."""
        pass
    
    @abstractmethod
    async def get_by_status(
        self,
        status: str,
        pagination: Optional[PaginationRequest] = None
    ) -> ServiceResult[PaginatedResult[EntityType]]:
        """Get videos by status."""
        pass


class IFileRepository(IRepository[EntityType]):
    """File repository interface."""
    
    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: str,
        pagination: Optional[PaginationRequest] = None
    ) -> ServiceResult[PaginatedResult[EntityType]]:
        """Get files by user ID."""
        pass
    
    @abstractmethod
    async def get_by_type(
        self,
        file_type: str,
        pagination: Optional[PaginationRequest] = None
    ) -> ServiceResult[PaginatedResult[EntityType]]:
        """Get files by type."""
        pass


# Repository factory for creating repository instances
class RepositoryFactory:
    """Factory for creating repository instances."""
    
    @staticmethod
    def create_user_repository(session: AsyncSession) -> IUserRepository:
        """Create user repository instance."""
        from .concrete_repositories import UserRepository
        return UserRepository(session)
    
    @staticmethod
    def create_job_repository(session: AsyncSession) -> IJobRepository:
        """Create job repository instance."""
        from .concrete_repositories import JobRepository
        return JobRepository(session)
    
    @staticmethod
    def create_video_repository(session: AsyncSession) -> IVideoRepository:
        """Create video repository instance."""
        from .concrete_repositories import VideoRepository
        return VideoRepository(session)
    
    @staticmethod
    def create_file_repository(session: AsyncSession) -> IFileRepository:
        """Create file repository instance."""
        from .concrete_repositories import FileRepository
        return FileRepository(session)
