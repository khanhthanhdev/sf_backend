"""
File management service for handling file operations without Redis.

This service provides high-level file management operations including
upload handling, storage management, metadata tracking, and cleanup
using database-only storage.
"""

import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import UploadFile, HTTPException, status

from ..database.connection import RDSConnectionManager

logger = logging.getLogger(__name__)


class FileMetadata:
    """Simple file metadata structure."""
    
    def __init__(self, filename: str, file_size: int, file_type: str, 
                 file_path: str, user_id: str, **kwargs):
        self.filename = filename
        self.file_size = file_size
        self.file_type = file_type
        self.file_path = file_path
        self.user_id = user_id
        self.created_at = kwargs.get('created_at', datetime.utcnow())
        self.updated_at = kwargs.get('updated_at', datetime.utcnow())
    
    def dict(self) -> Dict[str, Any]:
        return {
            'filename': self.filename,
            'file_size': self.file_size,
            'file_type': self.file_type,
            'file_path': self.file_path,
            'user_id': self.user_id,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }


class PaginatedResponse:
    """Simple paginated response structure."""
    
    def __init__(self, data: List[Any], total_count: int, page: int, items_per_page: int):
        self.data = data
        self.total_count = total_count
        self.page = page
        self.items_per_page = items_per_page
        self.total_pages = (total_count + items_per_page - 1) // items_per_page


class FileService:
    """Service for file management operations without Redis dependencies."""
    
    def __init__(self, db_manager: Optional[RDSConnectionManager] = None):
        """Initialize file service."""
        self.db_manager = db_manager
    
    async def upload_file(
        self,
        file: UploadFile,
        user_id: str,
        file_type: Optional[str] = None,
        subdirectory: Optional[str] = None
    ) -> FileMetadata:
        """
        Upload and store a file with validation.
        
        Args:
            file: FastAPI UploadFile object
            user_id: User ID for file ownership
            file_type: Optional file type override
            subdirectory: Optional subdirectory for organization
            
        Returns:
            FileMetadata with storage information
            
        Raises:
            HTTPException: If validation or storage fails
        """
        try:
            # Basic file validation
            if not file.filename:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail="No filename provided"
                )
            
            # Read file content
            content = await file.read()
            file_size = len(content)
            
            # Simple file type detection from extension
            if not file_type:
                file_extension = Path(file.filename).suffix.lower()
                file_type = self._get_file_type_from_extension(file_extension)
            
            # Generate storage path
            storage_dir = Path("uploads") / user_id
            if subdirectory:
                storage_dir = storage_dir / subdirectory
            
            storage_dir.mkdir(parents=True, exist_ok=True)
            file_path = storage_dir / file.filename
            
            # Save file
            with open(file_path, "wb") as f:
                f.write(content)
            
            # Create metadata
            file_metadata = FileMetadata(
                filename=file.filename,
                file_size=file_size,
                file_type=file_type,
                file_path=str(file_path),
                user_id=user_id
            )
            
            # Store metadata in database if available
            if self.db_manager:
                await self._store_file_metadata_db(file_metadata)
            
            logger.info(
                "File uploaded successfully",
                extra={
                    "filename": file_metadata.filename,
                    "user_id": user_id,
                    "file_type": file_type,
                    "file_size": file_metadata.file_size
                }
            )
            
            return file_metadata
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to upload file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload file: {str(e)}"
            )
    
    def _get_file_type_from_extension(self, extension: str) -> str:
        """Get file type from extension."""
        extension_map = {
            '.jpg': 'image',
            '.jpeg': 'image', 
            '.png': 'image',
            '.gif': 'image',
            '.mp4': 'video',
            '.avi': 'video',
            '.mov': 'video',
            '.pdf': 'document',
            '.txt': 'document',
            '.doc': 'document',
            '.docx': 'document'
        }
        return extension_map.get(extension, 'unknown')
    
    async def _store_file_metadata_db(self, file_metadata: FileMetadata) -> None:
        """Store file metadata in database."""
        try:
            if not self.db_manager:
                return
                
            async with self.db_manager.get_session() as session:
                query = """
                    INSERT INTO file_metadata 
                    (filename, file_size, file_type, file_path, user_id, created_at, updated_at)
                    VALUES ($1, $2, $3, $4, $5, $6, $7)
                """
                await session.execute(
                    query,
                    file_metadata.filename,
                    file_metadata.file_size,
                    file_metadata.file_type,
                    file_metadata.file_path,
                    file_metadata.user_id,
                    file_metadata.created_at,
                    file_metadata.updated_at
                )
                await session.commit()
                
        except Exception as e:
            logger.warning(f"Failed to store file metadata in database: {e}")
    
    async def get_file_metadata(self, file_id: str, user_id: str) -> Optional[FileMetadata]:
        """
        Get file metadata by ID.
        
        Args:
            file_id: File identifier
            user_id: User ID for ownership verification
            
        Returns:
            FileMetadata if found and accessible
        """
        try:
            if not self.db_manager:
                return None
            
            async with self.db_manager.get_session() as session:
                query = """
                    SELECT * FROM file_metadata 
                    WHERE filename = $1 AND user_id = $2
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                row = await session.fetchrow(query, file_id, user_id)
                
                if row:
                    return FileMetadata(**dict(row))
                return None
                
        except Exception as e:
            logger.error(f"Failed to get file metadata: {e}")
            return None
    
    async def get_user_files(
        self,
        user_id: str,
        file_type: Optional[str] = None,
        page: int = 1,
        items_per_page: int = 20
    ) -> PaginatedResponse:
        """
        Get paginated list of user's files.
        
        Args:
            user_id: User ID
            file_type: Optional file type filter
            page: Page number (1-based)
            items_per_page: Items per page
            
        Returns:
            PaginatedResponse with file metadata
        """
        try:
            if not self.db_manager:
                return PaginatedResponse(data=[], total_count=0, page=page, items_per_page=items_per_page)
            
            async with self.db_manager.get_session() as session:
                # Build query with optional file type filter
                where_clause = "WHERE user_id = $1"
                params = [user_id]
                
                if file_type:
                    where_clause += " AND file_type = $2"
                    params.append(file_type)
                
                # Get total count
                count_query = f"SELECT COUNT(*) FROM file_metadata {where_clause}"
                total_count = await session.fetchval(count_query, *params)
                
                # Get paginated results
                offset = (page - 1) * items_per_page
                data_query = f"""
                    SELECT * FROM file_metadata {where_clause}
                    ORDER BY created_at DESC
                    LIMIT ${len(params) + 1} OFFSET ${len(params) + 2}
                """
                params.extend([items_per_page, offset])
                
                rows = await session.fetch(data_query, *params)
                files = [FileMetadata(**dict(row)) for row in rows]
                
                return PaginatedResponse(
                    data=files,
                    total_count=total_count,
                    page=page,
                    items_per_page=items_per_page
                )
                
        except Exception as e:
            logger.error(f"Failed to get user files: {e}")
            return PaginatedResponse(data=[], total_count=0, page=page, items_per_page=items_per_page)
    
    async def delete_file(self, file_id: str, user_id: str) -> bool:
        """
        Delete a file and its metadata.
        
        Args:
            file_id: File identifier
            user_id: User ID for ownership verification
            
        Returns:
            True if deletion successful
        """
        try:
            # Get file metadata first
            file_metadata = await self.get_file_metadata(file_id, user_id)
            if not file_metadata:
                logger.warning(f"File {file_id} not found for user {user_id}")
                return False
            
            # Delete physical file
            file_path = Path(file_metadata.file_path)
            if file_path.exists():
                file_path.unlink()
            
            # Delete metadata from database
            if self.db_manager:
                async with self.db_manager.get_session() as session:
                    query = "DELETE FROM file_metadata WHERE filename = $1 AND user_id = $2"
                    await session.execute(query, file_id, user_id)
                    await session.commit()
            
            logger.info(f"File {file_id} deleted successfully for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file {file_id}: {e}")
            return False
    
    async def cleanup_old_files(self, retention_days: int = 30) -> int:
        """
        Clean up old files based on retention policy.
        
        Args:
            retention_days: Number of days to retain files
            
        Returns:
            Number of files cleaned up
        """
        try:
            if not self.db_manager:
                return 0
            
            cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
            cleaned_count = 0
            
            async with self.db_manager.get_session() as session:
                # Find old files
                query = """
                    SELECT filename, file_path, user_id FROM file_metadata 
                    WHERE created_at < $1
                """
                rows = await session.fetch(query, cutoff_date)
                
                for row in rows:
                    try:
                        # Delete physical file
                        file_path = Path(row['file_path'])
                        if file_path.exists():
                            file_path.unlink()
                        
                        # Delete metadata
                        delete_query = """
                            DELETE FROM file_metadata 
                            WHERE filename = $1 AND user_id = $2
                        """
                        await session.execute(delete_query, row['filename'], row['user_id'])
                        cleaned_count += 1
                        
                    except Exception as e:
                        logger.warning(f"Failed to cleanup file {row['filename']}: {e}")
                
                await session.commit()
            
            logger.info(f"Cleaned up {cleaned_count} old files")
            return cleaned_count
            
        except Exception as e:
            logger.error(f"Failed to cleanup old files: {e}")
            return 0