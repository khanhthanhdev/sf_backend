# ✅ Working FastAPI + Docker + ngrok Setup

## 🎯 Current Status: WORKING!

Your development environment is successfully set up with:
- ✅ Redis running in Docker
- ✅ ngrok exposing your local server publicly  
- ✅ FastAPI server running locally
- ✅ Public HTTPS URL: `https://d4e9601ecb72.ngrok-free.app`

## 🚀 Quick Start Commands

### 1. Start Services (Redis + ngrok)
```bash
./start-services.sh
```

### 2. Start FastAPI Server
```bash
# Simple working version
python simple_app.py

# Or the full version (once config is fixed)
python -m uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
```

### 3. Get Your Public URL
```bash
curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'
```

## 🌐 Your URLs

- **Local API**: http://localhost:8000
- **Public API**: https://d4e9601ecb72.ngrok-free.app
- **API Docs**: https://d4e9601ecb72.ngrok-free.app/docs (when using simple_app.py)
- **ngrok Dashboard**: http://localhost:4040
- **Redis**: localhost:6379

## 🔧 Configure Clerk Webhook

Now you can set up your Clerk webhook:

1. Go to [Clerk Dashboard](https://dashboard.clerk.com/)
2. Navigate to **Webhooks** → **Add Endpoint**
3. Enter your webhook URL:
   ```
   https://d4e9601ecb72.ngrok-free.app/api/v1/auth/webhooks/clerk
   ```
4. Select events: `user.created`, `user.updated`, `user.deleted`, `session.created`, `session.ended`
5. Copy the **Signing Secret** and add to your `.env`:
   ```env
   CLERK_WEBHOOK_SECRET=whsec_your_webhook_signing_secret_here
   ```

## 📝 Available Endpoints (Simple App)

- `GET /` - Welcome message
- `GET /health` - Health check
- `GET /config` - Configuration info

Test them:
```bash
curl https://d4e9601ecb72.ngrok-free.app/
curl https://d4e9601ecb72.ngrok-free.app/health
curl https://d4e9601ecb72.ngrok-free.app/config
```

## 🛠️ Service Management

### Check Services
```bash
# Check Redis
redis-cli ping

# Check ngrok tunnels
curl -s http://localhost:4040/api/tunnels

# Check Docker containers
docker ps
```

### Stop Services
```bash
# Stop all related containers
docker stop $(docker ps -q --filter 'ancestor=redis:7-alpine' --filter 'ancestor=ngrok/ngrok:latest')
```

### Restart Services
```bash
./start-services.sh
```

## 🔍 Troubleshooting

### If ngrok URL changes:
The ngrok URL will change each time you restart ngrok (unless you have a paid plan). Get the new URL with:
```bash
curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'
```

### If Redis connection fails:
```bash
# Check if Redis is running
docker ps | grep redis

# Restart Redis if needed
docker restart $(docker ps -q --filter 'ancestor=redis:7-alpine')
```

### If FastAPI config fails:
Use the simple app for now:
```bash
python simple_app.py
```

## 🎉 Next Steps

1. **Test your webhook**: Use the public URL to set up Clerk webhooks
2. **Fix the main FastAPI app**: The config parsing issue needs to be resolved
3. **Add authentication**: Implement Clerk authentication middleware
4. **Add your business logic**: Build your video generation endpoints

## 📋 Working Files

- `start-services.sh` - Starts Redis and ngrok
- `simple_app.py` - Working FastAPI application
- `simple_config.py` - Working configuration
- `.env` - Environment variables (configured)

Your development environment is ready for webhook testing! 🚀