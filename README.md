# FastAPI Video Backend

A FastAPI backend for the multi-agent video generation system using Pydantic for data modeling, Clerk for authentication, and Redis for caching and job queuing.

## Features

- **FastAPI Framework**: Modern, fast web framework for building APIs
- **Pydantic Models**: Data validation and serialization
- **Clerk Authentication**: Secure user authentication and management
- **Redis Integration**: Caching and job queue management
- **Structured Logging**: JSON-formatted logging with structlog
- **Environment Configuration**: Flexible configuration with Pydantic Settings
- **CORS Support**: Cross-origin resource sharing configuration
- **Health Checks**: Built-in health monitoring endpoints
- **Testing Suite**: Comprehensive test coverage with pytest

## Quick Start

### Prerequisites

- Python 3.11+
- Redis server
- Clerk account (for authentication)

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd fastapi-video-backend
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
   
   Update the `.env` file with your actual configuration:
   ```bash
   # Required: Get these from your Clerk dashboard
   CLERK_SECRET_KEY=your_actual_clerk_secret_key
   CLERK_PUBLISHABLE_KEY=your_actual_clerk_publishable_key
   
   # Required: Generate a secure secret key
   SECRET_KEY=your_super_secret_key_here
   ```

5. **Start Redis server**
   ```bash
   redis-server
   ```

6. **Run the application**
   ```bash
   # Development mode
   python -m src.app.main
   
   # Or using the script
   python -m uvicorn src.app.main:app --reload
   ```

7. **Access the API**
   - API Documentation: http://localhost:8000/docs
   - Alternative Docs: http://localhost:8000/redoc
   - Health Check: http://localhost:8000/health

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