# FastAPI Server Setup Guide

This guide will help you set up and run the FastAPI server for the T2M (Text-to-Media) video generation system.

## Prerequisites

- Python 3.11 or higher
- Redis server (for caching and job queuing)
- Git (for cloning the repository)

## Quick Start

### 1. Environment Setup

Your `.env` file is already configured with your Clerk keys. You just need to add the webhook secret once you create the webhook endpoint.

### 2. Get ngrok Auth Token (if not already set)

If you don't have an ngrok auth token in your `.env` file:

1. Go to [ngrok Dashboard](https://dashboard.ngrok.com/get-started/your-authtoken)
2. Sign up/login and copy your auth token
3. Add it to your `.env` file:
   ```env
   NGROK_AUTHTOKEN=your_token_here
   ```

### 3. Quick Setup with Docker (Recommended)

Run the automated setup script:

**On Windows:**

```cmd
setup-dev.bat
```

**On Linux/macOS:**

```bash
chmod +x setup-dev.sh
./setup-dev.sh
```

**Or manually with Make:**

```bash
make dev-services
```

### 4. Get Your Public ngrok URL

After running the setup script:

1. Visit the ngrok dashboard: http://localhost:4040
2. Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)
3. This is your public URL for webhooks

**Or get it via command:**

```bash
make get-ngrok-url
```

### 5. Configure Clerk Webhook

1. Go to [Clerk Dashboard](https://dashboard.clerk.com/)
2. Navigate to **Webhooks**
3. Click **"Add Endpoint"**
4. Enter your ngrok URL + webhook path:
   ```
   https://your-ngrok-url.ngrok.io/api/v1/auth/webhooks/clerk
   ```
5. Select events: `user.created`, `user.updated`, `user.deleted`, `session.created`, `session.ended`
6. Copy the **Signing Secret** and add it to your `.env`:
   ```env
   CLERK_WEBHOOK_SECRET=whsec_your_webhook_signing_secret_here
   ```

### 6. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 7. Start the FastAPI Server

#### Method 1: Using the Makefile (Recommended)

```bash
make serve-api
```

#### Method 2: Using uvicorn directly

```bash
python -m uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

#### Method 3: Full development workflow (services + API)

```bash
make dev-start
```

## Verification

Once the server is running, you can verify it's working by:

### 1. Health Check

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{
  "status": "healthy",
  "app_name": "FastAPI Video Backend",
  "version": "0.1.0",
  "environment": "development"
}
```

### 2. API Documentation

Visit these URLs in your browser:

- **Local Swagger UI**: http://localhost:8000/docs
- **Public Swagger UI**: https://your-ngrok-url.ngrok.io/docs
- **ReDoc**: http://localhost:8000/redoc
- **OpenAPI JSON**: http://localhost:8000/openapi.json
- **ngrok Dashboard**: http://localhost:4040

### 3. Test Public Endpoint

```bash
# Test local endpoint
curl http://localhost:8000/

# Test public ngrok endpoint
curl https://your-ngrok-url.ngrok.io/health
```

## Docker Services Management

### Available Commands

```bash
# Start development services (Redis + ngrok)
make dev-services

# Stop development services
make dev-services-stop

# View service logs
make dev-services-logs

# Get current ngrok public URL
make get-ngrok-url

# Full development workflow
make dev-start
```

### Manual Docker Commands

```bash
# Start services
docker-compose -f docker-compose.dev.yml up -d

# Stop services
docker-compose -f docker-compose.dev.yml down

# View logs
docker-compose -f docker-compose.dev.yml logs -f

# Check service status
docker-compose -f docker-compose.dev.yml ps
```

## Available API Endpoints

The server provides the following main endpoint groups:

- **Authentication** (`/api/v1/auth/*`) - User authentication and authorization
- **Videos** (`/api/v1/videos/*`) - Video generation and management
- **Jobs** (`/api/v1/jobs/*`) - Background job management
- **Files** (`/api/v1/files/*`) - File upload and management
- **System** (`/api/v1/system/*`) - System health and monitoring

## Development Features

### Auto-reload

The server runs with auto-reload enabled in development mode, so changes to your code will automatically restart the server.

### Debug Mode

When `DEBUG=true` in your `.env` file:

- Detailed error messages are shown
- API documentation is available
- CORS is configured for local development

### Logging

The application uses structured logging. Logs will show:

- Request/response information
- Performance metrics
- Error details
- Authentication events

## Troubleshooting

### Common Issues

#### 1. Redis Connection Error

```
Failed to initialize Redis: [Errno 111] Connection refused
```

**Solution**: Make sure Redis server is running on the configured host and port.

#### 2. Clerk Authentication Error

```
Failed to initialize Clerk: Invalid secret key
```

**Solution**: Verify your Clerk API keys in the `.env` file are correct.

#### 3. Port Already in Use

```
[Errno 48] Address already in use
```

**Solution**: Either stop the process using port 8000 or change the `PORT` in your `.env` file.

#### 4. Import Errors

```
ModuleNotFoundError: No module named 'src'
```

**Solution**: Make sure you're running the server from the project root directory.

### Checking Server Status

```bash
# Check if server is running
curl -f http://localhost:8000/health

# Check Redis connection
redis-cli ping

# View server logs (if running in background)
tail -f logs/app.log
```

## Production Deployment

For production deployment:

1. Set `ENVIRONMENT=production` in your `.env`
2. Set `DEBUG=false`
3. Use a strong `SECRET_KEY`
4. Configure proper `ALLOWED_ORIGINS` for CORS
5. Set up proper Redis configuration with authentication
6. Use a production ASGI server like Gunicorn with Uvicorn workers

```bash
# Production server example
gunicorn src.app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

## Next Steps

After setting up the server:

1. **Generate Client SDKs**: Use `make generate-clients` to create client libraries
2. **Test the API**: Use `make test-clients` to run integration tests
3. **Explore the Documentation**: Visit `/docs` to understand available endpoints
4. **Set up Authentication**: Configure Clerk for user management
5. **Upload Files**: Test file upload functionality through the API

## Support

If you encounter issues:

1. Check the server logs for detailed error messages
2. Verify all environment variables are set correctly
3. Ensure all dependencies are installed
4. Make sure Redis is running and accessible
5. Check that your API keys are valid and have proper permissions

For additional help, refer to the project documentation or create an issue in the repository.
