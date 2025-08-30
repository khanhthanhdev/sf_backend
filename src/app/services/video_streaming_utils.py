"""
Video streaming utilities for advanced video playback and streaming features.

This module provides utilities for video streaming optimization, adaptive bitrate
streaming preparation, and video format conversion helpers.
"""

import logging
import asyncio
import os
import tempfile
from typing import Dict, Any, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from enum import Enum

import cv2
from PIL import Image

logger = logging.getLogger(__name__)


class StreamingQuality(Enum):
    """Video streaming quality levels."""
    LOW = "360p"
    MEDIUM = "720p"
    HIGH = "1080p"
    ULTRA = "4k"


class VideoCodec(Enum):
    """Supported video codecs."""
    H264 = "h264"
    H265 = "h265"
    VP9 = "vp9"
    AV1 = "av1"


@dataclass
class StreamingProfile:
    """Video streaming profile configuration."""
    quality: StreamingQuality
    width: int
    height: int
    bitrate_kbps: int
    codec: VideoCodec
    fps: int = 30


class VideoStreamingOptimizer:
    """
    Utility class for optimizing videos for streaming.
    
    Provides methods for video analysis, quality optimization,
    and streaming preparation.
    """
    
    # Predefined streaming profiles
    STREAMING_PROFILES = {
        StreamingQuality.LOW: StreamingProfile(
            quality=StreamingQuality.LOW,
            width=640,
            height=360,
            bitrate_kbps=800,
            codec=VideoCodec.H264,
            fps=30
        ),
        StreamingQuality.MEDIUM: StreamingProfile(
            quality=StreamingQuality.MEDIUM,
            width=1280,
            height=720,
            bitrate_kbps=2500,
            codec=VideoCodec.H264,
            fps=30
        ),
        StreamingQuality.HIGH: StreamingProfile(
            quality=StreamingQuality.HIGH,
            width=1920,
            height=1080,
            bitrate_kbps=5000,
            codec=VideoCodec.H264,
            fps=30
        ),
        StreamingQuality.ULTRA: StreamingProfile(
            quality=StreamingQuality.ULTRA,
            width=3840,
            height=2160,
            bitrate_kbps=15000,
            codec=VideoCodec.H265,
            fps=30
        )
    }
    
    @staticmethod
    async def analyze_video_for_streaming(video_path: str) -> Dict[str, Any]:
        """
        Analyze video file for streaming optimization recommendations.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dict containing analysis results and recommendations
        """
        loop = asyncio.get_event_loop()
        
        def _analyze_video():
            try:
                cap = cv2.VideoCapture(video_path)
                
                if not cap.isOpened():
                    return {'error': 'Could not open video file'}
                
                # Get video properties
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = frame_count / fps if fps > 0 else 0
                
                # Get file size
                file_size = os.path.getsize(video_path)
                
                # Calculate current bitrate
                current_bitrate_kbps = (file_size * 8) / (duration * 1000) if duration > 0 else 0
                
                cap.release()
                
                # Determine optimal streaming quality
                optimal_quality = VideoStreamingOptimizer._determine_optimal_quality(
                    width, height, current_bitrate_kbps
                )
                
                # Generate recommendations
                recommendations = VideoStreamingOptimizer._generate_streaming_recommendations(
                    width, height, fps, current_bitrate_kbps, duration
                )
                
                return {
                    'current_properties': {
                        'width': width,
                        'height': height,
                        'fps': fps,
                        'duration_seconds': duration,
                        'file_size_bytes': file_size,
                        'estimated_bitrate_kbps': current_bitrate_kbps
                    },
                    'optimal_quality': optimal_quality.value,
                    'recommendations': recommendations,
                    'streaming_profiles': {
                        quality.value: {
                            'width': profile.width,
                            'height': profile.height,
                            'bitrate_kbps': profile.bitrate_kbps,
                            'codec': profile.codec.value,
                            'fps': profile.fps
                        }
                        for quality, profile in VideoStreamingOptimizer.STREAMING_PROFILES.items()
                        if profile.width <= width and profile.height <= height
                    }
                }
                
            except Exception as e:
                logger.error(f"Failed to analyze video: {e}")
                return {'error': str(e)}
        
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, _analyze_video)
    
    @staticmethod
    def _determine_optimal_quality(width: int, height: int, bitrate_kbps: float) -> StreamingQuality:
        """Determine optimal streaming quality based on video properties."""
        if height >= 2160:
            return StreamingQuality.ULTRA
        elif height >= 1080:
            return StreamingQuality.HIGH
        elif height >= 720:
            return StreamingQuality.MEDIUM
        else:
            return StreamingQuality.LOW
    
    @staticmethod
    def _generate_streaming_recommendations(width: int, 
                                          height: int, 
                                          fps: float, 
                                          bitrate_kbps: float,
                                          duration: float) -> List[str]:
        """Generate streaming optimization recommendations."""
        recommendations = []
        
        # Bitrate recommendations
        optimal_profile = VideoStreamingOptimizer._determine_optimal_quality(width, height, bitrate_kbps)
        optimal_bitrate = VideoStreamingOptimizer.STREAMING_PROFILES[optimal_profile].bitrate_kbps
        
        if bitrate_kbps > optimal_bitrate * 1.5:
            recommendations.append(f"Consider reducing bitrate from {bitrate_kbps:.0f} to {optimal_bitrate} kbps")
        elif bitrate_kbps < optimal_bitrate * 0.5:
            recommendations.append(f"Consider increasing bitrate from {bitrate_kbps:.0f} to {optimal_bitrate} kbps")
        
        # FPS recommendations
        if fps > 60:
            recommendations.append("Consider reducing frame rate to 30 or 60 fps for better streaming")
        elif fps < 24:
            recommendations.append("Consider increasing frame rate to at least 24 fps")
        
        # Duration recommendations
        if duration > 3600:  # 1 hour
            recommendations.append("Consider splitting long videos into segments for better streaming")
        
        # Resolution recommendations
        if width > 3840 or height > 2160:
            recommendations.append("Consider creating lower resolution versions for mobile streaming")
        
        return recommendations


class ThumbnailGenerator:
    """
    Advanced thumbnail generation utility.
    
    Provides methods for generating multiple thumbnails, animated previews,
    and thumbnail optimization.
    """
    
    @staticmethod
    async def generate_smart_thumbnails(video_path: str, 
                                       count: int = 5,
                                       avoid_black_frames: bool = True) -> List[Dict[str, Any]]:
        """
        Generate smart thumbnails by analyzing video content.
        
        Args:
            video_path: Path to video file
            count: Number of thumbnails to generate
            avoid_black_frames: Whether to avoid black or dark frames
            
        Returns:
            List of thumbnail information dictionaries
        """
        loop = asyncio.get_event_loop()
        
        def _generate_thumbnails():
            try:
                cap = cv2.VideoCapture(video_path)
                
                if not cap.isOpened():
                    return []
                
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                duration = frame_count / fps if fps > 0 else 0
                
                thumbnails = []
                
                # Generate candidate timestamps
                candidate_timestamps = []
                for i in range(count * 3):  # Generate more candidates than needed
                    timestamp = (duration / (count * 3)) * (i + 1)
                    candidate_timestamps.append(timestamp)
                
                # Analyze frames and select best ones
                selected_frames = []
                
                for timestamp in candidate_timestamps:
                    frame_number = int(timestamp * fps)
                    cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
                    
                    ret, frame = cap.read()
                    if not ret:
                        continue
                    
                    # Calculate frame brightness and contrast
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    brightness = cv2.mean(gray)[0]
                    contrast = gray.std()
                    
                    # Skip very dark frames if requested
                    if avoid_black_frames and brightness < 30:
                        continue
                    
                    # Calculate frame score (higher is better)
                    score = brightness * 0.3 + contrast * 0.7
                    
                    selected_frames.append({
                        'timestamp': timestamp,
                        'frame_number': frame_number,
                        'frame': frame.copy(),
                        'score': score,
                        'brightness': brightness,
                        'contrast': contrast
                    })
                
                # Sort by score and select top frames
                selected_frames.sort(key=lambda x: x['score'], reverse=True)
                selected_frames = selected_frames[:count]
                
                # Sort selected frames by timestamp
                selected_frames.sort(key=lambda x: x['timestamp'])
                
                # Save thumbnails
                for i, frame_info in enumerate(selected_frames):
                    thumbnail_path = f"/tmp/thumbnail_{i}_{frame_info['timestamp']:.1f}s.jpg"
                    
                    # Resize frame for thumbnail
                    height, width = frame_info['frame'].shape[:2]
                    if width > 320:
                        scale = 320 / width
                        new_width = 320
                        new_height = int(height * scale)
                        resized_frame = cv2.resize(frame_info['frame'], (new_width, new_height))
                    else:
                        resized_frame = frame_info['frame']
                    
                    # Save thumbnail
                    cv2.imwrite(thumbnail_path, resized_frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    
                    thumbnails.append({
                        'timestamp_seconds': frame_info['timestamp'],
                        'file_path': thumbnail_path,
                        'width': resized_frame.shape[1],
                        'height': resized_frame.shape[0],
                        'quality_score': frame_info['score'],
                        'brightness': frame_info['brightness'],
                        'contrast': frame_info['contrast']
                    })
                
                cap.release()
                return thumbnails
                
            except Exception as e:
                logger.error(f"Failed to generate smart thumbnails: {e}")
                return []
        
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, _generate_thumbnails)
    
    @staticmethod
    async def create_thumbnail_sprite(thumbnails: List[str], 
                                     output_path: str,
                                     columns: int = 5) -> Dict[str, Any]:
        """
        Create a thumbnail sprite sheet from individual thumbnails.
        
        Args:
            thumbnails: List of thumbnail file paths
            output_path: Output path for sprite sheet
            columns: Number of columns in sprite sheet
            
        Returns:
            Dict containing sprite sheet information
        """
        loop = asyncio.get_event_loop()
        
        def _create_sprite():
            try:
                if not thumbnails:
                    return {'error': 'No thumbnails provided'}
                
                # Load first thumbnail to get dimensions
                first_img = Image.open(thumbnails[0])
                thumb_width, thumb_height = first_img.size
                first_img.close()
                
                # Calculate sprite dimensions
                rows = (len(thumbnails) + columns - 1) // columns
                sprite_width = thumb_width * columns
                sprite_height = thumb_height * rows
                
                # Create sprite sheet
                sprite = Image.new('RGB', (sprite_width, sprite_height), (0, 0, 0))
                
                thumbnail_positions = []
                
                for i, thumb_path in enumerate(thumbnails):
                    if not os.path.exists(thumb_path):
                        continue
                    
                    row = i // columns
                    col = i % columns
                    
                    x = col * thumb_width
                    y = row * thumb_height
                    
                    # Load and paste thumbnail
                    thumb_img = Image.open(thumb_path)
                    sprite.paste(thumb_img, (x, y))
                    thumb_img.close()
                    
                    thumbnail_positions.append({
                        'index': i,
                        'x': x,
                        'y': y,
                        'width': thumb_width,
                        'height': thumb_height
                    })
                
                # Save sprite sheet
                sprite.save(output_path, 'JPEG', quality=85)
                sprite.close()
                
                return {
                    'sprite_path': output_path,
                    'sprite_width': sprite_width,
                    'sprite_height': sprite_height,
                    'thumbnail_width': thumb_width,
                    'thumbnail_height': thumb_height,
                    'columns': columns,
                    'rows': rows,
                    'thumbnail_count': len(thumbnails),
                    'positions': thumbnail_positions
                }
                
            except Exception as e:
                logger.error(f"Failed to create thumbnail sprite: {e}")
                return {'error': str(e)}
        
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, _create_sprite)


class VideoMetadataExtractor:
    """
    Advanced video metadata extraction utility.
    
    Provides detailed video analysis including codec information,
    color space, audio tracks, and technical specifications.
    """
    
    @staticmethod
    async def extract_comprehensive_metadata(video_path: str) -> Dict[str, Any]:
        """
        Extract comprehensive video metadata.
        
        Args:
            video_path: Path to video file
            
        Returns:
            Dict containing detailed metadata
        """
        loop = asyncio.get_event_loop()
        
        def _extract_metadata():
            try:
                cap = cv2.VideoCapture(video_path)
                
                if not cap.isOpened():
                    return {'error': 'Could not open video file'}
                
                # Basic properties
                width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fps = cap.get(cv2.CAP_PROP_FPS)
                frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                duration = frame_count / fps if fps > 0 else 0
                
                # File properties
                file_size = os.path.getsize(video_path)
                file_name = os.path.basename(video_path)
                file_ext = os.path.splitext(file_name)[1].lower()
                
                # Calculate bitrate
                bitrate_bps = (file_size * 8) / duration if duration > 0 else 0
                bitrate_kbps = bitrate_bps / 1000
                
                # Analyze first few frames for color information
                color_analysis = VideoMetadataExtractor._analyze_color_properties(cap)
                
                cap.release()
                
                # Determine video codec (basic detection)
                codec_info = VideoMetadataExtractor._detect_codec_info(video_path)
                
                return {
                    'file_info': {
                        'filename': file_name,
                        'extension': file_ext,
                        'size_bytes': file_size,
                        'size_mb': round(file_size / (1024 * 1024), 2)
                    },
                    'video_properties': {
                        'width': width,
                        'height': height,
                        'fps': fps,
                        'frame_count': frame_count,
                        'duration_seconds': duration,
                        'duration_formatted': VideoMetadataExtractor._format_duration(duration),
                        'aspect_ratio': VideoMetadataExtractor._calculate_aspect_ratio(width, height),
                        'resolution_category': VideoMetadataExtractor._categorize_resolution(width, height)
                    },
                    'bitrate_info': {
                        'bitrate_bps': bitrate_bps,
                        'bitrate_kbps': bitrate_kbps,
                        'bitrate_mbps': bitrate_kbps / 1000
                    },
                    'codec_info': codec_info,
                    'color_analysis': color_analysis,
                    'streaming_suitability': VideoMetadataExtractor._assess_streaming_suitability(
                        width, height, fps, bitrate_kbps, duration
                    )
                }
                
            except Exception as e:
                logger.error(f"Failed to extract comprehensive metadata: {e}")
                return {'error': str(e)}
        
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, _extract_metadata)
    
    @staticmethod
    def _analyze_color_properties(cap: cv2.VideoCapture) -> Dict[str, Any]:
        """Analyze color properties of video frames."""
        try:
            # Sample a few frames
            frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            sample_frames = min(10, frame_count)
            
            brightness_values = []
            contrast_values = []
            color_ranges = []
            
            for i in range(sample_frames):
                frame_pos = (frame_count // sample_frames) * i
                cap.set(cv2.CAP_PROP_POS_FRAMES, frame_pos)
                
                ret, frame = cap.read()
                if not ret:
                    continue
                
                # Convert to different color spaces for analysis
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
                
                # Calculate brightness and contrast
                brightness = cv2.mean(gray)[0]
                contrast = gray.std()
                
                brightness_values.append(brightness)
                contrast_values.append(contrast)
                
                # Analyze color range
                color_range = {
                    'hue_range': hsv[:, :, 0].max() - hsv[:, :, 0].min(),
                    'saturation_avg': cv2.mean(hsv[:, :, 1])[0],
                    'value_avg': cv2.mean(hsv[:, :, 2])[0]
                }
                color_ranges.append(color_range)
            
            return {
                'average_brightness': sum(brightness_values) / len(brightness_values) if brightness_values else 0,
                'average_contrast': sum(contrast_values) / len(contrast_values) if contrast_values else 0,
                'brightness_range': {
                    'min': min(brightness_values) if brightness_values else 0,
                    'max': max(brightness_values) if brightness_values else 0
                },
                'color_diversity': sum(cr['hue_range'] for cr in color_ranges) / len(color_ranges) if color_ranges else 0,
                'average_saturation': sum(cr['saturation_avg'] for cr in color_ranges) / len(color_ranges) if color_ranges else 0
            }
            
        except Exception as e:
            logger.error(f"Failed to analyze color properties: {e}")
            return {}
    
    @staticmethod
    def _detect_codec_info(video_path: str) -> Dict[str, Any]:
        """Detect video codec information (basic implementation)."""
        try:
            # This is a simplified codec detection
            # In a production environment, you might use ffprobe or similar tools
            file_ext = os.path.splitext(video_path)[1].lower()
            
            codec_mapping = {
                '.mp4': 'H.264/AVC',
                '.avi': 'Various',
                '.mov': 'H.264/HEVC',
                '.mkv': 'Various',
                '.webm': 'VP8/VP9'
            }
            
            return {
                'container_format': file_ext[1:] if file_ext else 'unknown',
                'likely_codec': codec_mapping.get(file_ext, 'unknown'),
                'detection_method': 'file_extension'
            }
            
        except Exception as e:
            return {'error': str(e)}
    
    @staticmethod
    def _format_duration(seconds: float) -> str:
        """Format duration in HH:MM:SS format."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        else:
            return f"{minutes:02d}:{secs:02d}"
    
    @staticmethod
    def _calculate_aspect_ratio(width: int, height: int) -> str:
        """Calculate and format aspect ratio."""
        def gcd(a, b):
            while b:
                a, b = b, a % b
            return a
        
        divisor = gcd(width, height)
        ratio_w = width // divisor
        ratio_h = height // divisor
        
        # Common aspect ratios
        common_ratios = {
            (16, 9): "16:9",
            (4, 3): "4:3",
            (21, 9): "21:9",
            (1, 1): "1:1",
            (3, 2): "3:2"
        }
        
        return common_ratios.get((ratio_w, ratio_h), f"{ratio_w}:{ratio_h}")
    
    @staticmethod
    def _categorize_resolution(width: int, height: int) -> str:
        """Categorize video resolution."""
        if height >= 2160:
            return "4K/UHD"
        elif height >= 1440:
            return "2K/QHD"
        elif height >= 1080:
            return "Full HD"
        elif height >= 720:
            return "HD"
        elif height >= 480:
            return "SD"
        else:
            return "Low Resolution"
    
    @staticmethod
    def _assess_streaming_suitability(width: int, 
                                    height: int, 
                                    fps: float, 
                                    bitrate_kbps: float,
                                    duration: float) -> Dict[str, Any]:
        """Assess video suitability for streaming."""
        suitability_score = 100
        issues = []
        recommendations = []
        
        # Check resolution
        if height > 2160:
            suitability_score -= 20
            issues.append("Very high resolution may cause streaming issues")
            recommendations.append("Consider creating lower resolution versions")
        
        # Check bitrate
        if bitrate_kbps > 10000:
            suitability_score -= 15
            issues.append("High bitrate may cause buffering")
            recommendations.append("Consider reducing bitrate")
        elif bitrate_kbps < 500:
            suitability_score -= 10
            issues.append("Low bitrate may result in poor quality")
        
        # Check frame rate
        if fps > 60:
            suitability_score -= 10
            issues.append("High frame rate increases bandwidth requirements")
        elif fps < 24:
            suitability_score -= 15
            issues.append("Low frame rate may appear choppy")
        
        # Check duration
        if duration > 7200:  # 2 hours
            suitability_score -= 10
            issues.append("Very long duration may cause streaming timeouts")
            recommendations.append("Consider splitting into segments")
        
        # Determine overall rating
        if suitability_score >= 90:
            rating = "Excellent"
        elif suitability_score >= 75:
            rating = "Good"
        elif suitability_score >= 60:
            rating = "Fair"
        else:
            rating = "Poor"
        
        return {
            'score': max(0, suitability_score),
            'rating': rating,
            'issues': issues,
            'recommendations': recommendations
        }