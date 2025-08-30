"""
S3 File Metadata Management and Versioning.

This module provides comprehensive metadata management for S3 files including
versioning support, metadata storage/retrieval, and file organization.
"""

import logging
import asyncio
import json
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, asdict
from enum import Enum

import boto3
from botocore.exceptions import ClientError

from src.config.aws_config import AWSConfig

logger = logging.getLogger(__name__)


class FileVersionStatus(str, Enum):
    """File version status enumeration."""
    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


@dataclass
class S3FileMetadata:
    """Comprehensive S3 file metadata structure."""
    file_id: str
    user_id: str
    job_id: Optional[str]
    scene_number: Optional[int]
    original_filename: str
    file_type: str
    mime_type: str
    file_size: int
    s3_bucket: str
    s3_key: str
    version_id: Optional[str]
    checksum: str
    created_at: datetime
    updated_at: datetime
    status: FileVersionStatus
    tags: List[str]
    custom_metadata: Dict[str, Any]
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        data = asdict(self)
        # Convert datetime objects to ISO strings
        data['created_at'] = self.created_at.isoformat()
        data['updated_at'] = self.updated_at.isoformat()
        if self.last_accessed:
            data['last_accessed'] = self.last_accessed.isoformat()
        return data
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'S3FileMetadata':
        """Create from dictionary."""
        # Convert ISO strings back to datetime objects
        data['created_at'] = datetime.fromisoformat(data['created_at'])
        data['updated_at'] = datetime.fromisoformat(data['updated_at'])
        if data.get('last_accessed'):
            data['last_accessed'] = datetime.fromisoformat(data['last_accessed'])
        return cls(**data)


@dataclass
class FileVersion:
    """File version information."""
    version_id: str
    version_number: int
    created_at: datetime
    file_size: int
    checksum: str
    is_current: bool
    change_description: Optional[str] = None
    created_by: Optional[str] = None


class S3MetadataManager:
    """Manages S3 file metadata and versioning."""
    
    def __init__(self, aws_config: AWSConfig):
        """
        Initialize S3 metadata manager.
        
        Args:
            aws_config: AWS configuration object
        """
        self.config = aws_config
        
        # Create thread-safe session
        self.session = boto3.Session(
            aws_access_key_id=aws_config.access_key_id,
            aws_secret_access_key=aws_config.secret_access_key,
            region_name=aws_config.region
        )
        self.s3_client = self.session.client('s3')
        
        # Metadata bucket for storing file metadata
        self.metadata_bucket = aws_config.buckets.get('temp', '')  # Use temp bucket for metadata
        
        logger.info(f"Initialized S3MetadataManager for environment: {aws_config.environment}")
    
    def _get_metadata_key(self, file_id: str) -> str:
        """
        Generate metadata key for storing file metadata.
        
        Args:
            file_id: File identifier (S3 key)
            
        Returns:
            str: Metadata key
        """
        # Replace slashes with underscores to create a flat metadata structure
        safe_file_id = file_id.replace('/', '_').replace('\\', '_')
        return f"metadata/{safe_file_id}.json"
    
    def _get_versions_key(self, file_id: str) -> str:
        """
        Generate versions key for storing file version history.
        
        Args:
            file_id: File identifier (S3 key)
            
        Returns:
            str: Versions key
        """
        safe_file_id = file_id.replace('/', '_').replace('\\', '_')
        return f"versions/{safe_file_id}.json"
    
    async def store_file_metadata(self, metadata: S3FileMetadata) -> bool:
        """
        Store file metadata in S3.
        
        Args:
            metadata: File metadata to store
            
        Returns:
            bool: True if metadata was stored successfully
        """
        try:
            metadata_key = self._get_metadata_key(metadata.file_id)
            metadata_json = json.dumps(metadata.to_dict(), indent=2)
            
            # Store metadata in S3
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self.s3_client.put_object,
                    {
                        'Bucket': self.metadata_bucket,
                        'Key': metadata_key,
                        'Body': metadata_json.encode('utf-8'),
                        'ContentType': 'application/json',
                        'Metadata': {
                            'file_id': metadata.file_id,
                            'user_id': metadata.user_id,
                            'file_type': metadata.file_type,
                            'created_at': metadata.created_at.isoformat()
                        }
                    }
                )
            
            logger.info(f"Successfully stored metadata for file: {metadata.file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to store file metadata: {e}")
            return False
    
    async def get_file_metadata(self, file_id: str) -> Optional[S3FileMetadata]:
        """
        Retrieve file metadata from S3.
        
        Args:
            file_id: File identifier (S3 key)
            
        Returns:
            S3FileMetadata or None if not found
        """
        try:
            metadata_key = self._get_metadata_key(file_id)
            
            # Get metadata from S3
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                try:
                    response = await loop.run_in_executor(
                        executor,
                        self.s3_client.get_object,
                        {'Bucket': self.metadata_bucket, 'Key': metadata_key}
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        return None
                    raise
            
            # Parse metadata
            metadata_json = response['Body'].read().decode('utf-8')
            metadata_dict = json.loads(metadata_json)
            
            return S3FileMetadata.from_dict(metadata_dict)
            
        except Exception as e:
            logger.error(f"Failed to get file metadata: {e}")
            return None
    
    async def update_file_metadata(self, file_id: str, updates: Dict[str, Any]) -> bool:
        """
        Update file metadata.
        
        Args:
            file_id: File identifier (S3 key)
            updates: Dictionary of fields to update
            
        Returns:
            bool: True if metadata was updated successfully
        """
        try:
            # Get existing metadata
            metadata = await self.get_file_metadata(file_id)
            if not metadata:
                logger.warning(f"Metadata not found for file: {file_id}")
                return False
            
            # Apply updates
            for field, value in updates.items():
                if hasattr(metadata, field):
                    setattr(metadata, field, value)
            
            # Update timestamp
            metadata.updated_at = datetime.utcnow()
            
            # Store updated metadata
            return await self.store_file_metadata(metadata)
            
        except Exception as e:
            logger.error(f"Failed to update file metadata: {e}")
            return False
    
    async def delete_file_metadata(self, file_id: str) -> bool:
        """
        Delete file metadata from S3.
        
        Args:
            file_id: File identifier (S3 key)
            
        Returns:
            bool: True if metadata was deleted successfully
        """
        try:
            metadata_key = self._get_metadata_key(file_id)
            versions_key = self._get_versions_key(file_id)
            
            # Delete both metadata and versions
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                # Delete metadata
                await loop.run_in_executor(
                    executor,
                    self.s3_client.delete_object,
                    {'Bucket': self.metadata_bucket, 'Key': metadata_key}
                )
                
                # Delete versions (ignore if doesn't exist)
                try:
                    await loop.run_in_executor(
                        executor,
                        self.s3_client.delete_object,
                        {'Bucket': self.metadata_bucket, 'Key': versions_key}
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] != 'NoSuchKey':
                        raise
            
            logger.info(f"Successfully deleted metadata for file: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to delete file metadata: {e}")
            return False
    
    async def create_file_version(self, file_id: str, version_info: FileVersion) -> bool:
        """
        Create a new file version entry.
        
        Args:
            file_id: File identifier (S3 key)
            version_info: Version information
            
        Returns:
            bool: True if version was created successfully
        """
        try:
            # Get existing versions
            versions = await self.get_file_versions(file_id)
            
            # Mark previous versions as not current
            for version in versions:
                version.is_current = False
            
            # Add new version
            new_version_dict = {
                'version_id': version_info.version_id,
                'version_number': version_info.version_number,
                'created_at': version_info.created_at.isoformat(),
                'file_size': version_info.file_size,
                'checksum': version_info.checksum,
                'is_current': version_info.is_current,
                'change_description': version_info.change_description,
                'created_by': version_info.created_by
            }
            
            versions_dict = [
                {
                    'version_id': v.version_id,
                    'version_number': v.version_number,
                    'created_at': v.created_at.isoformat(),
                    'file_size': v.file_size,
                    'checksum': v.checksum,
                    'is_current': v.is_current,
                    'change_description': v.change_description,
                    'created_by': v.created_by
                }
                for v in versions
            ]
            versions_dict.append(new_version_dict)
            
            # Store versions
            versions_key = self._get_versions_key(file_id)
            versions_json = json.dumps(versions_dict, indent=2)
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                await loop.run_in_executor(
                    executor,
                    self.s3_client.put_object,
                    {
                        'Bucket': self.metadata_bucket,
                        'Key': versions_key,
                        'Body': versions_json.encode('utf-8'),
                        'ContentType': 'application/json',
                        'Metadata': {
                            'file_id': file_id,
                            'version_count': str(len(versions_dict))
                        }
                    }
                )
            
            logger.info(f"Successfully created version {version_info.version_number} for file: {file_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to create file version: {e}")
            return False
    
    async def get_file_versions(self, file_id: str) -> List[FileVersion]:
        """
        Get all versions of a file.
        
        Args:
            file_id: File identifier (S3 key)
            
        Returns:
            List of FileVersion objects
        """
        try:
            versions_key = self._get_versions_key(file_id)
            
            # Get versions from S3
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                try:
                    response = await loop.run_in_executor(
                        executor,
                        self.s3_client.get_object,
                        {'Bucket': self.metadata_bucket, 'Key': versions_key}
                    )
                except ClientError as e:
                    if e.response['Error']['Code'] == 'NoSuchKey':
                        return []
                    raise
            
            # Parse versions
            versions_json = response['Body'].read().decode('utf-8')
            versions_data = json.loads(versions_json)
            
            versions = []
            for version_dict in versions_data:
                version = FileVersion(
                    version_id=version_dict['version_id'],
                    version_number=version_dict['version_number'],
                    created_at=datetime.fromisoformat(version_dict['created_at']),
                    file_size=version_dict['file_size'],
                    checksum=version_dict['checksum'],
                    is_current=version_dict['is_current'],
                    change_description=version_dict.get('change_description'),
                    created_by=version_dict.get('created_by')
                )
                versions.append(version)
            
            # Sort by version number (newest first)
            versions.sort(key=lambda x: x.version_number, reverse=True)
            
            return versions
            
        except Exception as e:
            logger.error(f"Failed to get file versions: {e}")
            return []
    
    async def get_current_version(self, file_id: str) -> Optional[FileVersion]:
        """
        Get the current version of a file.
        
        Args:
            file_id: File identifier (S3 key)
            
        Returns:
            FileVersion or None if not found
        """
        versions = await self.get_file_versions(file_id)
        
        for version in versions:
            if version.is_current:
                return version
        
        # If no current version marked, return the latest
        return versions[0] if versions else None
    
    async def restore_file_version(self, file_id: str, version_id: str) -> bool:
        """
        Restore a specific version as the current version.
        
        Args:
            file_id: File identifier (S3 key)
            version_id: Version ID to restore
            
        Returns:
            bool: True if version was restored successfully
        """
        try:
            versions = await self.get_file_versions(file_id)
            
            # Find the version to restore
            target_version = None
            for version in versions:
                if version.version_id == version_id:
                    target_version = version
                    break
            
            if not target_version:
                logger.warning(f"Version {version_id} not found for file: {file_id}")
                return False
            
            # Mark all versions as not current
            for version in versions:
                version.is_current = False
            
            # Mark target version as current
            target_version.is_current = True
            
            # Create new version entry for the restoration
            new_version = FileVersion(
                version_id=f"restore_{int(datetime.utcnow().timestamp())}",
                version_number=max(v.version_number for v in versions) + 1,
                created_at=datetime.utcnow(),
                file_size=target_version.file_size,
                checksum=target_version.checksum,
                is_current=True,
                change_description=f"Restored from version {target_version.version_number}",
                created_by=None  # Could be passed as parameter
            )
            
            # Update versions
            return await self.create_file_version(file_id, new_version)
            
        except Exception as e:
            logger.error(f"Failed to restore file version: {e}")
            return False
    
    async def track_file_access(self, file_id: str, user_id: str) -> bool:
        """
        Track file access for analytics.
        
        Args:
            file_id: File identifier (S3 key)
            user_id: User who accessed the file
            
        Returns:
            bool: True if access was tracked successfully
        """
        try:
            # Update metadata with access information
            updates = {
                'access_count': 0,  # Will be incremented
                'last_accessed': datetime.utcnow()
            }
            
            # Get current metadata to increment access count
            metadata = await self.get_file_metadata(file_id)
            if metadata:
                updates['access_count'] = metadata.access_count + 1
            
            return await self.update_file_metadata(file_id, updates)
            
        except Exception as e:
            logger.error(f"Failed to track file access: {e}")
            return False
    
    async def search_files_by_metadata(
        self,
        user_id: str,
        filters: Dict[str, Any],
        limit: int = 100
    ) -> List[S3FileMetadata]:
        """
        Search files by metadata criteria.
        
        Args:
            user_id: User ID to filter by
            filters: Search filters (file_type, tags, date_range, etc.)
            limit: Maximum number of results
            
        Returns:
            List of matching S3FileMetadata objects
        """
        try:
            # List all metadata files for the user
            prefix = f"metadata/users_{user_id}_"
            
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as executor:
                response = await loop.run_in_executor(
                    executor,
                    self.s3_client.list_objects_v2,
                    {
                        'Bucket': self.metadata_bucket,
                        'Prefix': prefix,
                        'MaxKeys': limit * 2  # Get more to account for filtering
                    }
                )
            
            matching_files = []
            
            # Process each metadata file
            for obj in response.get('Contents', []):
                try:
                    # Get metadata
                    metadata_response = await loop.run_in_executor(
                        executor,
                        self.s3_client.get_object,
                        {'Bucket': self.metadata_bucket, 'Key': obj['Key']}
                    )
                    
                    metadata_json = metadata_response['Body'].read().decode('utf-8')
                    metadata_dict = json.loads(metadata_json)
                    metadata = S3FileMetadata.from_dict(metadata_dict)
                    
                    # Apply filters
                    if self._matches_filters(metadata, filters):
                        matching_files.append(metadata)
                        
                        if len(matching_files) >= limit:
                            break
                
                except Exception as e:
                    logger.warning(f"Failed to process metadata file {obj['Key']}: {e}")
                    continue
            
            # Sort by created_at (newest first)
            matching_files.sort(key=lambda x: x.created_at, reverse=True)
            
            return matching_files[:limit]
            
        except Exception as e:
            logger.error(f"Failed to search files by metadata: {e}")
            return []
    
    def _matches_filters(self, metadata: S3FileMetadata, filters: Dict[str, Any]) -> bool:
        """
        Check if metadata matches search filters.
        
        Args:
            metadata: File metadata to check
            filters: Search filters
            
        Returns:
            bool: True if metadata matches all filters
        """
        try:
            # File type filter
            if 'file_type' in filters and metadata.file_type != filters['file_type']:
                return False
            
            # Tags filter (any tag matches)
            if 'tags' in filters:
                filter_tags = set(filters['tags'])
                metadata_tags = set(metadata.tags)
                if not filter_tags.intersection(metadata_tags):
                    return False
            
            # Date range filter
            if 'date_from' in filters:
                date_from = datetime.fromisoformat(filters['date_from'])
                if metadata.created_at < date_from:
                    return False
            
            if 'date_to' in filters:
                date_to = datetime.fromisoformat(filters['date_to'])
                if metadata.created_at > date_to:
                    return False
            
            # File size filter
            if 'min_size' in filters and metadata.file_size < filters['min_size']:
                return False
            
            if 'max_size' in filters and metadata.file_size > filters['max_size']:
                return False
            
            # Status filter
            if 'status' in filters and metadata.status != filters['status']:
                return False
            
            # Job ID filter
            if 'job_id' in filters and metadata.job_id != filters['job_id']:
                return False
            
            return True
            
        except Exception as e:
            logger.warning(f"Error applying filters: {e}")
            return False
    
    async def get_file_statistics(self, user_id: str) -> Dict[str, Any]:
        """
        Get file statistics for a user.
        
        Args:
            user_id: User ID
            
        Returns:
            Dictionary with file statistics
        """
        try:
            # Search all files for the user
            all_files = await self.search_files_by_metadata(user_id, {}, limit=10000)
            
            if not all_files:
                return {
                    'total_files': 0,
                    'total_size': 0,
                    'by_type': {},
                    'by_status': {},
                    'recent_uploads': 0,
                    'total_versions': 0
                }
            
            # Calculate statistics
            total_files = len(all_files)
            total_size = sum(f.file_size for f in all_files)
            
            # Group by type
            by_type = {}
            for file in all_files:
                by_type[file.file_type] = by_type.get(file.file_type, 0) + 1
            
            # Group by status
            by_status = {}
            for file in all_files:
                status = file.status.value
                by_status[status] = by_status.get(status, 0) + 1
            
            # Recent uploads (last 7 days)
            recent_cutoff = datetime.utcnow() - timedelta(days=7)
            recent_uploads = sum(1 for f in all_files if f.created_at > recent_cutoff)
            
            # Count total versions
            total_versions = 0
            for file in all_files:
                versions = await self.get_file_versions(file.file_id)
                total_versions += len(versions)
            
            return {
                'total_files': total_files,
                'total_size': total_size,
                'by_type': by_type,
                'by_status': by_status,
                'recent_uploads': recent_uploads,
                'total_versions': total_versions
            }
            
        except Exception as e:
            logger.error(f"Failed to get file statistics: {e}")
            return {
                'total_files': 0,
                'total_size': 0,
                'by_type': {},
                'by_status': {},
                'recent_uploads': 0,
                'total_versions': 0
            }