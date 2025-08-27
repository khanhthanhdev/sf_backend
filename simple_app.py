#!/usr/bin/env python3

from fastapi import FastAPI
from pydantic import BaseModel
from simple_config import SimpleSettings

# Create settings
settings = SimpleSettings()

# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    description="A simple FastAPI application for testing",
    version="1.0.0",
)

# Pydantic models for API documentation
class MessageRequest(BaseModel):
    message: str
    user_id: str = None

class MessageResponse(BaseModel):
    response: str
    timestamp: str

@app.get("/")
async def root():
    return {
        "message": f"Welcome to {settings.app_name}",
        "status": "running"
    }

@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "app": settings.app_name,
        "redis_host": settings.redis_host,
        "redis_port": settings.redis_port,
    }

@app.get("/config")
async def config():
    return {
        "origins": settings.get_allowed_origins(),
        "methods": settings.get_allowed_methods(),
        "clerk_configured": bool(settings.clerk_secret_key),
    }

@app.post("/api/message", response_model=MessageResponse)
async def send_message(request: MessageRequest):
    """Send a message and get a response."""
    from datetime import datetime
    return MessageResponse(
        response=f"Received: {request.message}",
        timestamp=datetime.now().isoformat()
    )

@app.get("/api/users/{user_id}")
async def get_user(user_id: str):
    """Get user information by ID."""
    return {
        "user_id": user_id,
        "name": f"User {user_id}",
        "status": "active"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "simple_app:app",
        host=settings.host,
        port=settings.port,
        reload=True,
    )