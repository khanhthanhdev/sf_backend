# Video Generation API - Frontend Integration Guide

This comprehensive guide provides everything frontend developers need to integrate with the Video Generation API. The API is built with FastAPI and deployed with AWS RDS (PostgreSQL) and S3 for scalable video storage.

## 📋 Table of Contents

1. [Getting Started](#getting-started)
2. [Authentication](#authentication)
3. [API Endpoints](#api-endpoints)
4. [Request/Response Examples](#requestresponse-examples)
5. [Error Handling](#error-handling)
6. [Frontend Integration Patterns](#frontend-integration-patterns)
7. [WebSocket Support](#websocket-support)
8. [Rate Limiting](#rate-limiting)
9. [Best Practices](#best-practices)

## 🚀 Getting Started

### Base URL
- **Development**: `http://localhost:8000/api/v1`
- **Production**: `https://your-domain.com/api/v1`

### API Version
- **Current Version**: `v1`
- **Content Type**: `application/json`

### Quick Health Check
```bash
GET /health
```

```json
{
  "app_name": "FastAPI Video Backend",
  "version": "1.0.0",
  "environment": "development",
  "status": "healthy"
}
```

## 🔐 Authentication

The API uses **Clerk Authentication** with Bearer tokens.

### Headers Required
```javascript
{
  "Authorization": "Bearer YOUR_CLERK_JWT_TOKEN",
  "Content-Type": "application/json"
}
```

### Getting Authentication Token
```javascript
// Using Clerk React
import { useAuth } from "@clerk/nextjs";

function VideoComponent() {
  const { getToken } = useAuth();
  
  const callAPI = async () => {
    const token = await getToken();
    
    const response = await fetch('/api/v1/videos/generate', {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(videoRequest)
    });
  };
}
```

## 🛠 API Endpoints

### 1. Video Generation

#### Create Video Generation Job
```http
POST /videos/generate
```

**Request Body:**
```json
{
  "configuration": {
    "topic": "Pythagorean Theorem",
    "context": "Explain the Pythagorean theorem with visual examples and mathematical proof",
    "quality": "medium",
    "use_rag": false,
    "use_context_learning": false
  },
  "priority": "normal"
}
```

**Response (201 Created):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "queued",
  "progress": {
    "percentage": 0.0,
    "current_stage": "initializing"
  },
  "estimated_completion_time": "2025-09-01T03:15:00Z",
  "created_at": "2025-09-01T03:10:00Z"
}
```

**Configuration Options:**
- `topic` (string, required): Main topic for video generation
- `context` (string, required): Detailed context and instructions
- `quality` (enum): `"low"`, `"medium"`, `"high"` (default: `"medium"`)
- `use_rag` (boolean): Enable RAG (Retrieval Augmented Generation) (default: `false`)
- `use_context_learning` (boolean): Enable context learning (default: `false`)

**Priority Options:**
- `"low"`: Lower priority, longer queue time
- `"normal"`: Standard priority (default)
- `"high"`: Higher priority, faster processing

### 2. Job Status Monitoring

#### Get Job Status
```http
GET /videos/jobs/{job_id}/status
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "processing",
  "progress": {
    "percentage": 45.5,
    "current_stage": "generating_script"
  },
  "created_at": "2025-09-01T03:10:00Z",
  "updated_at": "2025-09-01T03:12:30Z",
  "estimated_completion_time": "2025-09-01T03:15:00Z"
}
```

**Status Values:**
- `"queued"`: Job is waiting in queue
- `"processing"`: Video generation in progress
- `"completed"`: Video generation completed successfully
- `"failed"`: Video generation failed
- `"cancelled"`: Job was cancelled

**Processing Stages:**
- `"initializing"`: Setting up job
- `"generating_script"`: Creating video script
- `"generating_audio"`: Creating voiceover
- `"generating_visuals"`: Creating visual content
- `"rendering"`: Combining audio and visuals
- `"uploading"`: Uploading to S3
- `"completed"`: Job finished

### 3. Video Retrieval

#### Get Video URL and Metadata
```http
GET /videos/jobs/{job_id}/video-url
```

**Response (200 OK):**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "video_url": "https://development-t2m-videos-ap-southeast-1.s3.amazonaws.com/users/user_123/jobs/550e8400-e29b-41d4-a716-446655440000/videos/scene_001/output.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&...",
  "download_url": "https://development-t2m-videos-ap-southeast-1.s3.amazonaws.com/users/user_123/jobs/550e8400-e29b-41d4-a716-446655440000/videos/scene_001/output.mp4?X-Amz-Algorithm=AWS4-HMAC-SHA256&...",
  "thumbnail_url": "/api/v1/videos/jobs/550e8400-e29b-41d4-a716-446655440000/thumbnail",
  "metadata": {
    "duration": 30,
    "quality": "medium",
    "format": "mp4",
    "file_size": 1024000,
    "demo": false,
    "created_at": "2025-09-01T03:15:00Z"
  },
  "is_demo": false
}
```

**Error Responses:**
- `404`: Job not found
- `409`: Job not completed yet
- `403`: Access denied (not your job)

#### Stream Video Content
```http
GET /videos/jobs/{job_id}/stream
```

Direct video streaming endpoint for HTML video players.

#### Get Video Thumbnail
```http
GET /videos/jobs/{job_id}/thumbnail
```

Returns video thumbnail image (JPEG format).

#### Get Video Metadata
```http
GET /videos/jobs/{job_id}/metadata
```

**Response:**
```json
{
  "job_id": "550e8400-e29b-41d4-a716-446655440000",
  "metadata": {
    "title": "Pythagorean Theorem",
    "duration": 30,
    "quality": "medium",
    "format": "mp4",
    "file_size": 1024000,
    "created_at": "2025-09-01T03:15:00Z",
    "dimensions": {
      "width": 1920,
      "height": 1080
    }
  }
}
```

## 📝 Request/Response Examples

### Complete Frontend Workflow

```javascript
class VideoGenerationAPI {
  constructor(baseURL, getAuthToken) {
    this.baseURL = baseURL;
    this.getAuthToken = getAuthToken;
  }

  async makeRequest(endpoint, options = {}) {
    const token = await this.getAuthToken();
    const url = `${this.baseURL}${endpoint}`;
    
    const response = await fetch(url, {
      ...options,
      headers: {
        'Authorization': `Bearer ${token}`,
        'Content-Type': 'application/json',
        ...options.headers
      }
    });

    if (!response.ok) {
      throw new Error(`API Error: ${response.status} - ${await response.text()}`);
    }

    return response.json();
  }

  // 1. Create video generation job
  async createVideoJob(config) {
    return this.makeRequest('/videos/generate', {
      method: 'POST',
      body: JSON.stringify({
        configuration: config,
        priority: 'normal'
      })
    });
  }

  // 2. Monitor job progress
  async getJobStatus(jobId) {
    return this.makeRequest(`/videos/jobs/${jobId}/status`);
  }

  // 3. Get completed video
  async getVideoURL(jobId) {
    return this.makeRequest(`/videos/jobs/${jobId}/video-url`);
  }

  // 4. Poll for completion
  async waitForCompletion(jobId, onProgress, maxWaitTime = 300000) {
    const startTime = Date.now();
    
    while (Date.now() - startTime < maxWaitTime) {
      const status = await this.getJobStatus(jobId);
      
      if (onProgress) {
        onProgress(status);
      }
      
      if (status.status === 'completed') {
        return await this.getVideoURL(jobId);
      } else if (status.status === 'failed') {
        throw new Error(`Video generation failed: ${status.error?.message || 'Unknown error'}`);
      }
      
      await new Promise(resolve => setTimeout(resolve, 3000)); // Wait 3 seconds
    }
    
    throw new Error('Timeout waiting for video completion');
  }
}

// Usage Example
const api = new VideoGenerationAPI('/api/v1', getClerkToken);

async function generateVideo() {
  try {
    // Step 1: Create job
    const job = await api.createVideoJob({
      topic: "Pythagorean Theorem",
      context: "Explain the Pythagorean theorem with visual examples",
      quality: "medium",
      use_rag: false,
      use_context_learning: false
    });

    console.log('Job created:', job.job_id);

    // Step 2: Wait for completion with progress updates
    const video = await api.waitForCompletion(
      job.job_id,
      (status) => {
        console.log(`Progress: ${status.progress.percentage}% - ${status.progress.current_stage}`);
        updateProgressBar(status.progress.percentage);
      }
    );

    console.log('Video ready:', video.video_url);
    return video;

  } catch (error) {
    console.error('Video generation failed:', error);
    throw error;
  }
}
```

### React Hook Example

```javascript
import { useState, useCallback } from 'react';
import { useAuth } from '@clerk/nextjs';

export function useVideoGeneration() {
  const { getToken } = useAuth();
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);
  const [currentStage, setCurrentStage] = useState('');
  const [error, setError] = useState(null);

  const generateVideo = useCallback(async (config) => {
    setIsGenerating(true);
    setError(null);
    setProgress(0);

    try {
      const token = await getToken();
      const api = new VideoGenerationAPI('/api/v1', () => token);

      // Create job
      const job = await api.createVideoJob(config);

      // Wait for completion
      const video = await api.waitForCompletion(
        job.job_id,
        (status) => {
          setProgress(status.progress.percentage);
          setCurrentStage(status.progress.current_stage);
        }
      );

      setIsGenerating(false);
      return video;

    } catch (err) {
      setError(err.message);
      setIsGenerating(false);
      throw err;
    }
  }, [getToken]);

  return {
    generateVideo,
    isGenerating,
    progress,
    currentStage,
    error
  };
}

// Component usage
function VideoGenerator() {
  const { generateVideo, isGenerating, progress, currentStage, error } = useVideoGeneration();
  const [videoURL, setVideoURL] = useState(null);

  const handleGenerate = async () => {
    try {
      const video = await generateVideo({
        topic: "Pythagorean Theorem",
        context: "Educational video with examples",
        quality: "medium"
      });
      
      setVideoURL(video.video_url);
    } catch (error) {
      console.error('Generation failed:', error);
    }
  };

  return (
    <div>
      <button onClick={handleGenerate} disabled={isGenerating}>
        {isGenerating ? 'Generating...' : 'Generate Video'}
      </button>
      
      {isGenerating && (
        <div>
          <div>Progress: {progress.toFixed(1)}%</div>
          <div>Stage: {currentStage}</div>
          <progress value={progress} max={100} />
        </div>
      )}
      
      {error && <div style={{color: 'red'}}>Error: {error}</div>}
      
      {videoURL && (
        <video controls width="800">
          <source src={videoURL} type="video/mp4" />
          Your browser does not support the video tag.
        </video>
      )}
    </div>
  );
}
```

## ⚠️ Error Handling

### Common HTTP Status Codes

| Status Code | Meaning | Action |
|-------------|---------|---------|
| `200` | Success | Continue with response |
| `201` | Created | Job created successfully |
| `400` | Bad Request | Check request format |
| `401` | Unauthorized | Refresh authentication token |
| `403` | Forbidden | User doesn't own this resource |
| `404` | Not Found | Resource doesn't exist |
| `409` | Conflict | Job not ready (still processing) |
| `422` | Validation Error | Check input parameters |
| `429` | Rate Limited | Wait before retrying |
| `500` | Server Error | Retry after delay |

### Error Response Format

```json
{
  "detail": "Job is not completed yet. Current status: processing",
  "status": "processing",
  "progress": 45.5,
  "current_stage": "generating_visuals"
}
```

### Error Handling Best Practices

```javascript
async function handleAPICall(apiCall) {
  try {
    return await apiCall();
  } catch (error) {
    if (error.status === 401) {
      // Refresh authentication
      await refreshAuthToken();
      return apiCall(); // Retry
    } else if (error.status === 409) {
      // Job not ready, continue polling
      return null;
    } else if (error.status === 429) {
      // Rate limited, wait and retry
      await new Promise(resolve => setTimeout(resolve, 5000));
      return apiCall();
    } else if (error.status >= 500) {
      // Server error, retry with exponential backoff
      await exponentialBackoff();
      return apiCall();
    } else {
      // Other errors, propagate to user
      throw error;
    }
  }
}
```

## 🎯 Frontend Integration Patterns

### 1. Simple One-Shot Generation

```javascript
// For simple use cases where you just need to generate and get the result
async function simpleVideoGeneration(topic, context) {
  const api = new VideoGenerationAPI('/api/v1', getAuthToken);
  
  const job = await api.createVideoJob({
    topic,
    context,
    quality: 'medium'
  });
  
  const video = await api.waitForCompletion(job.job_id);
  return video.video_url;
}
```

### 2. Progress-Aware Generation

```javascript
// For UIs that need to show detailed progress
async function progressAwareGeneration(config, progressCallback) {
  const api = new VideoGenerationAPI('/api/v1', getAuthToken);
  
  const job = await api.createVideoJob(config);
  
  return api.waitForCompletion(job.job_id, (status) => {
    progressCallback({
      percentage: status.progress.percentage,
      stage: status.progress.current_stage,
      status: status.status
    });
  });
}
```

### 3. Background Generation with Notifications

```javascript
// For long-running generations that happen in background
class BackgroundVideoGenerator {
  constructor() {
    this.activeJobs = new Map();
  }
  
  async startGeneration(config) {
    const api = new VideoGenerationAPI('/api/v1', getAuthToken);
    const job = await api.createVideoJob(config);
    
    this.activeJobs.set(job.job_id, {
      status: 'processing',
      config,
      startTime: Date.now()
    });
    
    // Start polling in background
    this.pollJob(job.job_id);
    
    return job.job_id;
  }
  
  async pollJob(jobId) {
    const api = new VideoGenerationAPI('/api/v1', getAuthToken);
    
    const poll = async () => {
      try {
        const status = await api.getJobStatus(jobId);
        
        if (status.status === 'completed') {
          const video = await api.getVideoURL(jobId);
          this.onVideoReady(jobId, video);
          this.activeJobs.delete(jobId);
        } else if (status.status === 'failed') {
          this.onVideoFailed(jobId, status.error);
          this.activeJobs.delete(jobId);
        } else {
          // Continue polling
          setTimeout(poll, 5000);
        }
      } catch (error) {
        console.error('Polling error:', error);
        setTimeout(poll, 10000); // Retry after longer delay
      }
    };
    
    poll();
  }
  
  onVideoReady(jobId, video) {
    // Show notification
    showNotification(`Video ready: ${video.metadata.title}`, {
      action: () => window.open(video.video_url)
    });
  }
  
  onVideoFailed(jobId, error) {
    showNotification(`Video generation failed: ${error.message}`, {
      type: 'error'
    });
  }
}
```

### 4. Video Player Integration

```javascript
// For integrating generated videos with video players
function VideoPlayer({ videoData }) {
  const [isLoading, setIsLoading] = useState(true);
  
  useEffect(() => {
    if (videoData?.video_url) {
      // Preload video
      const video = document.createElement('video');
      video.onloadeddata = () => setIsLoading(false);
      video.src = videoData.video_url;
    }
  }, [videoData]);

  if (!videoData) return <div>No video available</div>;
  
  return (
    <div className="video-container">
      {isLoading && <div className="loading-spinner">Loading video...</div>}
      
      <video
        controls
        width="100%"
        poster={videoData.thumbnail_url}
        onLoadedData={() => setIsLoading(false)}
      >
        <source src={videoData.video_url} type="video/mp4" />
        Your browser does not support the video tag.
      </video>
      
      <div className="video-metadata">
        <p>Duration: {videoData.metadata.duration}s</p>
        <p>Quality: {videoData.metadata.quality}</p>
        <p>Size: {(videoData.metadata.file_size / 1024 / 1024).toFixed(2)} MB</p>
      </div>
    </div>
  );
}
```

## 🔄 WebSocket Support

*Note: WebSocket support is planned for future releases to provide real-time progress updates.*

## ⚡ Rate Limiting

- **Rate Limit**: 100 requests per minute per user
- **Concurrent Jobs**: Maximum 3 active video generation jobs per user
- **Headers Returned**:
  - `X-RateLimit-Limit`: Total requests allowed
  - `X-RateLimit-Remaining`: Remaining requests
  - `X-RateLimit-Reset`: Timestamp when limit resets

## ✅ Best Practices

### 1. Authentication
- Always use HTTPS in production
- Handle token expiration gracefully
- Store tokens securely (not in localStorage for sensitive apps)

### 2. Error Handling
- Implement exponential backoff for retries
- Provide meaningful error messages to users
- Log errors for debugging

### 3. Performance
- Cache video URLs (they have expiration times)
- Use video preloading for better UX
- Implement proper loading states

### 4. User Experience
- Show progress indicators for long operations
- Provide cancel functionality for running jobs
- Use background processing for better UX

### 5. Resource Management
- Clean up video URLs after use
- Limit concurrent video generations
- Implement proper timeout handling

### 6. Testing
- Test with various video configurations
- Test error scenarios (network failures, etc.)
- Test on different devices and browsers

## 🔧 Development Tips

### Environment Setup
```javascript
// config.js
export const API_CONFIG = {
  development: {
    baseURL: 'http://localhost:8000/api/v1',
    timeout: 300000 // 5 minutes
  },
  production: {
    baseURL: 'https://your-api-domain.com/api/v1',
    timeout: 600000 // 10 minutes
  }
};
```

### Debugging
```javascript
// Enable detailed logging
const api = new VideoGenerationAPI(baseURL, getAuthToken, {
  debug: process.env.NODE_ENV === 'development'
});
```

### TypeScript Support
```typescript
interface VideoConfig {
  topic: string;
  context: string;
  quality: 'low' | 'medium' | 'high';
  use_rag?: boolean;
  use_context_learning?: boolean;
}

interface JobStatus {
  job_id: string;
  status: 'queued' | 'processing' | 'completed' | 'failed' | 'cancelled';
  progress: {
    percentage: number;
    current_stage: string;
  };
  created_at: string;
  updated_at: string;
}

interface VideoData {
  job_id: string;
  status: string;
  video_url: string;
  download_url: string;
  thumbnail_url: string;
  metadata: {
    duration: number;
    quality: string;
    format: string;
    file_size: number;
    demo: boolean;
    created_at: string;
  };
  is_demo?: boolean;
}
```

## 📞 Support

For additional support:
- Check the API health endpoint: `GET /health`
- Review error messages for debugging information
- Monitor rate limiting headers
- Test with the provided examples

This guide covers all essential aspects of integrating with the Video Generation API. The API is designed to be developer-friendly with comprehensive error handling and clear response formats.
