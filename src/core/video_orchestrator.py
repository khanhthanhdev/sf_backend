
import os
import asyncio
import logging
import uuid
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

# Import from correct locations (relative to src directory)
from .video_planner import VideoPlanner
from .video_renderer import OptimizedVideoRenderer  
from .storage_manager import StorageManager, StorageMode
from .code_generator import CodeGenerator

logger = logging.getLogger(__name__)


class VideoGenerationStatus(str, Enum):
    """Video generation status enumeration."""
    PENDING = "pending"
    PLANNING = "planning"
    GENERATING = "generating"
    RENDERING = "rendering"
    COMBINING = "combining"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class VideoGenerationResult:
    """Result of video generation process."""
    success: bool
    topic: str
    job_id: Optional[str] = None
    scene_results: List[Dict[str, Any]] = None
    combined_video_path: Optional[str] = None
    combined_video_upload: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = None
    status: VideoGenerationStatus = VideoGenerationStatus.PENDING
    
    def __post_init__(self):
        if self.scene_results is None:
            self.scene_results = []
        if self.metadata is None:
            self.metadata = {}


@dataclass
class VideoGenerationConfig:
    """Configuration for video generation."""
    planner_model: Any
    scene_model: Any
    helper_model: Optional[Any] = None
    user_id: Optional[str] = None
    job_id: Optional[str] = None
    session_id: Optional[str] = None
    output_dir: str = "output"
    storage_mode: str = "local_only"
    enable_s3_upload: bool = False
    cleanup_local_files: bool = False
    use_rag: bool = False
    use_context_learning: bool = False
    use_visual_fix_code: bool = False
    quality: str = "medium"
    max_retries: int = 3
    progress_callback: Optional[Callable[[str, float, str], None]] = None


class VideoGenerationOrchestrator:
    """High-level orchestrator for video generation pipeline."""
    
    def __init__(self, config: VideoGenerationConfig):
        """Initialize the orchestrator with configuration."""
        self.config = config
        
        # Initialize session ID if not provided
        if not self.config.session_id:
            self.config.session_id = str(uuid.uuid4())
        
        # Initialize storage manager
        storage_mode_enum = StorageMode.from_string(config.storage_mode)
        self.storage_manager = StorageManager(
            storage_mode=storage_mode_enum,
            enable_s3_upload=config.enable_s3_upload,
            cleanup_local_files=config.cleanup_local_files
        )
        
        # Initialize video planner
        self.video_planner = VideoPlanner(
            planner_model=config.planner_model,
            scene_model=config.scene_model,
            helper_model=config.helper_model,
            use_rag=config.use_rag,
            use_context_learning=config.use_context_learning
        )
        
        # Initialize code generator
        self.code_generator = CodeGenerator()
        
        # Initialize video renderer
        self.video_renderer = OptimizedVideoRenderer(
            output_dir=self.config.output_dir,
            use_visual_fix_code=self.config.use_visual_fix_code,
            default_quality=self.config.quality,
            storage_manager=self.storage_manager,
            enable_s3_upload=self.config.enable_s3_upload,
            user_id=self.config.user_id,
            job_id=self.config.job_id
        )
    
    async def generate_video(self, 
                           topic: str, 
                           description: str) -> VideoGenerationResult:
        """Generate a complete video from topic and description.
        
        Args:
            topic: Video topic/title
            description: Video description/context
            
        Returns:
            VideoGenerationResult with generation status and metadata
        """
        try:
            result = VideoGenerationResult(
                success=False,
                topic=topic,
                job_id=self.config.job_id,
                scene_results=[],
                metadata={}
            )
            
            # Step 1: Generate scene outline
            self._update_progress("scene_planning", 10, "Generating scene outline...")
            
            scene_outline = await self.video_planner.generate_scene_outline(
                topic=topic,
                description=description,
                session_id=self.config.session_id
            )
            
            # Step 2: Generate scene implementations
            self._update_progress("scene_implementation", 30, "Generating scene implementations...")
            
            scene_implementations = await self.video_planner.generate_scene_implementation_concurrently_enhanced(
                topic=topic,
                description=description,
                plan=scene_outline,
                session_id=self.config.session_id
            )
            
            # Step 3: Generate and render scenes
            self._update_progress("scene_generation", 50, "Generating and rendering scenes...")
            
            scene_results = await self._generate_and_render_scenes(
                topic=topic,
                description=description,
                scene_outline=scene_outline,
                scene_implementations=scene_implementations
            )
            
            result.scene_results = scene_results
            
            # Step 4: Combine videos
            self._update_progress("video_combination", 80, "Combining videos...")
            
            combined_video_info = await self._combine_videos(topic, scene_results)
            result.combined_video_path = combined_video_info.get('local_path')
            result.combined_video_upload = combined_video_info.get('upload_result')
            
            # Step 5: Complete
            self._update_progress("completed", 100, "Video generation completed")
            
            result.success = True
            result.metadata = {
                'total_scenes': len(scene_results),
                'successful_scenes': sum(1 for s in scene_results if s.get('success', False)),
                'storage_mode': self.storage_manager.storage_mode.value,
                'has_s3_upload': any(s.get('upload_result', {}).get('success') for s in scene_results)
            }
            
            logger.info(f"Video generation completed successfully for topic: {topic}")
            return result
            
        except Exception as e:
            logger.error(f"Video generation failed for topic {topic}: {e}", exc_info=True)
            result.success = False
            result.error = str(e)
            return result
    
    async def _generate_and_render_scenes(self, 
                                        topic: str,
                                        description: str,
                                        scene_outline: str,
                                        scene_implementations: List[str]) -> List[Dict[str, Any]]:
        """Generate code and render videos for all scenes."""
        scene_results = []
        total_scenes = len(scene_implementations)
        
        for i, implementation in enumerate(scene_implementations):
            scene_number = i + 1
            scene_progress = 50 + (30 * i / total_scenes)  # Progress from 50% to 80%
            
            try:
                self._update_progress(
                    "scene_generation", 
                    scene_progress, 
                    f"Processing scene {scene_number}/{total_scenes}..."
                )
                
                # Generate scene code
                scene_trace_id = str(uuid.uuid4())
                
                code, response_text = self.code_generator.generate_manim_code(
                    topic=topic,
                    description=description,
                    scene_outline=scene_outline,
                    scene_implementation=implementation,
                    scene_number=scene_number,
                    scene_trace_id=scene_trace_id,
                    session_id=self.config.session_id
                )
                
                # Render scene video
                file_prefix = topic.lower().replace(" ", "_")
                code_dir = os.path.join(self.config.output_dir, file_prefix, f"scene{scene_number}", "code")
                media_dir = os.path.join(self.config.output_dir, file_prefix, "media")
                
                os.makedirs(code_dir, exist_ok=True)
                os.makedirs(media_dir, exist_ok=True)
                
                render_result = await self.video_renderer.render_scene_optimized(
                    code=code,
                    file_prefix=file_prefix,
                    curr_scene=scene_number,
                    curr_version=1,
                    code_dir=code_dir,
                    media_dir=media_dir,
                    quality=self.config.quality,
                    max_retries=self.config.max_retries,
                    scene_trace_id=scene_trace_id,
                    topic=topic,
                    session_id=self.config.session_id,
                    code_generator=self.code_generator,
                    scene_implementation=implementation
                )
                
                scene_result = {
                    'scene_number': scene_number,
                    'success': render_result[1] is None or not isinstance(render_result[1], str),
                    'code': render_result[0],
                    'error': render_result[1] if isinstance(render_result[1], str) else None,
                    'render_info': render_result[1] if isinstance(render_result[1], dict) else None
                }
                
                # Extract upload result if available
                if isinstance(render_result[1], dict) and 'upload_result' in render_result[1]:
                    scene_result['upload_result'] = render_result[1]['upload_result']
                    
                scene_results.append(scene_result)
                
            except Exception as e:
                logger.error(f"Failed to process scene {scene_number}: {e}")
                scene_results.append({
                    'scene_number': scene_number,
                    'success': False,
                    'error': str(e)
                })
        
        return scene_results
    
    async def _combine_videos(self, topic: str, scene_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Combine individual scene videos into a single video."""
        try:
            # Use video renderer's combine functionality
            combined_video_path = await self.video_renderer.combine_videos_optimized(
                topic=topic,
                use_hardware_acceleration=True
            )
            
            # Upload combined video if storage manager is configured
            upload_result = None
            if self.storage_manager and combined_video_path:
                upload_result = await self.storage_manager.store_video(
                    local_video_path=combined_video_path,
                    topic=topic,
                    scene_number=0,  # Use 0 for combined video
                    user_id=self.config.user_id,
                    job_id=self.config.job_id
                )
            
            return {
                'local_path': combined_video_path,
                'upload_result': upload_result
            }
            
        except Exception as e:
            logger.error(f"Failed to combine videos for topic {topic}: {e}")
            return {'error': str(e)}
    
    def _update_progress(self, stage: str, percentage: float, message: str):
        """Update progress via callback if configured."""
        if self.config.progress_callback:
            try:
                self.config.progress_callback(stage, percentage, message)
            except Exception as e:
                logger.warning(f"Progress callback failed: {e}")
        
        logger.info(f"Progress: {stage} - {percentage:.1f}% - {message}")
    
    @staticmethod
    def create_from_environment(topic: str, 
                              description: str,
                              planner_model: Any,
                              scene_model: Any,
                              helper_model: Any = None,
                              user_id: Optional[str] = None,
                              job_id: Optional[str] = None) -> 'VideoGenerationOrchestrator':
        """Create orchestrator with configuration from environment variables.
        
        Args:
            topic: Video topic
            description: Video description  
            planner_model: Model for video planning
            scene_model: Model for scene generation
            helper_model: Helper model (optional)
            user_id: User ID for S3 uploads
            job_id: Job ID for tracking
            
        Returns:
            Configured VideoGenerationOrchestrator
        """
        config = VideoGenerationConfig(
            planner_model=planner_model,
            scene_model=scene_model,
            helper_model=helper_model,
            user_id=user_id,
            job_id=job_id,
            output_dir=os.getenv('OUTPUT_DIR', 'output'),
            enable_s3_upload=os.getenv('ENABLE_S3_UPLOAD', 'false').lower() == 'true',
            storage_mode=os.getenv('VIDEO_STORAGE_MODE', 'local_only'),
            cleanup_local_files=os.getenv('CLEANUP_LOCAL_FILES', 'false').lower() == 'true',
            use_rag=os.getenv('USE_RAG', 'false').lower() == 'true',
            use_context_learning=os.getenv('USE_CONTEXT_LEARNING', 'false').lower() == 'true',
            use_visual_fix_code=os.getenv('USE_VISUAL_FIX_CODE', 'false').lower() == 'true',
            quality=os.getenv('VIDEO_QUALITY', 'medium'),
            max_retries=int(os.getenv('MAX_RETRIES', '3'))
        )
        
        return VideoGenerationOrchestrator(config)