"""
Storage Service Infrastructure Implementation - S3 and Local File Storage.

This module provides concrete implementations of the storage service interface
for different storage backends (AWS S3, Local filesystem).
"""

import logging
import asyncio
import os
import tempfile
from typing import Optional, Dict, Any, List, AsyncGenerator
from datetime import datetime, timedelta
from pathlib import Path
import io

import boto3
from botocore.exceptions import ClientError, NoCredentialsError
from boto3.s3.transfer import TransferConfig

from ..interfaces.infrastructure import IStorageService
from ..interfaces.base import ServiceResult
from ...core.config import get_settings

logger = logging.getLogger(__name__)


class S3StorageService(IStorageService):
    """AWS S3 storage service implementation."""
    
    def __init__(self, aws_config: Optional[Dict[str, Any]] = None):
        """Initialize S3 storage service with AWS configuration."""
        self.settings = get_settings()
        self.aws_config = aws_config or {}
        
        # Initialize S3 client
        session = boto3.Session(
            aws_access_key_id=self.aws_config.get('access_key_id'),
            aws_secret_access_key=self.aws_config.get('secret_access_key'),
            region_name=self.aws_config.get('region', 'us-east-1')
        )
        self.s3_client = session.client('s3')
        
        # Configure transfer settings
        self.transfer_config = TransferConfig(
            multipart_threshold=1024 * 25,  # 25MB
            max_concurrency=10,
            multipart_chunksize=1024 * 25,
            use_threads=True
        )
        
        self.bucket_name = self.aws_config.get('bucket_name', 'default-bucket')
        
    @property
    def service_name(self) -> str:
        return "S3StorageService"
    
    async def store_file(
        self, 
        file_content: bytes, 
        file_path: str, 
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """Store file in S3."""
        try:
            # Prepare upload parameters
            upload_params = {
                'Bucket': self.bucket_name,
                'Key': file_path,
                'Body': file_content
            }
            
            if content_type:
                upload_params['ContentType'] = content_type
            
            if metadata:
                upload_params['Metadata'] = metadata
            
            # Upload to S3
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.put_object(**upload_params)
            )
            
            # Get file info
            file_size = len(file_content)
            file_url = f"https://{self.bucket_name}.s3.amazonaws.com/{file_path}"
            
            return ServiceResult.success({
                "file_path": file_path,
                "file_url": file_url,
                "file_size": file_size,
                "storage_backend": "s3",
                "bucket": self.bucket_name
            })
            
        except ClientError as e:
            logger.error(f"S3 client error storing file {file_path}: {e}")
            return ServiceResult.error(
                error=f"S3 storage error: {str(e)}",
                error_code="S3_STORAGE_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error storing file {file_path}: {e}")
            return ServiceResult.error(
                error=f"Storage error: {str(e)}",
                error_code="STORAGE_ERROR"
            )
    
    async def retrieve_file(
        self, 
        file_path: str
    ) -> ServiceResult[bytes]:
        """Retrieve file from S3."""
        try:
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.get_object(Bucket=self.bucket_name, Key=file_path)
            )
            
            file_content = response['Body'].read()
            
            return ServiceResult.success(file_content)
            
        except ClientError as e:
            if e.response['Error']['Code'] == 'NoSuchKey':
                return ServiceResult.error(
                    error=f"File not found: {file_path}",
                    error_code="FILE_NOT_FOUND"
                )
            else:
                logger.error(f"S3 client error retrieving file {file_path}: {e}")
                return ServiceResult.error(
                    error=f"S3 retrieval error: {str(e)}",
                    error_code="S3_RETRIEVAL_ERROR"
                )
        except Exception as e:
            logger.error(f"Unexpected error retrieving file {file_path}: {e}")
            return ServiceResult.error(
                error=f"Retrieval error: {str(e)}",
                error_code="RETRIEVAL_ERROR"
            )
    
    async def delete_file(
        self, 
        file_path: str
    ) -> ServiceResult[bool]:
        """Delete file from S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.delete_object(Bucket=self.bucket_name, Key=file_path)
            )
            
            return ServiceResult.success(True)
            
        except ClientError as e:
            logger.error(f"S3 client error deleting file {file_path}: {e}")
            return ServiceResult.error(
                error=f"S3 deletion error: {str(e)}",
                error_code="S3_DELETION_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error deleting file {file_path}: {e}")
            return ServiceResult.error(
                error=f"Deletion error: {str(e)}",
                error_code="DELETION_ERROR"
            )
    
    async def generate_download_url(
        self, 
        file_path: str, 
        expiration_hours: int = 24
    ) -> ServiceResult[Dict[str, Any]]:
        """Generate presigned download URL for S3 object."""
        try:
            expiration_seconds = expiration_hours * 3600
            expires_at = datetime.utcnow() + timedelta(seconds=expiration_seconds)
            
            loop = asyncio.get_event_loop()
            presigned_url = await loop.run_in_executor(
                None,
                lambda: self.s3_client.generate_presigned_url(
                    'get_object',
                    Params={'Bucket': self.bucket_name, 'Key': file_path},
                    ExpiresIn=expiration_seconds
                )
            )
            
            return ServiceResult.success({
                "url": presigned_url,
                "expires_at": expires_at,
                "expiration_hours": expiration_hours
            })
            
        except ClientError as e:
            logger.error(f"S3 client error generating URL for {file_path}: {e}")
            return ServiceResult.error(
                error=f"S3 URL generation error: {str(e)}",
                error_code="S3_URL_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error generating URL for {file_path}: {e}")
            return ServiceResult.error(
                error=f"URL generation error: {str(e)}",
                error_code="URL_GENERATION_ERROR"
            )
    
    async def list_files(
        self, 
        prefix: str = "", 
        limit: Optional[int] = None
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """List files in S3 bucket with optional prefix."""
        try:
            list_params = {
                'Bucket': self.bucket_name,
                'Prefix': prefix
            }
            
            if limit:
                list_params['MaxKeys'] = limit
            
            loop = asyncio.get_event_loop()
            response = await loop.run_in_executor(
                None,
                lambda: self.s3_client.list_objects_v2(**list_params)
            )
            
            files = []
            for obj in response.get('Contents', []):
                files.append({
                    "file_path": obj['Key'],
                    "size": obj['Size'],
                    "last_modified": obj['LastModified'],
                    "etag": obj['ETag'].strip('"')
                })
            
            return ServiceResult.success(files)
            
        except ClientError as e:
            logger.error(f"S3 client error listing files with prefix {prefix}: {e}")
            return ServiceResult.error(
                error=f"S3 listing error: {str(e)}",
                error_code="S3_LISTING_ERROR"
            )
        except Exception as e:
            logger.error(f"Unexpected error listing files with prefix {prefix}: {e}")
            return ServiceResult.error(
                error=f"Listing error: {str(e)}",
                error_code="LISTING_ERROR"
            )
    
    async def check_file_exists(
        self, 
        file_path: str
    ) -> ServiceResult[bool]:
        """Check if file exists in S3."""
        try:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self.s3_client.head_object(Bucket=self.bucket_name, Key=file_path)
            )
            
            return ServiceResult.success(True)
            
        except ClientError as e:
            if e.response['Error']['Code'] == '404':
                return ServiceResult.success(False)
            else:
                logger.error(f"S3 client error checking file {file_path}: {e}")
                return ServiceResult.error(
                    error=f"S3 check error: {str(e)}",
                    error_code="S3_CHECK_ERROR"
                )
        except Exception as e:
            logger.error(f"Unexpected error checking file {file_path}: {e}")
            return ServiceResult.error(
                error=f"Check error: {str(e)}",
                error_code="CHECK_ERROR"
            )


class LocalStorageService(IStorageService):
    """Local filesystem storage service implementation."""
    
    def __init__(self, storage_path: str = None):
        """Initialize local storage service."""
        self.storage_path = Path(storage_path or tempfile.gettempdir()) / "local_storage"
        self.storage_path.mkdir(exist_ok=True, parents=True)
        
    @property
    def service_name(self) -> str:
        return "LocalStorageService"
    
    async def store_file(
        self, 
        file_content: bytes, 
        file_path: str, 
        content_type: Optional[str] = None,
        metadata: Optional[Dict[str, str]] = None
    ) -> ServiceResult[Dict[str, Any]]:
        """Store file in local filesystem."""
        try:
            full_path = self.storage_path / file_path
            full_path.parent.mkdir(exist_ok=True, parents=True)
            
            # Write file content
            with open(full_path, 'wb') as f:
                f.write(file_content)
            
            # Store metadata if provided
            if metadata:
                metadata_path = full_path.with_suffix(full_path.suffix + '.meta')
                import json
                with open(metadata_path, 'w') as f:
                    json.dump(metadata, f)
            
            file_size = len(file_content)
            
            return ServiceResult.success({
                "file_path": file_path,
                "full_path": str(full_path),
                "file_size": file_size,
                "storage_backend": "local"
            })
            
        except Exception as e:
            logger.error(f"Error storing file {file_path}: {e}")
            return ServiceResult.error(
                error=f"Local storage error: {str(e)}",
                error_code="LOCAL_STORAGE_ERROR"
            )
    
    async def retrieve_file(
        self, 
        file_path: str
    ) -> ServiceResult[bytes]:
        """Retrieve file from local filesystem."""
        try:
            full_path = self.storage_path / file_path
            
            if not full_path.exists():
                return ServiceResult.error(
                    error=f"File not found: {file_path}",
                    error_code="FILE_NOT_FOUND"
                )
            
            with open(full_path, 'rb') as f:
                file_content = f.read()
            
            return ServiceResult.success(file_content)
            
        except Exception as e:
            logger.error(f"Error retrieving file {file_path}: {e}")
            return ServiceResult.error(
                error=f"Local retrieval error: {str(e)}",
                error_code="LOCAL_RETRIEVAL_ERROR"
            )
    
    async def delete_file(
        self, 
        file_path: str
    ) -> ServiceResult[bool]:
        """Delete file from local filesystem."""
        try:
            full_path = self.storage_path / file_path
            
            if full_path.exists():
                full_path.unlink()
                
                # Also delete metadata if exists
                metadata_path = full_path.with_suffix(full_path.suffix + '.meta')
                if metadata_path.exists():
                    metadata_path.unlink()
            
            return ServiceResult.success(True)
            
        except Exception as e:
            logger.error(f"Error deleting file {file_path}: {e}")
            return ServiceResult.error(
                error=f"Local deletion error: {str(e)}",
                error_code="LOCAL_DELETION_ERROR"
            )
    
    async def generate_download_url(
        self, 
        file_path: str, 
        expiration_hours: int = 24
    ) -> ServiceResult[Dict[str, Any]]:
        """Generate local file path (no expiration for local storage)."""
        try:
            full_path = self.storage_path / file_path
            
            if not full_path.exists():
                return ServiceResult.error(
                    error=f"File not found: {file_path}",
                    error_code="FILE_NOT_FOUND"
                )
            
            expires_at = datetime.utcnow() + timedelta(hours=expiration_hours)
            
            return ServiceResult.success({
                "url": f"file://{full_path}",
                "expires_at": expires_at,
                "expiration_hours": expiration_hours
            })
            
        except Exception as e:
            logger.error(f"Error generating URL for {file_path}: {e}")
            return ServiceResult.error(
                error=f"Local URL generation error: {str(e)}",
                error_code="LOCAL_URL_ERROR"
            )
    
    async def list_files(
        self, 
        prefix: str = "", 
        limit: Optional[int] = None
    ) -> ServiceResult[List[Dict[str, Any]]]:
        """List files in local storage with optional prefix."""
        try:
            search_path = self.storage_path
            if prefix:
                search_path = search_path / prefix
            
            files = []
            for file_path in search_path.rglob('*'):
                if file_path.is_file() and not file_path.name.endswith('.meta'):
                    relative_path = file_path.relative_to(self.storage_path)
                    stat = file_path.stat()
                    
                    files.append({
                        "file_path": str(relative_path),
                        "size": stat.st_size,
                        "last_modified": datetime.fromtimestamp(stat.st_mtime),
                        "full_path": str(file_path)
                    })
                    
                    if limit and len(files) >= limit:
                        break
            
            return ServiceResult.success(files)
            
        except Exception as e:
            logger.error(f"Error listing files with prefix {prefix}: {e}")
            return ServiceResult.error(
                error=f"Local listing error: {str(e)}",
                error_code="LOCAL_LISTING_ERROR"
            )
    
    async def check_file_exists(
        self, 
        file_path: str
    ) -> ServiceResult[bool]:
        """Check if file exists in local storage."""
        try:
            full_path = self.storage_path / file_path
            exists = full_path.exists() and full_path.is_file()
            
            return ServiceResult.success(exists)
            
        except Exception as e:
            logger.error(f"Error checking file {file_path}: {e}")
            return ServiceResult.error(
                error=f"Local check error: {str(e)}",
                error_code="LOCAL_CHECK_ERROR"
            )
