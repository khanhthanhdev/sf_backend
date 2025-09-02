# Video Generation API Integration Specification

## Overview
This specification outlines the integration of the core video generation workflow (from `src/core/`) with the FastAPI video endpoints. The goal is to ensure that API requests trigger the full sophisticated pipeline: planning → scenario creation → Manim code generation → rendering → storage.

## Current Architecture Analysis

### Core Components (src/core/)
- **EnhancedVideoPlanner**: Creates scene outlines and implementation plans
- **CodeGenerator**: Generates Manim code with RAG and error handling
- **OptimizedVideoRenderer**: Renders scenes with caching and optimization
- **VideoGenerationOrchestrator**: Coordinates the entire pipeline
- **StorageManager**: Handles local and S3 storage

### API Layer (src/app/api/v1/videos.py)
- **POST /videos/generate**: Creates jobs and triggers processing
- **GET /videos/jobs/{job_id}/status**: Returns job status and progress
- **GET /videos/jobs/{job_id}/video-url**: Returns video URLs for completed jobs
- **GET /videos/jobs/{job_id}/stream**: Streams video content
- **GET /videos/jobs/{job_id}/download**: Downloads video files

### Current Gap
The API endpoints use `VideoService.process_video_generation_immediately()` but this doesn't connect to the sophisticated core workflow in `src/core/`.

## Integration Requirements

### 1. Core Workflow Integration
- API endpoints must trigger the full core pipeline
- Maintain existing API contract and response formats
- Preserve job tracking and status updates
- Support progress reporting during generation
- Handle errors gracefully with proper API responses

### 2. Storage Integration
- Generated videos must be stored via `StorageManager`
- Support both local and S3 storage modes
- Update job records with final video URLs
- Generate thumbnails and metadata

### 3. Progress Tracking
- Real-time progress updates during each pipeline stage
- Detailed stage information (planning, code generation, rendering)
- Error reporting with context and recovery suggestions

### 4. Configuration Management
- Environment-based model selection
- Quality and performance settings
- Storage configuration
- Concurrency limits

## Implementation Plan

### Phase 1: Core Service Integration

#### 1.1 Enhanced Video Service
Create `EnhancedVideoService` that bridges API and core workflow:

```python
# src/app/services/enhanced_video_service.py
class EnhancedVideoService:
    def __init__(self, 
                 video_service: VideoService,
                 storage_manager: StorageManager,
                 config: VideoGenerationConfig):
        self.video_service = video_service
        self.storage_manager = storage_manager
        self.config = config
        
    async def process_video_with_core_pipeline(self, job_id: str) -> None:
        """Process video using core agents pipeline."""
        # Get job details
        # Initialize core components
        # Run pipeline with progress tracking
        # Handle storage and job updates
```

#### 1.2 Pipeline Orchestrator Integration
Integrate `VideoGenerationOrchestrator` with job tracking:

```python
# Enhanced orchestrator with job integration
class APIVideoOrchestrator(VideoGenerationOrchestrator):
    def __init__(self, config: VideoGenerationConfig, 
                 job_id: str, video_service: VideoService):
        super().__init__(config)
        self.job_id = job_id
        self.video_service = video_service
        
    async def _update_progress(self, stage: str, percentage: float, message: str):
        """Update job progress in database."""
        await self.video_service.update_job_progress(
            self.job_id, stage, percentage, message
        )
```

### Phase 2: API Endpoint Updates

#### 2.1 Generate Video Endpoint
Update to use enhanced service:

```python
@router.post("/generate")
async def generate_video(
    request: JobCreateRequest,
    current_user: Dict[str, Any] = Depends(get_current_user),
    enhanced_video_service: EnhancedVideoService = Depends(get_enhanced_video_service)
) -> JobResponse:
    """Generate video using core agents pipeline."""
    
    # Create job record
    job = await enhanced_video_service.create_video_job(request, current_user)
    
    # Start core pipeline in background
    asyncio.create_task(
        enhanced_video_service.process_video_with_core_pipeline(job.id)
    )
    
    return JobResponse(job_id=job.id, status="queued", ...)
```

#### 2.2 Enhanced Progress Tracking
Real-time progress updates with detailed stages:

```python
# Progress stages mapping
PIPELINE_STAGES = {
    "initializing": {"percentage": 5, "description": "Initializing video generation"},
    "planning": {"percentage": 15, "description": "Creating scene outline"},
    "scenario_creation": {"percentage": 30, "description": "Generating scene implementations"},
    "code_generation": {"percentage": 50, "description": "Creating Manim code"},
    "rendering": {"percentage": 80, "description": "Rendering video scenes"},
    "combining": {"percentage": 90, "description": "Combining scenes"},
    "storage": {"percentage": 95, "description": "Uploading to storage"},
    "completed": {"percentage": 100, "description": "Video generation completed"}
}
```

### Phase 3: Configuration and Dependencies

#### 3.1 Dependency Injection Setup
```python
# src/app/dependencies.py
async def get_enhanced_video_service() -> EnhancedVideoService:
    """Get enhanced video service with core pipeline integration."""
    config = VideoGenerationConfig(
        planner_model=os.getenv("PLANNER_MODEL", "gemini/gemini-2.5-pro"),
        scene_model=os.getenv("SCENE_MODEL", "gemini/gemini-2.5-pro"),
        helper_model=os.getenv("HELPER_MODEL", "gemini/gemini-2.5-pro"),
        output_dir=os.getenv("OUTPUT_DIR", "output"),
        use_rag=os.getenv("USE_RAG", "true").lower() == "true",
        use_context_learning=os.getenv("USE_CONTEXT_LEARNING", "false").lower() == "true",
        max_scene_concurrency=int(os.getenv("MAX_SCENE_CONCURRENCY", "3")),
        enable_s3_upload=os.getenv("ENABLE_S3_UPLOAD", "true").lower() == "true"
    )
    
    storage_manager = StorageManager.create_from_config()
    video_service = get_video_service()
    
    return EnhancedVideoService(video_service, storage_manager, config)
```

#### 3.2 Environment Configuration
```bash
# .env additions for core pipeline
PLANNER_MODEL=gemini/gemini-2.5-pro
SCENE_MODEL=gemini/gemini-2.5-pro
HELPER_MODEL=gemini/gemini-2.5-pro
USE_RAG=true
USE_CONTEXT_LEARNING=false
MAX_SCENE_CONCURRENCY=3
MAX_CONCURRENT_RENDERS=2
ENABLE_CACHING=true
USE_GPU_ACCELERATION=false
DEFAULT_QUALITY=medium
```

### Phase 4: Error Handling and Recovery

#### 4.1 Comprehensive Error Handling
```python
class VideoGenerationError(Exception):
    """Base exception for video generation errors."""
    def __init__(self, stage: str, message: str, recoverable: bool = False):
        self.stage = stage
        self.message = message
        self.recoverable = recoverable
        super().__init__(f"Error in {stage}: {message}")

class PlanningError(VideoGenerationError):
    """Error during scene planning stage."""
    pass

class CodeGenerationError(VideoGenerationError):
    """Error during Manim code generation."""
    pass

class RenderingError(VideoGenerationError):
    """Error during video rendering."""
    pass
```

#### 4.2 Recovery Mechanisms
```python
async def handle_generation_error(self, job_id: str, error: VideoGenerationError):
    """Handle errors with recovery attempts."""
    if error.recoverable:
        # Attempt recovery based on error type
        if isinstance(error, CodeGenerationError):
            await self.retry_code_generation(job_id)
        elif isinstance(error, RenderingError):
            await self.retry_rendering(job_id)
    else:
        # Mark job as failed with detailed error info
        await self.video_service.update_job_error(
            job_id, error.stage, error.message
        )
```

## File Structure Changes

### New Files to Create
```
src/app/services/
├── enhanced_video_service.py          # Main integration service
├── pipeline_orchestrator.py           # API-aware orchestrator
└── progress_tracker.py                # Progress tracking utilities

src/app/core/
├── video_pipeline_integration.py      # Core pipeline wrapper
└── error_handlers.py                  # Error handling utilities

src/app/config/
└── pipeline_config.py                 # Pipeline configuration management
```

### Files to Modify
```
src/app/api/v1/videos.py               # Update endpoints to use enhanced service
src/app/dependencies.py                # Add enhanced service dependencies
src/app/services/video_service.py      # Add progress tracking methods
```

## Testing Strategy

### Unit Tests
- Test each core component integration
- Mock external dependencies (AI models, storage)
- Test error handling and recovery

### Integration Tests
- End-to-end API workflow testing
- Progress tracking validation
- Storage integration testing

### Performance Tests
- Concurrent job processing
- Memory usage during generation
- Storage upload performance

## Deployment Considerations

### Resource Requirements
- Increased memory for concurrent processing
- GPU support for accelerated rendering
- Storage space for temporary files

### Monitoring
- Job queue metrics
- Generation success/failure rates
- Performance metrics per stage
- Storage usage tracking

### Scaling
- Horizontal scaling with job queues
- Load balancing for API endpoints
- Distributed storage for large files

## Success Criteria

### Functional Requirements
- ✅ API endpoints trigger full core pipeline
- ✅ Real-time progress tracking works
- ✅ Generated videos are properly stored
- ✅ Error handling provides useful feedback
- ✅ Job status accurately reflects pipeline state

### Performance Requirements
- ✅ API response time < 500ms for job creation
- ✅ Progress updates every 5-10 seconds
- ✅ Support 10+ concurrent video generations
- ✅ 95% success rate for video generation

### Quality Requirements
- ✅ Generated videos match quality expectations
- ✅ Proper error messages for failures
- ✅ Consistent API behavior across environments
- ✅ Comprehensive logging for debugging

## Implementation Timeline

### Week 1: Core Integration
- Create `EnhancedVideoService`
- Integrate `VideoGenerationOrchestrator`
- Basic progress tracking

### Week 2: API Updates
- Update video generation endpoint
- Implement progress tracking
- Error handling integration

### Week 3: Storage & Configuration
- Storage manager integration
- Configuration management
- Environment setup

### Week 4: Testing & Optimization
- Comprehensive testing
- Performance optimization
- Documentation updates

## Next Steps

1. **Review and Approve Specification**
2. **Set up Development Environment**
3. **Create Enhanced Video Service**
4. **Implement Core Pipeline Integration**
5. **Update API Endpoints**
6. **Add Progress Tracking**
7. **Integrate Storage Management**
8. **Comprehensive Testing**
9. **Performance Optimization**
10. **Production Deployment**