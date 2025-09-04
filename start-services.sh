#!/bin/bash

# Simple script to start ngrok (Redis removed)
set -e

echo "🚀 Starting ngrok service (Redis has been removed)"
echo "============================================="

# Get ngrok token from .env file
if [ -f ".env" ]; then
    NGROK_AUTHTOKEN=$(grep "NGROK_AUTHTOKEN=" .env | cut -d '=' -f2)
fi

if [ -z "$NGROK_AUTHTOKEN" ]; then
    echo "❌ NGROK_AUTHTOKEN not found in .env file."
    echo "   Please add: NGROK_AUTHTOKEN=your_token_here"
    exit 1
fi

echo "✅ Found ngrok auth token"

# Note: Redis has been removed from this application
echo "🔍 Redis has been removed - application now uses database-only storage"
echo "✅ Redis removal completed"

# Check if ngrok is already running
if docker ps | grep -q "ngrok.*4040"; then
    echo "✅ ngrok is already running"
    echo "   📊 ngrok Web Interface: http://localhost:4040"
else
    # Start ngrok container
    echo "🔧 Starting ngrok..."
    docker run -d \
        --name t2m-ngrok-$(date +%s) \
        --rm \
        -p 4040:4040 \
        -e NGROK_AUTHTOKEN=$NGROK_AUTHTOKEN \
        --add-host=host.docker.internal:host-gateway \
        ngrok/ngrok:latest \
        http host.docker.internal:8000

    # Wait for ngrok to start
    sleep 3

    echo "✅ ngrok is running"
    echo "   📊 ngrok Web Interface: http://localhost:4040"
fi

echo ""
echo "🎯 Next Steps:"
echo "=============="
echo "1. Start your FastAPI server:"
echo "   python -m uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "2. Get your public URL:"
echo "   curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'"
echo ""
echo "📝 To stop services:"
echo "docker stop \$(docker ps -q --filter 'ancestor=redis:7-alpine' --filter 'ancestor=ngrok/ngrok:latest')"
echo ""
echo "✨ Services are ready!"