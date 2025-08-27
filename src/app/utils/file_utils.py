"""
File handling utilities for secure file operations.

This module provides utilities for file upload validation, secure storage,
metadata extraction, and file management operations.
"""

import os
import io
import hashlib
import mimetypes
import magic
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timedelta
import aiofiles
import aiofiles.os
from PIL import Image
import ffmpeg

from fastapi import UploadFile, HTTPException, status
from pydantic import BaseModel

from ..core.config import get_settings
from ..core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class FileValidationResult(BaseModel):
    """Result of file validation."""
    is_valid: bool
    file_type: str
    mime_type: str
    file_size: int
    errors: List[str] = []
    warnings: List[str] = []


class FileMetadata(BaseModel):
    """File metadata information."""
    filename: str
    original_filename: str
    file_path: str
    file_size: int
    mime_type: str
    file_type: str
    checksum: str
    created_at: datetime
    metadata: Dict[str, Any] = {}


class FileManager:
    """Secure file management operations."""
    
    # Allowed file types and their MIME types
    ALLOWED_FILE_TYPES = {
        'image': {
            'image/jpeg', 'image/png', 'image/gif', 'image/webp',
            'image/bmp', 'image/tiff'
        },
        'video': {
            'video/mp4', 'video/webm', 'video/avi', 'video/mov',
            'video/quicktime', 'video/x-msvideo'
        },
        'audio': {
            'audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp3',
            'audio/aac', 'audio/flac'
        },
        'document': {
            'application/pdf', 'text/plain', 'application/msword',
            'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        },
        'archive': {
            'application/zip', 'application/x-tar', 'application/gzip'
        }
    }
    
    # Maximum file sizes (in bytes)
    MAX_FILE_SIZES = {
        'image': 10 * 1024 * 1024,      # 10MB
        'video': 500 * 1024 * 1024,     # 500MB
        'audio': 50 * 1024 * 1024,      # 50MB
        'document': 25 * 1024 * 1024,   # 25MB
        'archive': 100 * 1024 * 1024,   # 100MB
    }
    
    def __init__(self, storage_path: Optional[str] = None):
        """Initialize file manager with storage path."""
        self.storage_path = Path(storage_path or settings.file_storage_path)
        self.ensure_storage_directories()
    
    def ensure_storage_directories(self) -> None:
        """Ensure all required storage directories exist."""
        directories = [
            self.storage_path,
            self.storage_path / "uploads",
            self.storage_path / "videos",
            self.storage_path / "thumbnails",
            self.storage_path / "temp",
            self.storage_path / "cache"
        ]
        
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            # Set secure permissions (owner read/write/execute only)
            os.chmod(directory, 0o700)
    
    async def validate_file(self, file: UploadFile) -> FileValidationResult:
        """
        Validate uploaded file for security and compliance.
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            FileValidationResult with validation details
        """
        errors = []
        warnings = []
        
        # Check file size
        file_size = 0
        if hasattr(file, 'size') and file.size:
            file_size = file.size
        else:
            # Read file to get size
            content = await file.read()
            file_size = len(content)
            await file.seek(0)  # Reset file pointer
        
        # Detect MIME type using python-magic
        file_content = await file.read(1024)  # Read first 1KB
        await file.seek(0)  # Reset file pointer
        
        try:
            mime_type = magic.from_buffer(file_content, mime=True)
        except Exception as e:
            logger.warning(f"Failed to detect MIME type: {e}")
            mime_type = file.content_type or 'application/octet-stream'
        
        # Determine file type category
        file_type = self._get_file_type_category(mime_type)
        
        if not file_type:
            errors.append(f"Unsupported file type: {mime_type}")
        
        # Check file size limits
        if file_type and file_size > self.MAX_FILE_SIZES.get(file_type, 0):
            max_size_mb = self.MAX_FILE_SIZES[file_type] / (1024 * 1024)
            errors.append(f"File too large. Maximum size for {file_type}: {max_size_mb}MB")
        
        # Check filename
        if not file.filename or len(file.filename) > 255:
            errors.append("Invalid filename")
        
        # Check for potentially dangerous file extensions
        if file.filename:
            dangerous_extensions = {'.exe', '.bat', '.cmd', '.scr', '.pif', '.com'}
            file_ext = Path(file.filename).suffix.lower()
            if file_ext in dangerous_extensions:
                errors.append(f"Dangerous file extension: {file_ext}")
        
        # Additional security checks
        if file_type == 'image':
            try:
                # Validate image file
                await file.seek(0)
                content = await file.read()
                await file.seek(0)
                
                # Try to open with PIL to validate
                try:
                    img = Image.open(io.BytesIO(content))
                    img.verify()
                except Exception as e:
                    errors.append(f"Invalid image file: {str(e)}")
            except Exception as e:
                warnings.append(f"Could not validate image: {str(e)}")
        
        return FileValidationResult(
            is_valid=len(errors) == 0,
            file_type=file_type or 'unknown',
            mime_type=mime_type,
            file_size=file_size,
            errors=errors,
            warnings=warnings
        )
    
    def _get_file_type_category(self, mime_type: str) -> Optional[str]:
        """Get file type category from MIME type."""
        for category, mime_types in self.ALLOWED_FILE_TYPES.items():
            if mime_type in mime_types:
                return category
        return None
    
    async def store_file(
        self,
        file: UploadFile,
        user_id: str,
        file_type: str,
        subdirectory: Optional[str] = None
    ) -> FileMetadata:
        """
        Store uploaded file securely with metadata.
        
        Args:
            file: FastAPI UploadFile object
            user_id: User ID for file ownership
            file_type: File type category
            subdirectory: Optional subdirectory for organization
            
        Returns:
            FileMetadata with storage information
            
        Raises:
            HTTPException: If file storage fails
        """
        try:
            # Generate secure filename
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
            file_ext = Path(file.filename).suffix.lower()
            secure_filename = f"{user_id}_{timestamp}_{hashlib.md5(file.filename.encode()).hexdigest()[:8]}{file_ext}"
            
            # Determine storage path
            storage_dir = self.storage_path / "uploads" / file_type
            if subdirectory:
                storage_dir = storage_dir / subdirectory
            
            storage_dir.mkdir(parents=True, exist_ok=True)
            file_path = storage_dir / secure_filename
            
            # Read and store file
            content = await file.read()
            
            async with aiofiles.open(file_path, 'wb') as f:
                await f.write(content)
            
            # Set secure file permissions
            os.chmod(file_path, 0o600)  # Owner read/write only
            
            # Calculate checksum
            checksum = hashlib.sha256(content).hexdigest()
            
            # Extract metadata
            metadata = await self._extract_file_metadata(file_path, file_type)
            
            file_metadata = FileMetadata(
                filename=secure_filename,
                original_filename=file.filename,
                file_path=str(file_path),
                file_size=len(content),
                mime_type=file.content_type or 'application/octet-stream',
                file_type=file_type,
                checksum=checksum,
                created_at=datetime.utcnow(),
                metadata=metadata
            )
            
            logger.info(
                "File stored successfully",
                filename=secure_filename,
                original_filename=file.filename,
                file_size=len(content),
                user_id=user_id,
                file_type=file_type
            )
            
            return file_metadata
            
        except Exception as e:
            logger.error(f"Failed to store file: {e}", exc_info=True)
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to store file: {str(e)}"
            )
    
    async def _extract_file_metadata(self, file_path: Path, file_type: str) -> Dict[str, Any]:
        """Extract metadata from file based on type."""
        metadata = {}
        
        try:
            if file_type == 'image':
                metadata.update(await self._extract_image_metadata(file_path))
            elif file_type == 'video':
                metadata.update(await self._extract_video_metadata(file_path))
            elif file_type == 'audio':
                metadata.update(await self._extract_audio_metadata(file_path))
        except Exception as e:
            logger.warning(f"Failed to extract metadata for {file_path}: {e}")
        
        return metadata
    
    async def _extract_image_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract image metadata."""
        metadata = {}
        
        try:
            with Image.open(file_path) as img:
                metadata.update({
                    'width': img.width,
                    'height': img.height,
                    'format': img.format,
                    'mode': img.mode,
                    'has_transparency': img.mode in ('RGBA', 'LA') or 'transparency' in img.info
                })
                
                # Extract EXIF data if available
                if hasattr(img, '_getexif') and img._getexif():
                    exif = img._getexif()
                    if exif:
                        metadata['exif'] = {k: v for k, v in exif.items() if isinstance(v, (str, int, float))}
        except Exception as e:
            logger.warning(f"Failed to extract image metadata: {e}")
        
        return metadata
    
    async def _extract_video_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract video metadata using ffmpeg."""
        metadata = {}
        
        try:
            probe = ffmpeg.probe(str(file_path))
            
            # Get video stream info
            video_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'video'), None)
            if video_stream:
                metadata.update({
                    'width': int(video_stream.get('width', 0)),
                    'height': int(video_stream.get('height', 0)),
                    'duration': float(video_stream.get('duration', 0)),
                    'fps': eval(video_stream.get('r_frame_rate', '0/1')),
                    'codec': video_stream.get('codec_name'),
                    'bitrate': int(video_stream.get('bit_rate', 0))
                })
            
            # Get audio stream info
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
            if audio_stream:
                metadata.update({
                    'audio_codec': audio_stream.get('codec_name'),
                    'audio_bitrate': int(audio_stream.get('bit_rate', 0)),
                    'sample_rate': int(audio_stream.get('sample_rate', 0)),
                    'channels': int(audio_stream.get('channels', 0))
                })
                
        except Exception as e:
            logger.warning(f"Failed to extract video metadata: {e}")
        
        return metadata
    
    async def _extract_audio_metadata(self, file_path: Path) -> Dict[str, Any]:
        """Extract audio metadata."""
        metadata = {}
        
        try:
            probe = ffmpeg.probe(str(file_path))
            
            audio_stream = next((stream for stream in probe['streams'] if stream['codec_type'] == 'audio'), None)
            if audio_stream:
                metadata.update({
                    'duration': float(audio_stream.get('duration', 0)),
                    'codec': audio_stream.get('codec_name'),
                    'bitrate': int(audio_stream.get('bit_rate', 0)),
                    'sample_rate': int(audio_stream.get('sample_rate', 0)),
                    'channels': int(audio_stream.get('channels', 0))
                })
                
        except Exception as e:
            logger.warning(f"Failed to extract audio metadata: {e}")
        
        return metadata
    
    async def delete_file(self, file_path: str) -> bool:
        """
        Securely delete a file.
        
        Args:
            file_path: Path to file to delete
            
        Returns:
            True if file was deleted successfully
        """
        try:
            path = Path(file_path)
            if path.exists() and path.is_file():
                await aiofiles.os.remove(path)
                logger.info(f"File deleted: {file_path}")
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            return False
    
    async def cleanup_expired_files(self, retention_days: int = 30) -> int:
        """
        Clean up files older than retention period.
        
        Args:
            retention_days: Number of days to retain files
            
        Returns:
            Number of files cleaned up
        """
        cleanup_count = 0
        cutoff_date = datetime.utcnow() - timedelta(days=retention_days)
        
        try:
            for root, dirs, files in os.walk(self.storage_path):
                for file in files:
                    file_path = Path(root) / file
                    
                    # Check file modification time
                    if file_path.stat().st_mtime < cutoff_date.timestamp():
                        try:
                            await aiofiles.os.remove(file_path)
                            cleanup_count += 1
                            logger.debug(f"Cleaned up expired file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Failed to cleanup file {file_path}: {e}")
            
            logger.info(f"Cleaned up {cleanup_count} expired files")
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired files: {e}")
        
        return cleanup_count
    
    def get_file_url(self, file_path: str, file_type: str) -> str:
        """
        Generate URL for file access.
        
        Args:
            file_path: Path to file
            file_type: Type of file
            
        Returns:
            URL for file access
        """
        # Extract filename from path
        filename = Path(file_path).name
        
        # Generate URL based on file type
        if file_type == 'video':
            return f"/api/v1/files/videos/{filename}"
        elif file_type == 'image':
            return f"/api/v1/files/images/{filename}"
        elif file_type == 'audio':
            return f"/api/v1/files/audio/{filename}"
        else:
            return f"/api/v1/files/download/{filename}"


# Global file manager instance
file_manager = FileManager()


# Utility functions
async def validate_upload_file(file: UploadFile) -> FileValidationResult:
    """Validate uploaded file."""
    return await file_manager.validate_file(file)


async def store_upload_file(
    file: UploadFile,
    user_id: str,
    file_type: str,
    subdirectory: Optional[str] = None
) -> FileMetadata:
    """Store uploaded file securely."""
    return await file_manager.store_file(file, user_id, file_type, subdirectory)


async def delete_stored_file(file_path: str) -> bool:
    """Delete stored file."""
    return await file_manager.delete_file(file_path)


async def cleanup_old_files(retention_days: int = 30) -> int:
    """Clean up old files."""
    return await file_manager.cleanup_expired_files(retention_days)


def generate_file_url(file_path: str, file_type: str) -> str:
    """Generate file access URL."""
    return file_manager.get_file_url(file_path, file_type)