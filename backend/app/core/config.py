# File: backend/app/core/config.py
import os
from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional, Dict, Any, List


class Settings(BaseSettings):
    """Application settings."""

    # API Settings
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "QuickScript Backend"
    DEBUG: bool = Field(default=True)

    # CORS Settings
    CORS_ORIGINS: List[str] = ["http://localhost:1420"]  # Tauri default port

    # File Processing
    TEMP_DIR: str = "temp"
    MAX_UPLOAD_SIZE_MB: int = 2048  # 2GB max upload
    SUPPORTED_AUDIO_FORMATS: List[str] = ["mp3", "wav", "ogg", "flac", "m4a"]
    SUPPORTED_VIDEO_FORMATS: List[str] = ["mp4", "mov", "avi", "mkv", "webm"]

    # Transcription Settings
    WHISPER_MODEL: str = "medium"  # Options: tiny, base, small, medium, large
    DEFAULT_LANGUAGE: Optional[str] = None  # Auto-detect if None

    # Summarization Settings
    SUMMARIZATION_MODEL: str = "facebook/seamless-m4t-v2-large"
    MAX_SUMMARY_LENGTH: int = 4096

    # Paths
    MODELS_DIR: str = Field(default="models")

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()


# File: backend/app/core/errors.py
from fastapi import HTTPException
from typing import Any, Dict, Optional


class ApplicationError(Exception):
    """Base exception for application errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)

    def to_http_exception(self) -> HTTPException:
        """Convert to FastAPI HTTPException."""
        return HTTPException(
            status_code=self.status_code,
            detail={"message": self.message, "details": self.details},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "message": self.message,
            "status_code": self.status_code,
            "details": self.details,
        }
