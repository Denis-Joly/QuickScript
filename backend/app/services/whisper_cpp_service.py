# File: backend/app/services/whisper_cpp_service.py
import os
import logging
import asyncio
from typing import Dict, List

from app.core.errors import ApplicationError

logger = logging.getLogger(__name__)


class WhisperCppService:
    """Service for transcribing audio using pywhispercpp with GPU acceleration."""

    def __init__(self):
        # Model configuration
        self.model_name = "base.en"  # Use base.en model for speed
        self.model = None

        # Set up parameters - keep it minimal to start
        self.params = {
            "n_threads": 6,  # Use multiple threads
            "print_realtime": False,  # Don't print realtime results
            "print_progress": True,  # Show progress during transcription
        }

        # Allow whisper.cpp to automatically use the best available backend
        logger.info(f"WhisperCppService initialized with model {self.model_name}")

    async def _load_model(self):
        """Load the model if not already loaded."""
        if self.model is None:
            try:
                # Import here to avoid loading at startup
                from pywhispercpp.model import Model

                logger.info(f"Loading whisper.cpp model: {self.model_name}")
                # Let pywhispercpp handle model downloading and initialization
                self.model = Model(self.model_name, **self.params)
                logger.info("Model loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load whisper.cpp model: {str(e)}")
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

            # Run transcription in a separate thread to not block the event loop
            segments = await asyncio.to_thread(self.model.transcribe, audio_path)

            # Format the result to match our expected format
            result = self._format_transcription(segments)

            logger.info(f"Transcription complete: {len(result['text'])} characters")
            return result

        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            raise ApplicationError(f"Failed to transcribe audio: {str(e)}")

    def _format_transcription(self, segments) -> dict:
        """Format pywhispercpp output to match our expected format."""
        formatted_segments = []
        full_text = ""

        for i, segment in enumerate(segments):
            # Extract segment data
            start = segment.t0  # Start time in seconds
            end = segment.t1  # End time in seconds
            text = segment.text.strip()

            # Skip empty segments
            if not text:
                continue

            # Add to full text with spacing
            if i > 0 and not full_text.endswith(" "):
                full_text += " "
            full_text += text

            # Create segment with word-level timestamps
            formatted_segment = {
                "id": i,
                "start": start,
                "end": end,
                "text": text,
                "words": [],
            }

            # Add word-level timestamps if available
            if hasattr(segment, "words") and segment.words:
                for word in segment.words:
                    formatted_segment["words"].append(
                        {
                            "word": word.word,
                            "start": word.t0,
                            "end": word.t1,
                            "probability": 1.0,  # pywhispercpp doesn't provide probabilities
                        }
                    )

            formatted_segments.append(formatted_segment)

        # Compile final transcription
        return {
            "text": full_text,
            "segments": formatted_segments,
            "language": "en",
        }
