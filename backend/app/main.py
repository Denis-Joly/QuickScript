# File: backend/app/main.py
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel, HttpUrl
import uvicorn
import asyncio
import os
import uuid
import logging
from typing import Optional, List

from app.services.media_service import MediaService
from app.services.transcription_service import TranscriptionService
from app.services.whisper_cpp_service import WhisperCppService
from app.services.summarization_service import SummarizationService
from app.services.export_service import ExportService
from app.services.checkpoint_service import CheckpointService

from app.core.config import settings
from app.core.errors import ApplicationError
from app.utils.temp_storage import TempStorage

# Initialize checkpoint service in app startup
checkpoint_service = CheckpointService()

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
transcription_service = WhisperCppService()  # TranscriptionService()
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
# In main.py
from app.services.checkpoint_service import CheckpointService

# Initialize checkpoint service in app startup
checkpoint_service = CheckpointService()


# Replace the process_media_file function
async def process_media_file(job_id: str, file_path: str, options: dict):
    try:
        # Update job status
        job_statuses[job_id]["status"] = "processing"
        job_statuses[job_id]["progress"] = 0.1
        job_statuses[job_id]["message"] = "Analyzing media file..."

        # Step 1: Check if we have a complete checkpoint
        complete_checkpoint = await checkpoint_service.load_checkpoint(
            job_id, file_path, "complete"
        )

        if complete_checkpoint and os.path.exists(
            complete_checkpoint.get("result_path", "")
        ):
            # Restore from complete checkpoint
            job_statuses[job_id]["result_path"] = complete_checkpoint["result_path"]
            job_statuses[job_id]["status"] = "complete"
            job_statuses[job_id]["progress"] = 1.0
            job_statuses[job_id][
                "message"
            ] = "Processing complete (restored from checkpoint)"
            logger.info(f"Restored completed job {job_id} from checkpoint")
            return

        # Step 2: Extract audio with checkpoint support
        job_statuses[job_id]["progress"] = 0.2
        job_statuses[job_id]["message"] = "Extracting audio..."

        # Check for audio extraction checkpoint
        audio_checkpoint = await checkpoint_service.load_checkpoint(
            job_id, file_path, "extract_audio"
        )

        if audio_checkpoint and os.path.exists(audio_checkpoint.get("audio_path", "")):
            audio_path = audio_checkpoint["audio_path"]
            logger.info(f"Restored audio path from checkpoint for job {job_id}")
        else:
            audio_path = await media_service.extract_audio(file_path, job_id)

        job_statuses[job_id]["progress"] = 0.3
        job_statuses[job_id]["message"] = "Transcribing audio..."

        # Step 3: Transcribe audio with checkpoint support
        transcription_checkpoint = await checkpoint_service.load_checkpoint(
            job_id, audio_path, "transcription"
        )

        if transcription_checkpoint:
            transcription = transcription_checkpoint
            logger.info(f"Restored transcription from checkpoint for job {job_id}")
        else:
            transcription = await transcription_service.transcribe(audio_path)
            # Save transcription checkpoint
            await checkpoint_service.save_checkpoint(
                job_id, audio_path, "transcription", transcription
            )

        job_statuses[job_id]["progress"] = 0.7
        job_statuses[job_id]["message"] = "Generating structured text..."

        # Step 4: Generate structured text with checkpoint support
        markdown_checkpoint = await checkpoint_service.load_checkpoint(
            job_id, audio_path, "markdown"
        )

        if markdown_checkpoint and markdown_checkpoint.get("markdown"):
            markdown = markdown_checkpoint["markdown"]
            logger.info(f"Restored markdown from checkpoint for job {job_id}")
        else:
            markdown = await summarization_service.summarize(transcription)
            # Save markdown checkpoint
            await checkpoint_service.save_checkpoint(
                job_id, audio_path, "markdown", {"markdown": markdown}
            )

        job_statuses[job_id]["progress"] = 0.9
        job_statuses[job_id]["message"] = "Finalizing output..."

        # Step 5: Save result
        result_path = await temp_storage.save_text(
            markdown, prefix=job_id, suffix=".md"
        )
        job_statuses[job_id]["result_path"] = result_path

        # Save complete checkpoint
        await checkpoint_service.save_checkpoint(
            job_id,
            file_path,
            "complete",
            {"result_path": result_path, "transcription": transcription},
        )

        # Update job status
        job_statuses[job_id]["status"] = "complete"
        job_statuses[job_id]["progress"] = 1.0
        job_statuses[job_id]["message"] = "Processing complete"

        # Clean up temp audio file
        if audio_path != file_path:  # Only delete if we created a new audio file
            await temp_storage.delete_file(audio_path)

    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        job_statuses[job_id]["status"] = "error"
        job_statuses[job_id]["message"] = f"Error: {str(e)}"

        # Clean up temp files
        if "file_path" in job_statuses[job_id]:
            await temp_storage.delete_file(job_statuses[job_id]["file_path"])


# In main.py, also replace process_media_url
async def process_media_url(job_id: str, url: str, options: dict):
    try:
        # Check for complete checkpoint first
        complete_checkpoint = await checkpoint_service.load_checkpoint(
            job_id, url, "complete"
        )

        if complete_checkpoint and os.path.exists(
            complete_checkpoint.get("result_path", "")
        ):
            # Restore from complete checkpoint
            job_statuses[job_id]["result_path"] = complete_checkpoint["result_path"]
            job_statuses[job_id]["status"] = "complete"
            job_statuses[job_id]["progress"] = 1.0
            job_statuses[job_id][
                "message"
            ] = "Processing complete (restored from checkpoint)"
            logger.info(f"Restored completed job {job_id} from checkpoint")
            return

        # Update job status
        job_statuses[job_id]["status"] = "processing"
        job_statuses[job_id]["progress"] = 0.1
        job_statuses[job_id]["message"] = "Downloading content..."

        # Step 1: Download media with checkpoint support
        download_checkpoint = await checkpoint_service.load_checkpoint(
            job_id, url, "download_media"
        )

        if download_checkpoint and os.path.exists(
            download_checkpoint.get("file_path", "")
        ):
            file_path = download_checkpoint["file_path"]
            logger.info(f"Restored download from checkpoint for job {job_id}")
        else:
            file_path = await media_service.download_media(url, job_id)

        job_statuses[job_id]["file_path"] = file_path

        # From here, proceed with the same logic as process_media_file
        # by forwarding to the shared implementation
        await process_media_file(job_id, file_path, options)

    except Exception as e:
        logger.error(f"Processing error for job {job_id}: {str(e)}")
        job_statuses[job_id]["status"] = "error"
        job_statuses[job_id]["message"] = f"Error: {str(e)}"

        # Clean up temp files
        if "file_path" in job_statuses[job_id]:
            await temp_storage.delete_file(job_statuses[job_id]["file_path"])


# In main.py, add these handlers
@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    # Create temp dirs if they don't exist
    os.makedirs("temp", exist_ok=True)

    # Clean up old temp files and checkpoints
    try:
        await temp_storage.cleanup(max_age_hours=24)
        await checkpoint_service.clean_old_checkpoints(max_age_hours=24)
    except Exception as e:
        logger.error(f"Startup cleanup error: {str(e)}")


# Schedule periodic cleanup
async def periodic_cleanup():
    """Run cleanup tasks periodically."""
    while True:
        try:
            # Wait for 1 hour
            await asyncio.sleep(3600)

            # Run cleanup tasks
            await temp_storage.cleanup(max_age_hours=24)
            await checkpoint_service.clean_old_checkpoints(max_age_hours=24)

            logger.info("Completed periodic cleanup")

        except asyncio.CancelledError:
            # Handle graceful shutdown
            break
        except Exception as e:
            logger.error(f"Periodic cleanup error: {str(e)}")
            # Wait a bit before retrying
            await asyncio.sleep(60)


# Start the cleanup task
@app.on_event("startup")
async def start_cleanup_task():
    """Start the periodic cleanup task."""
    asyncio.create_task(periodic_cleanup())


# Clean up on shutdown
@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("Application shutting down, cleaning up resources")
    # This will only clean temporary files older than 24 hours
    # to avoid disrupting in-progress tasks
    try:
        await temp_storage.cleanup(max_age_hours=24)
    except Exception as e:
        logger.error(f"Shutdown cleanup error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
