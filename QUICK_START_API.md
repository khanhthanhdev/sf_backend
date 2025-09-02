# Video Generation API - Quick Start Guide

## 🚀 Quick Setup

### 1. Authentication
```javascript
const headers = {
  "Authorization": "Bearer YOUR_CLERK_JWT_TOKEN",
  "Content-Type": "application/json"
}
```

### 2. Generate Video (3 Steps)

```javascript
// Step 1: Create job
const response = await fetch('/api/v1/videos/generate', {
  method: 'POST',
  headers,
  body: JSON.stringify({
    configuration: {
      topic: "Pythagorean Theorem",
      context: "Explain with examples and proof",
      quality: "medium"
    },
    priority: "normal"
  })
});
const job = await response.json();
// Returns: { job_id: "uuid", status: "queued", progress: { percentage: 0 } }

// Step 2: Poll for completion
const pollStatus = async (jobId) => {
  const response = await fetch(`/api/v1/videos/jobs/${jobId}/status`, { headers });
  return await response.json();
};

// Step 3: Get video URL when completed
const getVideo = async (jobId) => {
  const response = await fetch(`/api/v1/videos/jobs/${jobId}/video-url`, { headers });
  return await response.json();
};
```

## 📋 API Endpoints

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `POST` | `/videos/generate` | Create video job |
| `GET` | `/videos/jobs/{id}/status` | Check progress |
| `GET` | `/videos/jobs/{id}/video-url` | Get video URL |
| `GET` | `/videos/jobs/{id}/stream` | Stream video |
| `GET` | `/videos/jobs/{id}/thumbnail` | Get thumbnail |

## 🔄 Status Flow

```
queued → processing → completed
                  ↓
                failed
```

## 📝 Request Examples

### Create Video
```json
{
  "configuration": {
    "topic": "Your Topic",
    "context": "Detailed context",
    "quality": "medium"
  }
}
```

### Response
```json
{
  "job_id": "uuid",
  "status": "queued",
  "progress": { "percentage": 0, "current_stage": "initializing" }
}
```

## ⚡ React Hook

```javascript
function useVideoGeneration() {
  const { getToken } = useAuth();
  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);

  const generateVideo = async (config) => {
    setIsGenerating(true);
    const token = await getToken();
    
    // Create job
    const jobResponse = await fetch('/api/v1/videos/generate', {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' },
      body: JSON.stringify({ configuration: config })
    });
    const job = await jobResponse.json();

    // Poll until complete
    while (true) {
      const statusResponse = await fetch(`/api/v1/videos/jobs/${job.job_id}/status`, {
        headers: { 'Authorization': `Bearer ${token}` }
      });
      const status = await statusResponse.json();
      
      setProgress(status.progress.percentage);
      
      if (status.status === 'completed') {
        const videoResponse = await fetch(`/api/v1/videos/jobs/${job.job_id}/video-url`, {
          headers: { 'Authorization': `Bearer ${token}` }
        });
        const video = await videoResponse.json();
        setIsGenerating(false);
        return video;
      }
      
      if (status.status === 'failed') {
        setIsGenerating(false);
        throw new Error('Video generation failed');
      }
      
      await new Promise(resolve => setTimeout(resolve, 3000));
    }
  };

  return { generateVideo, isGenerating, progress };
}
```

## 🎯 Usage

```javascript
function VideoGenerator() {
  const { generateVideo, isGenerating, progress } = useVideoGeneration();
  const [videoURL, setVideoURL] = useState(null);

  const handleGenerate = async () => {
    const video = await generateVideo({
      topic: "Machine Learning",
      context: "Explain basic concepts with examples",
      quality: "medium"
    });
    setVideoURL(video.video_url);
  };

  return (
    <div>
      <button onClick={handleGenerate} disabled={isGenerating}>
        Generate Video
      </button>
      
      {isGenerating && <div>Progress: {progress}%</div>}
      
      {videoURL && (
        <video controls>
          <source src={videoURL} type="video/mp4" />
        </video>
      )}
    </div>
  );
}
```

## ⚠️ Error Handling

```javascript
try {
  const video = await generateVideo(config);
} catch (error) {
  if (error.status === 409) {
    // Job not ready yet, continue polling
  } else if (error.status === 401) {
    // Refresh auth token
  } else {
    // Handle other errors
    console.error('Video generation failed:', error);
  }
}
```

## 📊 Response Format

### Video URL Response
```json
{
  "job_id": "uuid",
  "status": "completed",
  "video_url": "https://s3.amazonaws.com/bucket/video.mp4",
  "download_url": "https://s3.amazonaws.com/bucket/video.mp4",
  "thumbnail_url": "/api/v1/videos/jobs/uuid/thumbnail",
  "metadata": {
    "duration": 30,
    "quality": "medium",
    "format": "mp4",
    "file_size": 1024000
  }
}
```

That's it! You're ready to integrate video generation into your frontend. See [FRONTEND_API_GUIDE.md](./FRONTEND_API_GUIDE.md) for the complete documentation.
