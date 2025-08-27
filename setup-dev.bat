@echo off
REM T2M FastAPI Development Setup Script for Windows
REM This script sets up Redis, ngrok, and provides instructions for FastAPI

echo 🚀 Setting up T2M FastAPI Development Environment
echo ================================================

REM Check if Docker is installed
docker --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker is not installed. Please install Docker Desktop first.
    pause
    exit /b 1
)

REM Check if Docker Compose is installed
docker-compose --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Docker Compose is not installed. Please install Docker Compose first.
    pause
    exit /b 1
)

REM Check if .env file exists
if not exist ".env" (
    echo ❌ .env file not found. Please copy .env.example to .env and configure it.
    pause
    exit /b 1
)

REM Check if NGROK_AUTHTOKEN is set
findstr /C:"NGROK_AUTHTOKEN=" .env >nul
if %errorlevel% neq 0 (
    echo ❌ NGROK_AUTHTOKEN is not set in .env file.
    echo    Please get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken
    echo    and add it to your .env file: NGROK_AUTHTOKEN=your_token_here
    pause
    exit /b 1
)

echo ✅ Prerequisites check passed
echo.

REM Start Redis and ngrok services
echo 🔧 Starting Redis and ngrok services...
docker-compose -f docker-compose.dev.yml up -d

echo.
echo ⏳ Waiting for services to start...
timeout /t 5 /nobreak >nul

REM Check if services are running
docker-compose -f docker-compose.dev.yml ps

echo.
echo 🎯 Next Steps:
echo ==============
echo.
echo 1. Start your FastAPI server locally:
echo    python -m uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
echo.
echo 2. Get your public ngrok URL:
echo    - Visit: http://localhost:4040
echo    - Copy the HTTPS URL (e.g., https://abc123.ngrok.io)
echo.
echo 3. Configure Clerk webhook:
echo    - Go to https://dashboard.clerk.com/
echo    - Navigate to Webhooks
echo    - Add endpoint: https://your-ngrok-url.ngrok.io/api/v1/auth/webhooks/clerk
echo    - Copy the signing secret to CLERK_WEBHOOK_SECRET in .env
echo.
echo 4. Test your setup:
echo    curl https://your-ngrok-url.ngrok.io/health
echo.
echo 📝 Useful Commands:
echo ==================
echo • View logs: docker-compose -f docker-compose.dev.yml logs -f
echo • Stop services: docker-compose -f docker-compose.dev.yml down
echo • Restart services: docker-compose -f docker-compose.dev.yml restart
echo • Check Redis: redis-cli ping
echo.
echo 🌐 URLs:
echo ========
echo • FastAPI (local): http://localhost:8000
echo • FastAPI Docs: http://localhost:8000/docs
echo • ngrok Dashboard: http://localhost:4040
echo • Redis: localhost:6379
echo.
echo ✨ Development environment is ready!
pause