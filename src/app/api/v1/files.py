"""
File management API endpoints.

This module implements REST API endpoints for file operations including
upload, download, metadata retrieval, and file management.
"""

import logging
from typing import Optional, List, Dict, Any
from pathlib import Path

from fastapi import (
    APIRouter, Depends, HTTPException, status, UploadFile, File, Form,
    Request, Response, Query
)
from fastapi.responses import StreamingResponse, FileResponse
from redis.asyncio import Redis
import aiofiles

from ...core.redis import get_redis
from ...core.auth import verify_clerk_token
from ...models.file import (
    FileUploadRequest, FileUploadResponse, FileMetadataResponse,
    FileListResponse, FileStatsResponse, FileCleanupRequest,
    FileCleanupResponse, FileType, FileBatchUploadRequest,
    FileBatchUploadResponse, FileSearchRequest
)
from ...models.common import PaginatedResponse
from ...services.file_service import FileService
from ...api.dependencies import get_current_user, get_file_service
from ...utils.file_utils import FileMetadata

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/files", tags=["files"])


@router.post("/upload", response_model=FileUploadResponse, status_code=status.HTTP_201_CREATED)
async def upload_file(
    file: UploadFile = File(..., description="File to upload"),
    file_type: Optional[FileType] = Form(None, description="File type category"),
    subdirectory: Optional[str] = Form(None, description="Optional subdirectory"),
    description: Optional[str] = Form(None, description="File description"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> FileUploadResponse:
    """
    Upload a single file.
    
    This endpoint accepts a file upload with optional metadata and stores it
    securely with proper validation and access controls.
    
    Args:
        file: File to upload
        file_type: Optional file type category
        subdirectory: Optional subdirectory for organization
        description: Optional file description
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        FileUploadResponse with upload details
        
    Raises:
        HTTPException: If upload fails or validation errors occur
    """
    try:
        logger.info(
            "Starting file upload",
            filename=file.filename,
            content_type=file.content_type,
            user_id=current_user["user_info"]["id"],
            file_type=file_type
        )
        
        # Upload file
        file_metadata = await file_service.upload_file(
            file=file,
            user_id=current_user["user_info"]["id"],
            file_type=file_type.value if file_type else None,
            subdirectory=subdirectory
        )
        
        # Generate download URL
        download_url = await file_service.generate_download_url(
            file_id=Path(file_metadata.filename).stem,
            user_id=current_user["user_info"]["id"]
        )
        
        logger.info(
            "File uploaded successfully",
            file_id=Path(file_metadata.filename).stem,
            filename=file_metadata.filename,
            file_size=file_metadata.file_size,
            user_id=current_user["user_info"]["id"]
        )
        
        return FileUploadResponse(
            file_id=Path(file_metadata.filename).stem,
            filename=file_metadata.filename,
            file_type=FileType(file_metadata.file_type),
            file_size=file_metadata.file_size,
            download_url=download_url or f"/api/v1/files/{Path(file_metadata.filename).stem}/download",
            created_at=file_metadata.created_at
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to upload file",
            filename=file.filename,
            user_id=current_user["user_info"]["id"],
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to upload file: {str(e)}"
        )


@router.post("/batch-upload", response_model=FileBatchUploadResponse)
async def batch_upload_files(
    files: List[UploadFile] = File(..., description="Files to upload"),
    file_type: Optional[FileType] = Form(None, description="File type for all files"),
    subdirectory: Optional[str] = Form(None, description="Subdirectory for all files"),
    description: Optional[str] = Form(None, description="Description for all files"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> FileBatchUploadResponse:
    """
    Upload multiple files in batch.
    
    Args:
        files: List of files to upload
        file_type: Optional file type for all files
        subdirectory: Optional subdirectory for all files
        description: Optional description for all files
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        FileBatchUploadResponse with batch upload results
    """
    try:
        if len(files) > 50:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Maximum 50 files allowed per batch"
            )
        
        successful_uploads = []
        failed_uploads = []
        
        logger.info(
            "Starting batch file upload",
            file_count=len(files),
            user_id=current_user["user_info"]["id"]
        )
        
        for file in files:
            try:
                # Upload individual file
                file_metadata = await file_service.upload_file(
                    file=file,
                    user_id=current_user["user_info"]["id"],
                    file_type=file_type.value if file_type else None,
                    subdirectory=subdirectory
                )
                
                # Generate download URL
                download_url = await file_service.generate_download_url(
                    file_id=Path(file_metadata.filename).stem,
                    user_id=current_user["user_info"]["id"]
                )
                
                successful_uploads.append(FileUploadResponse(
                    file_id=Path(file_metadata.filename).stem,
                    filename=file_metadata.filename,
                    file_type=FileType(file_metadata.file_type),
                    file_size=file_metadata.file_size,
                    download_url=download_url or f"/api/v1/files/{Path(file_metadata.filename).stem}/download",
                    created_at=file_metadata.created_at
                ))
                
            except Exception as e:
                failed_uploads.append({
                    "filename": file.filename,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
        
        logger.info(
            "Batch upload completed",
            total_files=len(files),
            successful=len(successful_uploads),
            failed=len(failed_uploads),
            user_id=current_user["user_info"]["id"]
        )
        
        return FileBatchUploadResponse(
            successful_uploads=successful_uploads,
            failed_uploads=failed_uploads,
            total_files=len(files),
            success_count=len(successful_uploads),
            failure_count=len(failed_uploads)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Batch upload failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Batch upload failed: {str(e)}"
        )


@router.get("/{file_id}/download")
async def download_file(
    file_id: str,
    request: Request,
    inline: bool = Query(False, description="Serve file inline instead of attachment"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> StreamingResponse:
    """
    Download a file by ID with range request support and caching.
    
    Args:
        file_id: File identifier
        request: FastAPI request object
        inline: Whether to serve inline or as attachment
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        StreamingResponse with file content
        
    Raises:
        HTTPException: If file not found or access denied
    """
    try:
        # Get file metadata
        file_metadata = await file_service.get_file_metadata(
            file_id=file_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not file_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        logger.info(
            "Serving file download",
            file_id=file_id,
            filename=file_metadata.filename,
            user_id=current_user["user_info"]["id"],
            inline=inline
        )
        
        # Track file access
        from ...utils.file_cache import track_file_access
        await track_file_access(
            file_id=file_id,
            user_id=current_user["user_info"]["id"],
            access_type="download"
        )
        
        # Use enhanced file serving with user context
        from ...utils.file_serving import serve_file_secure
        
        return await serve_file_secure(
            file_path=file_metadata.file_path,
            file_type=file_metadata.file_type,
            original_filename=file_metadata.original_filename,
            request=request,
            inline=inline,
            enable_caching=True,
            user_id=current_user["user_info"]["id"]
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to download file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to download file: {str(e)}"
        )


@router.get("/{file_id}/metadata", response_model=FileMetadataResponse)
async def get_file_metadata(
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> FileMetadataResponse:
    """
    Get file metadata by ID.
    
    Args:
        file_id: File identifier
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        FileMetadataResponse with file metadata
        
    Raises:
        HTTPException: If file not found or access denied
    """
    try:
        file_metadata = await file_service.get_file_metadata(
            file_id=file_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not file_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Generate download URL
        download_url = await file_service.generate_download_url(
            file_id=file_id,
            user_id=current_user["user_info"]["id"]
        )
        
        return FileMetadataResponse(
            id=file_id,
            filename=file_metadata.filename,
            original_filename=file_metadata.original_filename,
            file_type=FileType(file_metadata.file_type),
            mime_type=file_metadata.mime_type,
            file_size=file_metadata.file_size,
            checksum=file_metadata.checksum,
            created_at=file_metadata.created_at,
            download_url=download_url,
            metadata=file_metadata.metadata
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file metadata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file metadata: {str(e)}"
        )


@router.get("", response_model=FileListResponse)
async def list_files(
    file_type: Optional[FileType] = Query(None, description="Filter by file type"),
    page: int = Query(1, ge=1, description="Page number"),
    items_per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> FileListResponse:
    """
    List user's files with pagination and filtering.
    
    Args:
        file_type: Optional file type filter
        page: Page number
        items_per_page: Items per page
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        FileListResponse with paginated file list
    """
    try:
        # Get paginated files
        paginated_response = await file_service.get_user_files(
            user_id=current_user["user_info"]["id"],
            file_type=file_type.value if file_type else None,
            page=page,
            items_per_page=items_per_page
        )
        
        # Convert to response format
        files = []
        for file_metadata in paginated_response.data:
            download_url = await file_service.generate_download_url(
                file_id=Path(file_metadata.filename).stem,
                user_id=current_user["user_info"]["id"]
            )
            
            files.append(FileMetadataResponse(
                id=Path(file_metadata.filename).stem,
                filename=file_metadata.filename,
                original_filename=file_metadata.original_filename,
                file_type=FileType(file_metadata.file_type),
                mime_type=file_metadata.mime_type,
                file_size=file_metadata.file_size,
                checksum=file_metadata.checksum,
                created_at=file_metadata.created_at,
                download_url=download_url,
                metadata=file_metadata.metadata
            ))
        
        return FileListResponse(
            files=files,
            total_count=paginated_response.total_count,
            page=page,
            items_per_page=items_per_page,
            has_next=page * items_per_page < paginated_response.total_count,
            has_previous=page > 1
        )
        
    except Exception as e:
        logger.error(f"Failed to list files: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list files: {str(e)}"
        )


@router.delete("/{file_id}")
async def delete_file(
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> Dict[str, Any]:
    """
    Delete a file by ID.
    
    Args:
        file_id: File identifier
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        Success message
        
    Raises:
        HTTPException: If file not found or deletion fails
    """
    try:
        success = await file_service.delete_file(
            file_id=file_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found or already deleted"
            )
        
        logger.info(
            "File deleted successfully",
            file_id=file_id,
            user_id=current_user["user_info"]["id"]
        )
        
        return {"message": "File deleted successfully", "file_id": file_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete file: {str(e)}"
        )


@router.get("/stats", response_model=FileStatsResponse)
async def get_file_stats(
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> FileStatsResponse:
    """
    Get file statistics for the current user.
    
    Args:
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        FileStatsResponse with user's file statistics
    """
    try:
        stats = await file_service.get_file_stats(
            user_id=current_user["user_info"]["id"]
        )
        
        return FileStatsResponse(
            total_files=stats.get("total_files", 0),
            total_size=stats.get("total_size", 0),
            by_type=stats.get("by_type", {}),
            recent_uploads=stats.get("recent_uploads", 0)
        )
        
    except Exception as e:
        logger.error(f"Failed to get file stats: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file stats: {str(e)}"
        )


@router.post("/cleanup", response_model=FileCleanupResponse)
async def cleanup_files(
    request: FileCleanupRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> FileCleanupResponse:
    """
    Clean up old files (admin only).
    
    Args:
        request: Cleanup request parameters
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        FileCleanupResponse with cleanup results
        
    Raises:
        HTTPException: If user is not admin or cleanup fails
    """
    try:
        # Check if user is admin (you may need to implement admin role checking)
        user_roles = current_user.get("user_info", {}).get("roles", [])
        if "admin" not in user_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Admin access required"
            )
        
        if request.dry_run:
            # For dry run, just return what would be cleaned
            return FileCleanupResponse(
                files_cleaned=0,
                metadata_cleaned=0,
                retention_days=request.retention_days,
                dry_run=True
            )
        
        # Perform cleanup
        cleanup_stats = await file_service.cleanup_expired_files(
            retention_days=request.retention_days
        )
        
        logger.info(
            "File cleanup completed",
            **cleanup_stats,
            user_id=current_user["user_info"]["id"]
        )
        
        return FileCleanupResponse(
            files_cleaned=cleanup_stats.get("files_cleaned", 0),
            metadata_cleaned=cleanup_stats.get("metadata_cleaned", 0),
            retention_days=request.retention_days,
            dry_run=False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cleanup files: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup files: {str(e)}"
        )


@router.get("/{file_id}/thumbnail")
async def get_file_thumbnail(
    file_id: str,
    size: str = Query("medium", pattern="^(small|medium|large)$", description="Thumbnail size"),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> StreamingResponse:
    """
    Get thumbnail for image or video file.
    
    Args:
        file_id: File identifier
        size: Thumbnail size (small, medium, large)
        request: FastAPI request object
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        StreamingResponse with thumbnail image
        
    Raises:
        HTTPException: If file not found or thumbnail not available
    """
    try:
        # Get file metadata
        file_metadata = await file_service.get_file_metadata(
            file_id=file_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not file_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check if file type supports thumbnails
        if file_metadata.file_type not in ['image', 'video']:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Thumbnails not available for this file type"
            )
        
        # For now, return a placeholder response
        # In a real implementation, you would generate/serve actual thumbnails
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="Thumbnail generation not yet implemented"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get thumbnail: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get thumbnail: {str(e)}"
        )


@router.get("/{file_id}/stream")
async def stream_file(
    file_id: str,
    quality: str = Query("auto", description="Stream quality"),
    request: Request = None,
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> StreamingResponse:
    """
    Stream video or audio file with adaptive quality.
    
    Args:
        file_id: File identifier
        quality: Stream quality setting
        request: FastAPI request object
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        StreamingResponse with media stream
        
    Raises:
        HTTPException: If file not found or streaming not supported
    """
    try:
        # Get file metadata
        file_metadata = await file_service.get_file_metadata(
            file_id=file_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not file_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Check if file type supports streaming
        if file_metadata.file_type not in ['video', 'audio']:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Streaming not available for this file type"
            )
        
        logger.info(
            "Serving file stream",
            file_id=file_id,
            filename=file_metadata.filename,
            quality=quality,
            user_id=current_user["user_info"]["id"]
        )
        
        # Track file access
        from ...utils.file_cache import track_file_access
        await track_file_access(
            file_id=file_id,
            user_id=current_user["user_info"]["id"],
            access_type="stream"
        )
        
        # Use enhanced file serving with inline=True for streaming
        from ...utils.file_serving import serve_file_secure
        
        return await serve_file_secure(
            file_path=file_metadata.file_path,
            file_type=file_metadata.file_type,
            original_filename=file_metadata.original_filename,
            request=request,
            inline=True,  # Serve inline for streaming
            enable_caching=True
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to stream file: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream file: {str(e)}"
        )


@router.get("/{file_id}/info")
async def get_file_info(
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> Dict[str, Any]:
    """
    Get comprehensive file information including URLs.
    
    Args:
        file_id: File identifier
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        Dictionary with file information and access URLs
        
    Raises:
        HTTPException: If file not found or access denied
    """
    try:
        file_metadata = await file_service.get_file_metadata(
            file_id=file_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not file_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Generate various URLs
        from ...utils.file_serving import (
            generate_secure_file_url,
            generate_thumbnail_url,
            generate_streaming_url
        )
        
        urls = {
            "download": generate_secure_file_url(file_id, file_metadata.file_type),
            "download_inline": generate_secure_file_url(file_id, file_metadata.file_type, inline=True),
        }
        
        # Add type-specific URLs
        if file_metadata.file_type in ['image', 'video']:
            urls["thumbnail_small"] = generate_thumbnail_url(file_id, "small")
            urls["thumbnail_medium"] = generate_thumbnail_url(file_id, "medium")
            urls["thumbnail_large"] = generate_thumbnail_url(file_id, "large")
        
        if file_metadata.file_type in ['video', 'audio']:
            urls["stream"] = generate_streaming_url(file_id)
        
        return {
            "file_id": file_id,
            "filename": file_metadata.filename,
            "original_filename": file_metadata.original_filename,
            "file_type": file_metadata.file_type,
            "mime_type": file_metadata.mime_type,
            "file_size": file_metadata.file_size,
            "created_at": file_metadata.created_at.isoformat(),
            "metadata": file_metadata.metadata,
            "urls": urls
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file info: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file info: {str(e)}"
        )


@router.get("/{file_id}/analytics")
async def get_file_analytics(
    file_id: str,
    current_user: Dict[str, Any] = Depends(get_current_user),
    file_service: FileService = Depends(get_file_service)
) -> Dict[str, Any]:
    """
    Get file access analytics and statistics.
    
    Args:
        file_id: File identifier
        current_user: Authenticated user information
        file_service: File service dependency
        
    Returns:
        Dictionary with file analytics
        
    Raises:
        HTTPException: If file not found or access denied
    """
    try:
        # Verify file ownership
        file_metadata = await file_service.get_file_metadata(
            file_id=file_id,
            user_id=current_user["user_info"]["id"]
        )
        
        if not file_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        # Get access statistics
        from ...utils.file_cache import get_file_access_statistics
        access_stats = await get_file_access_statistics(file_id)
        
        return {
            "file_id": file_id,
            "filename": file_metadata.filename,
            "access_statistics": access_stats,
            "file_size": file_metadata.file_size,
            "created_at": file_metadata.created_at.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get file analytics: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get file analytics: {str(e)}"
        )


@router.get("/{file_id}/secure")
async def secure_file_access(
    file_id: str,
    request: Request,
    user_id: str = Query(..., description="User ID from signed URL"),
    expires: str = Query(..., description="Expiration timestamp"),
    signature: str = Query(..., description="URL signature"),
    file_type: Optional[str] = Query(None, description="File type"),
    inline: Optional[str] = Query("false", description="Serve inline"),
    size: Optional[str] = Query(None, description="Thumbnail size"),
    quality: Optional[str] = Query(None, description="Stream quality"),
    file_service: FileService = Depends(get_file_service)
) -> StreamingResponse:
    """
    Secure file access endpoint using signed URLs.
    
    This endpoint provides secure file access without requiring authentication
    headers, using signed URLs with expiration and integrity verification.
    
    Args:
        file_id: File identifier
        request: FastAPI request object
        user_id: User ID from signed URL
        expires: Expiration timestamp
        signature: URL signature for verification
        file_type: Optional file type
        inline: Whether to serve inline
        size: Thumbnail size (for thumbnails)
        quality: Stream quality (for streaming)
        file_service: File service dependency
        
    Returns:
        StreamingResponse with file content
        
    Raises:
        HTTPException: If URL is invalid, expired, or file not found
    """
    try:
        # Verify signed URL
        from ...utils.secure_url_generator import verify_url_signature
        
        params = {
            'user_id': user_id,
            'expires': expires,
            'signature': signature
        }
        
        if file_type:
            params['file_type'] = file_type
        if inline:
            params['inline'] = inline
        if size:
            params['size'] = size
        if quality:
            params['quality'] = quality
        
        verification_result = verify_url_signature(file_id, params)
        
        if not verification_result['valid']:
            logger.warning(
                "Invalid signed URL access attempt",
                file_id=file_id,
                user_id=user_id,
                error=verification_result['error']
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Invalid URL: {verification_result['error']}"
            )
        
        # Get file metadata
        file_metadata = await file_service.get_file_metadata(
            file_id=file_id,
            user_id=verification_result['user_id']
        )
        
        if not file_metadata:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="File not found"
            )
        
        logger.info(
            "Serving secure file access",
            file_id=file_id,
            user_id=verification_result['user_id'],
            file_type=verification_result.get('file_type'),
            inline=verification_result['inline']
        )
        
        # Track file access
        from ...utils.file_cache import track_file_access
        access_type = "download"
        if verification_result.get('file_type') == "thumbnail":
            access_type = "thumbnail"
        elif verification_result.get('file_type') == "stream":
            access_type = "stream"
        
        await track_file_access(
            file_id=file_id,
            user_id=verification_result['user_id'],
            access_type=access_type
        )
        
        # Serve file using enhanced file serving
        from ...utils.file_serving import serve_file_secure
        
        return await serve_file_secure(
            file_path=file_metadata.file_path,
            file_type=file_metadata.file_type,
            original_filename=file_metadata.original_filename,
            request=request,
            inline=verification_result['inline'],
            enable_caching=True,
            user_id=verification_result['user_id']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            "Failed to serve secure file access",
            file_id=file_id,
            user_id=user_id,
            error=str(e),
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to serve file: {str(e)}"
        )