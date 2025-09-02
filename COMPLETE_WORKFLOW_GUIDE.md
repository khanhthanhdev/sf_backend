# Complete Video Generation Workflow Setup Guide

This guide walks you through setting up the complete frontend-to-backend video generation workflow.

## 🎯 Overview

The complete flow works as follows:

1. **Frontend Form** (`/videos/create`) - User inputs topic, model settings, quality preferences
2. **API Request** - Frontend sends POST to `/api/v1/videos/generate`  
3. **Job Creation** - Backend creates job in AWS RDS database
4. **Video Generation** - Backend runs end-to-end AI video generation pipeline
5. **Progress Monitoring** - Frontend polls `/api/v1/videos/jobs/{id}/status`
6. **Video Display** - Frontend displays completed video via streaming URL

## 🚀 Quick Start

### 1. Start Backend (T2M)

```bash
cd t2m
# Install dependencies
pip install -r requirements.txt

# Set up environment variables
cp .env.example .env
# Edit .env with your API keys and database configuration

# Start the FastAPI server
python main.py
```

The backend will be available at `http://localhost:8000`

### 2. Start Frontend (SF Frontend)

```bash
cd sf_frontend
# Install dependencies
npm install

# Set up environment variables
cp .env.example .env.local
# Edit .env.local with your Clerk and backend configuration

# Start the Next.js development server
npm run dev
```

The frontend will be available at `http://localhost:3000`

### 3. Test the Complete Flow

1. Open `http://localhost:3000/videos/create`
2. Fill out the video creation form:
   - **Topic**: "Pythagorean Theorem" 
   - **Context**: "Explain the mathematical proof with visual demonstration"
   - **Model**: Choose from available AI models
   - **Quality**: Select desired video quality
   - **Options**: Enable/disable subtitles, thumbnails, RAG
3. Click "Create Video"
4. You'll be redirected to `/videos/status/{jobId}`
5. Monitor the real-time progress updates
6. When completed, the video will display with playback controls

## 🔧 Configuration

### Backend Configuration

Key environment variables in `t2m/.env`:

```env
# Database
DATABASE_URL=postgresql://user:pass@localhost/t2m
REDIS_URL=redis://localhost:6379

# AI Models
OPENAI_API_KEY=your_openai_key
ANTHROPIC_API_KEY=your_anthropic_key
GEMINI_API_KEY=your_gemini_key

# AWS (for video storage)
AWS_ACCESS_KEY_ID=your_aws_key
AWS_SECRET_ACCESS_KEY=your_aws_secret
AWS_REGION=us-east-1
S3_BUCKET_NAME=your_video_bucket

# Authentication
CLERK_SECRET_KEY=your_clerk_secret
```

### Frontend Configuration

Key environment variables in `sf_frontend/.env.local`:

```env
# Backend API
NEXT_PUBLIC_API_URL=http://localhost:8000

# Clerk Authentication
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY=your_clerk_publishable_key
CLERK_SECRET_KEY=your_clerk_secret_key
```

## 📊 API Endpoints

### Video Generation Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/v1/videos/generate` | Create video generation job |
| `GET` | `/api/v1/videos/jobs/{id}/status` | Get job status and progress |
| `GET` | `/api/v1/videos/jobs/{id}/video-url` | Get video streaming URLs |
| `GET` | `/api/v1/videos/jobs/{id}/stream` | Stream video content |
| `GET` | `/api/v1/videos/jobs/{id}/download` | Download video file |
| `GET` | `/api/v1/videos/jobs/{id}/thumbnail` | Get video thumbnail |
| `GET` | `/api/v1/videos/jobs/{id}/metadata` | Get video metadata |

### Request/Response Examples

#### Create Video Job

```bash
curl -X POST http://localhost:8000/api/v1/videos/generate \
  -H "Authorization: Bearer YOUR_CLERK_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "configuration": {
      "topic": "Pythagorean Theorem",
      "context": "Explain the mathematical proof with visual demonstration",
      "model": "gemini/gemini-2.0-flash-thinking-exp-01-21",
      "quality": "medium",
      "use_rag": false,
      "enable_subtitles": true,
      "enable_thumbnails": true,
      "output_format": "mp4"
    },
    "priority": "normal"
  }'
```

Response:
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "progress": {
    "percentage": 5.0,
    "current_stage": "initializing",
    "stages_completed": []
  },
  "created_at": "2024-01-15T10:30:00Z"
}
```

## 🧪 Testing

### Manual Testing

1. Run the test script:
```bash
cd t2m
python test_full_flow.py
```

2. Test with different configurations:
   - Various AI models
   - Different quality settings
   - Enable/disable features (RAG, subtitles)

## 📚 Complete Flow Summary

Your complete video generation workflow is now set up:

1. **User Input**: Frontend form captures video requirements
2. **Job Creation**: Backend creates job and starts processing immediately  
3. **AI Generation**: Multi-agent pipeline generates educational video
4. **Progress Tracking**: Real-time status updates via WebSocket/polling
5. **Video Storage**: Completed videos stored in AWS S3
6. **Video Display**: Frontend streams video with player controls

The system supports:
- Multiple AI models (Gemini, GPT-4, Claude)
- Quality settings (low to ultra)
- Advanced features (RAG, subtitles, thumbnails)
- Real-time progress monitoring
- Secure authentication via Clerk
- Scalable cloud storage via AWS

Happy video generation! 🎬
