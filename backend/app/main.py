# File: backend/app/main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl
import uvicorn
import os
import uuid
import logging
from typing import Optional, List

from app.services.media_service import MediaService
from app.services.transcription_service import TranscriptionService
from app.services.summarization_service import SummarizationService
from app.services.export_service import ExportService
from app.core.config import settings
from app.core.errors import ApplicationError
from app.utils.temp_storage import TempStorage

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="QuickScript Backend API",
    description="API for converting audio/video to structured markdown",
    version="1.0.0",
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:1420"],  # Tauri default port
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize services
media_service = MediaService()
transcription_service = TranscriptionService()
summarization_service = SummarizationService()
export_service = ExportService()
temp_storage = TempStorage()

# Models
class JobStatus(BaseModel):
    job_id: str
    status: str
    progress: float
    message: Optional[str] = None
    result_url: Optional[str] = None


class URLRequest(BaseModel):
    url: HttpUrl
    options: Optional[dict] = {}


# Job tracking
job_statuses = {}


@app.get("/")
async def root():
    return {"message": "QuickScript API is running"}


@app.post("/process/file", response_model=JobStatus)
async def process_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    options: Optional[str] = Form("{}"),
):
    try:
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Save file to temp storage
        file_path = await temp_storage.save_file(file)
        
        # Initialize job status
        job_statuses[job_id] = {
            "status": "queued",
            "progress": 0.0,
            "message": "Job queued",
            "file_path": file_path,
            "result_path": None,
        }
        
        # Add processing task to background
        background_tasks.add_task(
            process_media_file,
            job_id,
            file_path,
            options,
        )
        
        return JobStatus(
            job_id=job_id,
            status="queued",
            progress=0.0,
            message="File upload successful, processing queued",
        )
        
    except Exception as e:
        logger.error(f"File upload error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/process/url", response_model=JobStatus)
async def process_url(background_tasks: BackgroundTasks, request: URLRequest):
    try:
        # Generate a unique job ID
        job_id = str(uuid.uuid4())
        
        # Initialize job status
        job_statuses[job_id] = {
            "status": "queued",
            "progress": 0.0,
            "message": "Job queued",
            "url": request.url,
            "result_path": None,
        }
        
        # Add processing task to background
        background_tasks.add_task(
            process_media_url,
            job_id,
            request.url,
            request.options,
        )
        
        return JobStatus(
            job_id=job_id,
            status="queued",
            progress=0.0,
            message="URL submitted, processing queued",
        )
        
    except Exception as e:
        logger.error(f"URL submission error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/status/{job_id}", response_model=JobStatus)
async def get_status(job_id: str):
    if job_id not in job_statuses:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_statuses[job_id]
    
    return JobStatus(
        job_id=job_id,
        status=job["status"],
        progress=job["progress"],
        message=job["message"],
        result_url=f"/download/{job_id}" if job["status"] == "complete" else None,
    )


@app.get("/download/{job_id}/{format}")
async def download_result(job_id: str, format: str):
    if job_id not in job_statuses:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_statuses[job_id]
    
    if job["status"] != "complete":
        raise HTTPException(status_code=400, detail="Job not complete")
    
    if not job["result_path"]:
        raise HTTPException(status_code=404, detail="Result not found")
    
    try:
        # Convert result to requested format
        result_path = job["result_path"]
        output_path = await export_service.export(result_path, format)
        
        return FileResponse(
            output_path,
            filename=f"quickscript_output.{format}",
            media_type=f"application/{format}",
        )
        
    except Exception as e:
        logger.error(f"Download error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/job/{job_id}")
async def cancel_job(job_id: str):
    if job_id not in job_statuses:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = job_statuses[job_id]
    
    # Clean up temp files
    if "file_path" in job and job["file_path"]:
        await temp_storage.delete_file(job["file_path"])
    
    if "result_path" in job and job["result_path"]:
        await temp_storage.delete_file(job["result_path"])
    
    # Remove job from status tracking
    del job_statuses[job_id]
    
    return {"message": "Job cancelled and resources cleaned up"}


# Background processing functions
async def process_media_file(job_id: str, file_path: str, options: dict):
    try:
        # Update job status
        job_statuses[job_id]["status"] = "processing"
        job_statuses[job_id]["progress"] = 0.1
        job_statuses[job_id]["message"] = "Extracting audio..."
        
        # Extract audio
        audio_path = await media_service.extract_audio(file_path)
        job_statuses[job_id]["progress"] = 0.3
        job_statuses[job_id]["message"] = "Transcribing audio..."
        
        # Transcribe audio
        transcription = await transcription_service.transcribe(audio_path)
        job_statuses[job_id]["progress"] = 0.7
        job_statuses[job_id]["message"] = "Generating structured text..."
        
        # Generate structured text
        markdown = await summarization_service.summarize(transcription)
        job_statuses[job_id]["progress"] = 0.9
        job_statuses[job_id]["message"] = "Finalizing output..."
        
        # Save result
        result_path = await temp_storage.save_text(markdown, prefix=job_id, suffix=".md")
        job_statuses[job_id]["result_path"] = result_path
        
        # Update job status
        job_statuses[job_id]["status"] = "complete"
        job_statuses[job_id]["progress"] = 1.0
        job_statuses[job_id]["message"] = "Processing complete"
        
        # Clean up temp audio file
        await temp_storage.delete_file(audio_path)
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        job_statuses[job_id]["status"] = "error"
        job_statuses[job_id]["message"] = f"Error: {str(e)}"
        
        # Clean up temp files
        if "file_path" in job_statuses[job_id]:
            await temp_storage.delete_file(job_statuses[job_id]["file_path"])


async def process_media_url(job_id: str, url: str, options: dict):
    try:
        # Update job status
        job_statuses[job_id]["status"] = "processing"
        job_statuses[job_id]["progress"] = 0.1
        job_statuses[job_id]["message"] = "Downloading content..."
        
        # Download media
        file_path = await media_service.download_media(url)
        job_statuses[job_id]["file_path"] = file_path
        job_statuses[job_id]["progress"] = 0.2
        job_statuses[job_id]["message"] = "Extracting audio..."
        
        # Extract audio
        audio_path = await media_service.extract_audio(file_path)
        job_statuses[job_id]["progress"] = 0.3
        job_statuses[job_id]["message"] = "Transcribing audio..."
        
        # Transcribe audio
        transcription = await transcription_service.transcribe(audio_path)
        job_statuses[job_id]["progress"] = 0.7
        job_statuses[job_id]["message"] = "Generating structured text..."
        
        # Generate structured text
        markdown = await summarization_service.summarize(transcription)
        job_statuses[job_id]["progress"] = 0.9
        job_statuses[job_id]["message"] = "Finalizing output..."
        
        # Save result
        result_path = await temp_storage.save_text(markdown, prefix=job_id, suffix=".md")
        job_statuses[job_id]["result_path"] = result_path
        
        # Update job status
        job_statuses[job_id]["status"] = "complete"
        job_statuses[job_id]["progress"] = 1.0
        job_statuses[job_id]["message"] = "Processing complete"
        
        # Clean up temp files
        await temp_storage.delete_file(audio_path)
        await temp_storage.delete_file(file_path)
        
    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        job_statuses[job_id]["status"] = "error"
        job_statuses[job_id]["message"] = f"Error: {str(e)}"
        
        # Clean up temp files
        if "file_path" in job_statuses[job_id]:
            await temp_storage.delete_file(job_statuses[job_id]["file_path"])


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
