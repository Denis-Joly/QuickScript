# QuickScript API Documentation

## Endpoints

### POST /process/file
Upload and process a local media file.

**Request**:
- Multipart form data with 'file' field

**Response**:
```json
{
  "job_id": "string",
  "status": "queued",
  "progress": 0,
  "message": "Job queued"
}
```

### POST /process/url
Process a media URL.

**Request**:
```json
{
  "url": "https://example.com/video.mp4",
  "options": {}
}
```

**Response**:
```json
{
  "job_id": "string",
  "status": "queued",
  "progress": 0,
  "message": "Job queued"
}
```

### GET /status/{job_id}
Get the status of a job.

**Response**:
```json
{
  "job_id": "string",
  "status": "processing",
  "progress": 0.5,
  "message": "Transcribing audio...",
  "result_url": null
}
```

### GET /download/{job_id}/{format}
Download the result in the specified format.

**Parameters**:
- job_id: Job ID
- format: Output format (md, txt, pdf)

**Response**:
- File download

### DELETE /job/{job_id}
Cancel a job and clean up resources.

**Response**:
```json
{
  "message": "Job cancelled and resources cleaned up"
}
```

