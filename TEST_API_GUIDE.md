# Video Generation API Test Guide

This guide explains how to use the test scripts to interact with your video generation API.

## Test Scripts

### 1. `test_video_api_simple.py` (Recommended for beginners)
A simple synchronous test script using the `requests` library.

### 2. `test_video_api.py` (Advanced)
An asynchronous test script using `aiohttp` with support for concurrent testing.

## Prerequisites

1. **Install dependencies:**
   ```bash
   pip install -r test_requirements.txt
   ```

2. **Start your API server:**
   ```bash
   # Make sure your FastAPI server is running
   python main.py
   # or
   uvicorn src.app.main:app --reload --host 0.0.0.0 --port 8000
   ```

3. **Get authentication token (if required):**
   - If your API requires authentication, you'll need a Clerk JWT token
   - You can get this from your frontend application or Clerk dashboard

## Basic Usage

### Simple Health Check
```bash
python test_video_api_simple.py --health-only
```

### Basic Video Generation Test
```bash
python test_video_api_simple.py
```

### Custom Topic and Context
```bash
python test_video_api_simple.py \
  --topic "Solar System" \
  --context "Explain the planets and their characteristics with visual aids"
```

### With Authentication Token
```bash
python test_video_api_simple.py \
  --token "your_jwt_token_here" \
  --topic "Photosynthesis" \
  --context "How plants convert sunlight into energy"
```

### Skip File Downloads (faster testing)
```bash
python test_video_api_simple.py --no-download
```

### Different Server URL
```bash
python test_video_api_simple.py --url "http://your-server.com:8000"
```

## Advanced Usage

### Test Multiple Concurrent Jobs
```bash
python test_video_api.py --multiple 3
```

### Verbose Logging
```bash
python test_video_api_simple.py --verbose
```

### Full Example with All Options
```bash
python test_video_api_simple.py \
  --url "http://localhost:8000" \
  --token "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9..." \
  --topic "Machine Learning Basics" \
  --context "Introduction to neural networks and deep learning concepts" \
  --verbose
```

## What the Test Does

1. **Creates a video generation job** with your specified topic and context
2. **Monitors job progress** by polling the status endpoint every 5 seconds
3. **Downloads the completed video** (unless `--no-download` is used)
4. **Downloads the video thumbnail** in medium size
5. **Tests video streaming** endpoint
6. **Gets video metadata** including file information and processing metrics

## Expected Output

```
2024-01-15 10:30:00,123 - INFO - === Testing Health Check ===
2024-01-15 10:30:00,234 - INFO - Health check passed
2024-01-15 10:30:00,345 - INFO - === Step 1: Creating Video Generation Job ===
2024-01-15 10:30:00,456 - INFO - Creating video job: Pythagorean Theorem
2024-01-15 10:30:01,567 - INFO - Job created successfully: 550e8400-e29b-41d4-a716-446655440000
2024-01-15 10:30:01,678 - INFO - Created job: 550e8400-e29b-41d4-a716-446655440000
2024-01-15 10:30:01,789 - INFO - === Step 2: Monitoring Job Progress ===
2024-01-15 10:30:01,890 - INFO - Waiting for job 550e8400-e29b-41d4-a716-446655440000 to complete...
2024-01-15 10:30:02,001 - INFO - Job 550e8400-e29b-41d4-a716-446655440000: processing - 25.0% (content_generation)
2024-01-15 10:30:07,112 - INFO - Job 550e8400-e29b-41d4-a716-446655440000: processing - 75.0% (video_rendering)
2024-01-15 10:30:12,223 - INFO - Job 550e8400-e29b-41d4-a716-446655440000: completed - 100.0% (completed)
2024-01-15 10:30:12,334 - INFO - Job completed successfully!
2024-01-15 10:30:12,445 - INFO - === Step 3: Getting Video Metadata ===
2024-01-15 10:30:12,556 - INFO - Video metadata: {...}
2024-01-15 10:30:12,667 - INFO - === Step 4: Downloading Video File ===
2024-01-15 10:30:12,778 - INFO - Downloading video to: video_550e8400-e29b-41d4-a716-446655440000.mp4
2024-01-15 10:30:15,889 - INFO - Video downloaded successfully: video_550e8400-e29b-41d4-a716-446655440000.mp4 (15728640 bytes)
2024-01-15 10:30:15,990 - INFO - Video saved to: video_550e8400-e29b-41d4-a716-446655440000.mp4
2024-01-15 10:30:16,101 - INFO - === Step 5: Downloading Thumbnail ===
2024-01-15 10:30:16,212 - INFO - Downloading thumbnail (medium) to: thumbnail_550e8400-e29b-41d4-a716-446655440000_medium.jpg
2024-01-15 10:30:16,323 - INFO - Thumbnail downloaded successfully: thumbnail_550e8400-e29b-41d4-a716-446655440000_medium.jpg
2024-01-15 10:30:16,434 - INFO - Thumbnail saved to: thumbnail_550e8400-e29b-41d4-a716-446655440000_medium.jpg
2024-01-15 10:30:16,545 - INFO - === Step 6: Testing Video Streaming ===
2024-01-15 10:30:16,656 - INFO - Testing video streaming (auto)
2024-01-15 10:30:16,767 - INFO - Streaming test successful: received 1024 bytes
2024-01-15 10:30:16,878 - INFO - Streaming test: PASSED
2024-01-15 10:30:16,989 - INFO - === Test Completed ===
```

## Troubleshooting

### Common Issues

1. **Connection refused:**
   - Make sure your API server is running
   - Check the URL and port number

2. **Authentication errors:**
   - Verify your JWT token is valid and not expired
   - Check if the API requires authentication

3. **Job creation fails:**
   - Check the API logs for detailed error messages
   - Verify your request payload matches the expected schema

4. **Job gets stuck in processing:**
   - Check if your video generation service is running
   - Look at the server logs for processing errors

5. **Download fails:**
   - Ensure the job completed successfully
   - Check if the video file exists on the server

### Debug Mode

Enable verbose logging to see detailed request/response information:
```bash
python test_video_api_simple.py --verbose
```

### Manual Testing

You can also test individual endpoints manually using curl:

```bash
# Create a job
curl -X POST "http://localhost:8000/api/v1/videos/generate" \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer your_token_here" \
  -d '{
    "configuration": {
      "topic": "Test Topic",
      "context": "Test context",
      "quality": "medium",
      "use_rag": true
    },
    "priority": "normal"
  }'

# Check job status
curl "http://localhost:8000/api/v1/videos/jobs/YOUR_JOB_ID/status" \
  -H "Authorization: Bearer your_token_here"

# Download video
curl "http://localhost:8000/api/v1/videos/jobs/YOUR_JOB_ID/download" \
  -H "Authorization: Bearer your_token_here" \
  -o "video.mp4"
```

## API Endpoints Tested

- `POST /api/v1/videos/generate` - Create video generation job
- `GET /api/v1/videos/jobs/{job_id}/status` - Get job status
- `GET /api/v1/videos/jobs/{job_id}/download` - Download video file
- `GET /api/v1/videos/jobs/{job_id}/metadata` - Get video metadata
- `GET /api/v1/videos/jobs/{job_id}/thumbnail` - Download thumbnail
- `GET /api/v1/videos/jobs/{job_id}/stream` - Stream video

## Configuration Options

The test scripts support various video generation options:

- **Quality:** `low`, `medium`, `high`, `ultra`
- **RAG:** Enable/disable retrieval-augmented generation
- **Subtitles:** Enable/disable subtitle generation
- **Thumbnails:** Enable/disable thumbnail generation
- **Output format:** Video format (default: mp4)
- **Priority:** Job priority (`low`, `normal`, `high`, `urgent`)

## Next Steps

After successful testing, you can:

1. Integrate the API calls into your frontend application
2. Build a web interface for video generation
3. Create batch processing workflows
4. Set up monitoring and alerting for production use