# T2M Video Generation System

A comprehensive text-to-video generation system with FastAPI backend, featuring multi-agent video creation, AWS S3 integration, and intelligent storage management.

## Features

### Core Video Generation
- **Multi-Agent Pipeline**: Advanced video planning, code generation, and rendering
- **Manim Integration**: High-quality mathematical and educational video generation
- **RAG Support**: Retrieval-augmented generation for improved content quality
- **Visual Self-Reflection**: AI-powered visual quality assessment and improvement

### Storage & Cloud Integration
- **AWS S3 Storage**: Automatic video uploads with streaming URL generation
- **Flexible Storage Modes**: Local-only, S3-only, or hybrid storage options
- **Thumbnail Generation**: Automatic video thumbnail creation and storage
- **Progress Tracking**: Real-time upload progress and status monitoring

### API & Authentication
- **FastAPI Framework**: Modern, fast web framework for building APIs
- **Clerk Authentication**: Secure user authentication and management
- **Redis Integration**: Caching and job queue management
- **Structured Logging**: JSON-formatted logging with structlog
- **CORS Support**: Cross-origin resource sharing configuration

## Quick Start

### Prerequisites

- Python 3.11+
- Redis server
- Clerk account (for authentication)
- AWS Account (for S3 storage, optional)
- FFmpeg (for video processing)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd t2m
   ```

2. **Install dependencies**
   ```bash
   pip install -e .
   ```

3. **Set up development environment**
   ```bash
   python scripts/setup.py
   ```

4. **Configure environment variables**
   
   Copy the example environment file and update with your configuration:
   ```bash
   cp .env.example .env
   ```
   
   **Required for basic operation:**
   ```bash
   # Clerk Authentication
   CLERK_SECRET_KEY=your_actual_clerk_secret_key
   CLERK_PUBLISHABLE_KEY=your_actual_clerk_publishable_key
   
   # Application Security
   SECRET_KEY=your_super_secret_key_here
   
   # Video Generation
   VIDEO_STORAGE_MODE=local_only  # Start with local-only for development
   OUTPUT_DIR=output
   ```
   
   **Optional for AWS S3 integration:**
   ```bash
   # AWS Configuration (for S3 storage)
   AWS_ACCESS_KEY_ID=your_aws_access_key_id
   AWS_SECRET_ACCESS_KEY=your_aws_secret_access_key
   AWS_REGION=us-east-1
   AWS_ACCOUNT_ID=your_account_id
   
   # Enable S3 features
   VIDEO_STORAGE_MODE=local_and_s3
   ENABLE_S3_UPLOAD=true
   ENABLE_THUMBNAILS=true
   ```

5. **Set up AWS resources (if using S3)**
   ```bash
   # Setup S3 buckets and test connectivity
   python scripts/setup_aws_resources.py
   
   # Test AWS configuration
   python scripts/test_aws_config.py
   ```

6. **Start Redis server**
   ```bash
   redis-server
   ```

7. **Run the application**
   
   **For API server:**
   ```bash
   # Development mode
   python -m src.app.main
   
   # Or using uvicorn directly
   python -m uvicorn src.app.main:app --reload
   ```
   
   **For direct video generation:**
   ```bash
   # Local-only generation (development)
   python main.py --mode local --topic "Math Functions" --description "Educational video about quadratic functions"
   
   # S3-enabled generation (production)
   python main.py --mode s3 --user-id user123 --topic "Physics Waves" --description "Video about wave motion"
   ```

8. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Alternative Docs: http://localhost:8000/redoc
   - Health Check: http://localhost:8000/health

## Usage

### Video Generation Modes

The system supports three storage modes:

1. **`local_only`** - Development mode, videos stored locally only
2. **`s3_only`** - Production mode, videos stored only in AWS S3
3. **`local_and_s3`** - Hybrid mode, videos stored locally and uploaded to S3

### Command Line Interface

```bash
# Generate video locally (development)
python main.py --mode local \
  --topic "Mathematics - Derivatives" \
  --description "Educational video explaining derivative concepts with visual animations"

# Generate video with S3 upload (production)
python main.py --mode s3 \
  --user-id user_12345 \
  --topic "Physics - Electromagnetic Waves" \
  --description "Comprehensive explanation of electromagnetic wave propagation"

# Custom output directory
python main.py --mode local \
  --output-dir ./custom_output \
  --topic "Chemistry - Molecular Bonding" \
  --description "Visual explanation of ionic and covalent bonds"
```

### Python API Usage

```python
import asyncio
from src.core.video_orchestrator import VideoGenerationOrchestrator, VideoGenerationConfig
from mllm_tools.gemini import GeminiWrapper

async def generate_video():
    # Initialize models
    planner_model = GeminiWrapper(model_name="gemini-1.5-pro")
    scene_model = GeminiWrapper(model_name="gemini-1.5-pro")
    
    # Configure generation
    config = VideoGenerationConfig(
        planner_model=planner_model,
        scene_model=scene_model,
        user_id="user_123",
        job_id="job_456",
        storage_mode="local_and_s3",
        enable_s3_upload=True,
        quality="high"
    )
    
    # Create orchestrator
    orchestrator = VideoGenerationOrchestrator(config)
    
    # Generate video
    result = await orchestrator.generate_video(
        topic="Calculus - Integration",
        description="Visual explanation of integration techniques"
    )
    
    if result.success:
        print(f"✅ Video generated: {result.combined_video_upload.streaming_url}")
    else:
        print(f"❌ Generation failed: {result.error}")

# Run the generation
asyncio.run(generate_video())
```

### Storage Manager Usage

```python
from src.core.storage_manager import StorageManager

# Create storage manager
storage_manager = StorageManager.create_from_config(
    storage_mode='local_and_s3',
    user_id='user_123'
)

# Upload existing video
upload_result = await storage_manager.store_video(
    local_video_path="./output/video.mp4",
    topic="Sample Video",
    scene_number=1,
    user_id="user_123",
    job_id="job_456"
)

if upload_result.success:
    print(f"Streaming URL: {upload_result.streaming_url}")
```

## Project Structure

```
src/
├── app/
│   ├── main.py                    # FastAPI application entry point
│   ├── api/                       # API layer
│   │   ├── dependencies.py        # Shared dependencies
│   │   └── v1/                    # API version 1
│   │       ├── videos.py          # Video generation endpoints
│   │       ├── jobs.py            # Job management endpoints
│   │       └── system.py          # System health endpoints
│   ├── core/                      # Core utilities and configurations
│   │   ├── config.py              # Application settings
│   │   ├── redis.py               # Redis connection and utilities
│   │   ├── auth.py                # Clerk authentication utilities
│   │   ├── logger.py              # Logging configuration
│   │   └── exceptions.py          # Custom exceptions
│   ├── services/                  # Business logic layer
│   │   ├── video_service.py       # Video generation business logic
│   │   ├── job_service.py         # Job management logic
│   │   └── queue_service.py       # Redis queue management
│   ├── models/                    # Pydantic models
│   │   ├── job.py                 # Job data models
│   │   ├── video.py               # Video metadata models
│   │   ├── user.py                # User data models
│   │   └── system.py              # System status models
│   ├── middleware/                # Custom middleware
│   │   ├── cors.py                # CORS middleware
│   │   ├── clerk_auth.py          # Clerk authentication middleware
│   │   └── error_handling.py      # Global error handling
│   └── utils/                     # Utility functions
│       ├── file_utils.py          # File handling utilities
│       └── helpers.py             # General helper functions
├── tests/                         # Test suite
└── scripts/                       # Utility scripts
```

## Configuration

The application uses environment-based configuration with Pydantic Settings. All configuration options are documented in `.env.example`.

### Key Configuration Sections

- **Application Settings**: Basic app configuration
- **Server Settings**: Host, port, and server options
- **Redis Settings**: Redis connection and caching configuration
- **Clerk Settings**: Authentication configuration
- **Security Settings**: JWT and security configuration
- **Logging Settings**: Structured logging configuration

## Development

### Running Tests

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=src

# Run specific test file
pytest tests/test_main.py
```

### Code Quality

```bash
# Format code
black src/ tests/

# Sort imports
isort src/ tests/

# Lint code
flake8 src/ tests/

# Type checking
mypy src/
```

### Development Scripts

- `python scripts/setup.py` - Set up development environment
- `python -m src.app.main` - Run development server
- `pytest` - Run test suite

## API Documentation

Once the application is running, you can access:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json

## Health Monitoring

The application includes built-in health check endpoints:

- `GET /health` - Basic health status
- `GET /` - Root endpoint with basic information

## Logging

The application uses structured logging with configurable output formats:

- **Development**: Colorized console output
- **Production**: JSON-formatted logs

Log levels and formats can be configured via environment variables.

## Security

- **Authentication**: Clerk-based JWT authentication
- **CORS**: Configurable cross-origin resource sharing
- **Rate Limiting**: Built-in rate limiting support
- **Input Validation**: Pydantic-based request validation
- **Security Headers**: Automatic security header injection

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests for new functionality
5. Ensure all tests pass
6. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.