# File: backend/app/services/transcription_service.py
import os
import tempfile
import logging
import whisper  # Changed from whisper_cpp to whisper
from typing import Dict, List, Optional, Tuple
import json
import re

from app.core.errors import ApplicationError
from app.core.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for transcribing audio to text using OpenAI Whisper."""

    def __init__(self):
        # Initialize Whisper model
        self.model = None
        self.model_name = "medium"  # Default model size

        # Path to save models - keep this for compatibility
        self.model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "models",
            "whisper-medium.bin",  # This won't be used but kept for logging
        )

    async def _load_model(self):
        """Load the Whisper model if not already loaded."""
        if self.model is None:
            try:
                logger.info(f"Loading Whisper model: {self.model_name}")

                # Ensure models directory exists (for future compatibility)
                models_dir = os.path.dirname(self.model_path)
                os.makedirs(models_dir, exist_ok=True)

                # Load the OpenAI Whisper model
                self.model = whisper.load_model(self.model_name)
                logger.info("Whisper model loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load Whisper model: {str(e)}")
                raise ApplicationError(f"Failed to load transcription model: {str(e)}")

    async def transcribe(self, audio_path: str) -> dict:
        """
        Transcribe audio to text with timestamps.

        Args:
            audio_path: Path to the audio file

        Returns:
            Dictionary containing transcription with timestamps

        Raises:
            ApplicationError: If transcription fails
        """
        try:
            logger.info(f"Transcribing audio file: {audio_path}")

            # Load model if needed
            await self._load_model()

            # Transcribe the audio using OpenAI Whisper
            # Note: OpenAI Whisper has a different API than whisper_cpp
            result = self.model.transcribe(
                audio_path,
                language=None,  # Auto-detect language
                verbose=False,
                word_timestamps=True,  # Get word-level timestamps
            )

            # Process and return the result
            # OpenAI Whisper returns a different format, so we need to make it compatible
            # with the expected format in our application

            # Create segments with proper format
            formatted_segments = []
            for segment in result["segments"]:
                formatted_segment = {
                    "id": segment.get("id", 0),
                    "start": segment["start"],
                    "end": segment["end"],
                    "text": segment["text"],
                    "words": [],
                }

                # Add word timestamps if available
                if "words" in segment:
                    for word in segment["words"]:
                        formatted_segment["words"].append(
                            {
                                "word": word["word"],
                                "start": word["start"],
                                "end": word["end"],
                                "probability": word.get("probability", 1.0),
                            }
                        )

                formatted_segments.append(formatted_segment)

            # Compile final transcription
            transcription = {
                "text": result["text"],
                "segments": formatted_segments,
                "language": result.get("language", "en"),
            }

            logger.info(
                f"Transcription complete: {len(transcription['text'])} characters"
            )
            return transcription

        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            raise ApplicationError(f"Failed to transcribe audio: {str(e)}")
