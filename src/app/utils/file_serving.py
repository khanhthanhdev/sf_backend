"""
File serving utilities for secure and efficient file delivery.

This module provides utilities for serving files with access control,
caching, range requests, and security checks.
"""

import os
import mimetypes
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
import hashlib

from fastapi import Request, Response, HTTPException, status
from fastapi.responses import StreamingResponse, FileResponse
import aiofiles

from ..core.config import get_settings
from ..core.logger import get_logger

settings = get_settings()
logger = get_logger(__name__)


class FileServingManager:
    """Manager for secure file serving operations."""
    
    def __init__(self):
        self.cache_control_headers = {
            'image': 'public, max-age=86400',  # 1 day
            'video': 'public, max-age=3600',   # 1 hour
            'audio': 'public, max-age=3600',   # 1 hour
            'document': 'private, max-age=300', # 5 minutes
            'archive': 'private, max-age=300'   # 5 minutes
        }
    
    async def serve_file(
        self,
        file_path: str,
        file_type: str,
        original_filename: str,
        request: Request,
        inline: bool = False,
        enable_caching: bool = True,
        user_id: Optional[str] = None
    ) -> StreamingResponse:
        """
        Serve a file with proper headers and security checks.
        
        Args:
            file_path: Path to the file
            file_type: Type of file (image, video, etc.)
            original_filename: Original filename for Content-Disposition
            request: FastAPI request object
            inline: Whether to serve inline or as attachment
            enable_caching: Whether to enable caching headers
            
        Returns:
            StreamingResponse with file content
            
        Raises:
            HTTPException: If file not found or access denied
        """
        path = Path(file_path)
        
        # Security check - ensure file is within allowed directories
        if not self._is_safe_path(path):
            logger.warning(
                "Attempted access to unsafe file path",
                file_path=file_path,
                user_id=user_id,
                resolved_path=str(path.resolve()) if path.exists() else "non-existent"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access denied: Invalid file path"
            )
        
        # Check if file exists
        if not path.exists() or not path.is_file():
            logger.info(
                "File not found",
                file_path=file_path,
                user_id=user_id,
                exists=path.exists(),
                is_file=path.is_file() if path.exists() else False
            )
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Get file stats
        file_stat = path.stat()
        file_size = file_stat.st_size
        last_modified = datetime.fromtimestamp(file_stat.st_mtime)
        
        # Generate ETag
        etag = self._generate_etag(path, file_stat)
        
        # Check conditional requests
        if self._check_not_modified(request, etag, last_modified):
            return Response(status_code=status.HTTP_304_NOT_MODIFIED)
        
        # Determine content type
        content_type = self._get_content_type(path, file_type)
        
        # Check for range requests
        range_header = request.headers.get('range')
        if range_header:
            return await self._serve_range_request(
                path, file_size, range_header, content_type,
                original_filename, inline, enable_caching, file_type,
                etag, last_modified
            )
        
        # Serve full file
        return await self._serve_full_file(
            path, file_size, content_type, original_filename,
            inline, enable_caching, file_type, etag, last_modified
        )
    
    def _is_safe_path(self, path: Path) -> bool:
        """Check if file path is safe and within allowed directories."""
        try:
            # Resolve path to absolute path
            resolved_path = path.resolve()
            
            # Check if path is within storage directory
            storage_path = Path(settings.file_storage_path).resolve()
            
            # Ensure the file is within the storage directory
            return str(resolved_path).startswith(str(storage_path))
            
        except Exception:
            return False
    
    def _generate_etag(self, path: Path, file_stat: os.stat_result) -> str:
        """Generate ETag for file based on path, size, and modification time."""
        etag_data = f"{path}:{file_stat.st_size}:{file_stat.st_mtime}"
        return hashlib.md5(etag_data.encode()).hexdigest()
    
    def _check_not_modified(
        self,
        request: Request,
        etag: str,
        last_modified: datetime
    ) -> bool:
        """Check if file has not been modified based on conditional headers."""
        # Check If-None-Match header
        if_none_match = request.headers.get('if-none-match')
        if if_none_match and etag in if_none_match:
            return True
        
        # Check If-Modified-Since header
        if_modified_since = request.headers.get('if-modified-since')
        if if_modified_since:
            try:
                client_time = datetime.strptime(
                    if_modified_since, '%a, %d %b %Y %H:%M:%S GMT'
                )
                if last_modified <= client_time:
                    return True
            except ValueError:
                pass
        
        return False
    
    def _get_content_type(self, path: Path, file_type: str) -> str:
        """Determine content type for file."""
        # Try to guess from file extension
        content_type, _ = mimetypes.guess_type(str(path))
        
        if content_type:
            return content_type
        
        # Fallback based on file type
        fallback_types = {
            'image': 'image/jpeg',
            'video': 'video/mp4',
            'audio': 'audio/mpeg',
            'document': 'application/pdf',
            'archive': 'application/zip'
        }
        
        return fallback_types.get(file_type, 'application/octet-stream')
    
    async def _serve_range_request(
        self,
        path: Path,
        file_size: int,
        range_header: str,
        content_type: str,
        original_filename: str,
        inline: bool,
        enable_caching: bool,
        file_type: str,
        etag: str,
        last_modified: datetime
    ) -> StreamingResponse:
        """Serve file with range request support."""
        try:
            # Parse range header
            ranges = self._parse_range_header(range_header, file_size)
            if not ranges:
                raise HTTPException(
                    status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE,
                    headers={"Content-Range": f"bytes */{file_size}"}
                )
            
            # For simplicity, only handle single range requests
            start, end = ranges[0]
            content_length = end - start + 1
            
            # Create streaming response
            async def range_streamer():
                async with aiofiles.open(path, 'rb') as f:
                    await f.seek(start)
                    remaining = content_length
                    
                    while remaining > 0:
                        chunk_size = min(8192, remaining)
                        chunk = await f.read(chunk_size)
                        if not chunk:
                            break
                        remaining -= len(chunk)
                        yield chunk
            
            # Prepare headers
            headers = {
                "Content-Range": f"bytes {start}-{end}/{file_size}",
                "Accept-Ranges": "bytes",
                "Content-Length": str(content_length),
                "ETag": f'"{etag}"',
                "Last-Modified": last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
            }
            
            # Add caching headers
            if enable_caching:
                cache_control = self.cache_control_headers.get(file_type, 'private, max-age=300')
                headers["Cache-Control"] = cache_control
            
            # Add content disposition
            disposition = "inline" if inline else "attachment"
            headers["Content-Disposition"] = f'{disposition}; filename="{original_filename}"'
            
            return StreamingResponse(
                range_streamer(),
                status_code=status.HTTP_206_PARTIAL_CONTENT,
                media_type=content_type,
                headers=headers
            )
            
        except Exception as e:
            logger.error(f"Failed to serve range request: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to serve range request"
            )
    
    async def _serve_full_file(
        self,
        path: Path,
        file_size: int,
        content_type: str,
        original_filename: str,
        inline: bool,
        enable_caching: bool,
        file_type: str,
        etag: str,
        last_modified: datetime
    ) -> StreamingResponse:
        """Serve full file."""
        async def file_streamer():
            async with aiofiles.open(path, 'rb') as f:
                while chunk := await f.read(8192):
                    yield chunk
        
        # Prepare headers
        headers = {
            "Content-Length": str(file_size),
            "Accept-Ranges": "bytes",
            "ETag": f'"{etag}"',
            "Last-Modified": last_modified.strftime('%a, %d %b %Y %H:%M:%S GMT')
        }
        
        # Add caching headers
        if enable_caching:
            cache_control = self.cache_control_headers.get(file_type, 'private, max-age=300')
            headers["Cache-Control"] = cache_control
        
        # Add content disposition
        disposition = "inline" if inline else "attachment"
        headers["Content-Disposition"] = f'{disposition}; filename="{original_filename}"'
        
        return StreamingResponse(
            file_streamer(),
            media_type=content_type,
            headers=headers
        )
    
    def _parse_range_header(self, range_header: str, file_size: int) -> Optional[list]:
        """Parse HTTP Range header."""
        try:
            if not range_header.startswith('bytes='):
                return None
            
            ranges = []
            range_specs = range_header[6:].split(',')
            
            for range_spec in range_specs:
                range_spec = range_spec.strip()
                
                if '-' not in range_spec:
                    continue
                
                start_str, end_str = range_spec.split('-', 1)
                
                # Handle different range formats
                if start_str and end_str:
                    # bytes=200-1023
                    start = int(start_str)
                    end = int(end_str)
                elif start_str:
                    # bytes=200-
                    start = int(start_str)
                    end = file_size - 1
                elif end_str:
                    # bytes=-500
                    start = file_size - int(end_str)
                    end = file_size - 1
                else:
                    continue
                
                # Validate range
                if start < 0 or end >= file_size or start > end:
                    continue
                
                ranges.append((start, end))
            
            return ranges if ranges else None
            
        except (ValueError, IndexError):
            return None
    
    def generate_file_url(
        self,
        file_id: str,
        file_type: str,
        inline: bool = False,
        expires_in: Optional[int] = None
    ) -> str:
        """
        Generate URL for file access.
        
        Args:
            file_id: File identifier
            file_type: Type of file
            inline: Whether to serve inline
            expires_in: Optional expiration time in seconds
            
        Returns:
            File access URL
        """
        base_url = f"/api/v1/files/{file_id}"
        
        # Add query parameters
        params = []
        if inline:
            params.append("inline=true")
        if expires_in:
            params.append(f"expires_in={expires_in}")
        
        if params:
            base_url += "?" + "&".join(params)
        
        return base_url
    
    def generate_thumbnail_url(self, file_id: str, size: str = "medium") -> str:
        """Generate thumbnail URL for image/video files."""
        return f"/api/v1/files/{file_id}/thumbnail?size={size}"
    
    def generate_streaming_url(self, file_id: str, quality: str = "auto") -> str:
        """Generate streaming URL for video files."""
        return f"/api/v1/files/{file_id}/stream?quality={quality}"


# Global file serving manager
file_serving_manager = FileServingManager()


# Utility functions
async def serve_file_secure(
    file_path: str,
    file_type: str,
    original_filename: str,
    request: Request,
    inline: bool = False,
    enable_caching: bool = True,
    user_id: Optional[str] = None
) -> StreamingResponse:
    """Serve file with security checks and optimizations."""
    return await file_serving_manager.serve_file(
        file_path=file_path,
        file_type=file_type,
        original_filename=original_filename,
        request=request,
        inline=inline,
        enable_caching=enable_caching,
        user_id=user_id
    )


def generate_secure_file_url(
    file_id: str,
    file_type: str,
    inline: bool = False,
    expires_in: Optional[int] = None
) -> str:
    """Generate secure file URL."""
    return file_serving_manager.generate_file_url(
        file_id=file_id,
        file_type=file_type,
        inline=inline,
        expires_in=expires_in
    )


def generate_thumbnail_url(file_id: str, size: str = "medium") -> str:
    """Generate thumbnail URL."""
    return file_serving_manager.generate_thumbnail_url(file_id, size)


def generate_streaming_url(file_id: str, quality: str = "auto") -> str:
    """Generate streaming URL."""
    return file_serving_manager.generate_streaming_url(file_id, quality)