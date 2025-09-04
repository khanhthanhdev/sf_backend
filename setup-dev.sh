#!/bin/bash

# T2M FastAPI Development Setup Script
# This script sets up Redis, ngrok, and provides instructions for FastAPI

set -e

echo "🚀 Setting up T2M FastAPI Development Environment"
echo "================================================"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "❌ .env file not found. Please copy .env.example to .env and configure it."
    exit 1
fi

# Check if NGROK_AUTHTOKEN is set
if ! grep -q "NGROK_AUTHTOKEN=" .env || grep -q "NGROK_AUTHTOKEN=$" .env; then
    echo "❌ NGROK_AUTHTOKEN is not set in .env file."
    echo "   Please get your auth token from https://dashboard.ngrok.com/get-started/your-authtoken"
    echo "   and add it to your .env file: NGROK_AUTHTOKEN=your_token_here"
    exit 1
fi

echo "✅ Prerequisites check passed"
echo ""

# Start ngrok services (Redis removed)
echo "🔧 Starting ngrok service (Redis has been removed)..."

echo "📝 Note: Redis has been completely removed from this application"
echo "Application now uses database-only storage for better simplicity."
echo ""

# Check if ngrok is running  
if docker-compose -f docker-compose.simple.yml ps ngrok | grep -q "Up"; then
    echo "✅ ngrok is running"
    echo "   📊 ngrok Web Interface: http://localhost:4040"
else
    echo "❌ ngrok failed to start"
    echo "Starting ngrok manually..."
    docker-compose -f docker-compose.simple.yml up -d
fi

echo ""
echo "🎯 Next Steps:"
echo "=============="
echo ""
echo "1. Start your FastAPI server locally:"
echo "   python -m uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "2. Get your public ngrok URL:"
echo "   - Visit: http://localhost:4040"
echo "   - Copy the HTTPS URL (e.g., https://abc123.ngrok.io)"
echo ""
echo "3. Configure Clerk webhook:"
echo "   - Go to https://dashboard.clerk.com/"
echo "   - Navigate to Webhooks"
echo "   - Add endpoint: https://your-ngrok-url.ngrok.io/api/v1/auth/webhooks/clerk"
echo "   - Copy the signing secret to CLERK_WEBHOOK_SECRET in .env"
echo ""
echo "4. Test your setup:"
echo "   curl https://your-ngrok-url.ngrok.io/health"
echo ""
echo "📝 Useful Commands:"
echo "=================="
echo "• View logs: docker-compose -f docker-compose.simple.yml logs -f"
echo "• Stop services: docker-compose -f docker-compose.simple.yml down"
echo "• Restart services: docker-compose -f docker-compose.simple.yml restart"
echo "• Redis: REMOVED (application uses database-only storage)"
echo ""
echo "🌐 URLs:"
echo "========"
echo "• FastAPI (local): http://localhost:8000"
echo "• FastAPI Docs: http://localhost:8000/docs"
echo "• ngrok Dashboard: http://localhost:4040"
echo "• Redis: REMOVED from application"
echo ""
echo "✨ Development environment is ready!"