# File: backend/app/services/transcription_service.py
import os
import tempfile
import logging
import json
import asyncio
from typing import Dict, List, Optional, Tuple
import torch

from app.core.errors import ApplicationError
from app.core.config import settings

logger = logging.getLogger(__name__)


class TranscriptionService:
    """Service for transcribing audio to text using Faster-Whisper."""

    def __init__(self):
        # Initialize Whisper model
        self.model = None
        self.model_name = "medium"  # Default model size

        # Configure GPU/CPU settings
        self.use_gpu = torch.cuda.is_available()
        self.device = "cuda" if self.use_gpu else "cpu"
        self.compute_type = "float16" if self.use_gpu else "float32"

        # Path to save models
        self.model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "models"
        )

        logger.info(
            f"TranscriptionService initialized with device={self.device}, compute_type={self.compute_type}"
        )

    async def _load_model(self):
        """Load the Faster-Whisper model if not already loaded."""
        if self.model is None:
            try:
                logger.info(f"Loading Faster-Whisper model: {self.model_name}")

                # Ensure models directory exists
                models_dir = self.model_path
                os.makedirs(models_dir, exist_ok=True)

                # Import here to avoid loading at startup
                from faster_whisper import WhisperModel

                # Load the Faster-Whisper model with optimized settings
                self.model = WhisperModel(
                    self.model_name,
                    device=self.device,
                    compute_type=self.compute_type,
                    download_root=self.model_path,
                    cpu_threads=(
                        4 if not self.use_gpu else 1
                    ),  # More CPU threads if no GPU
                )

                logger.info(
                    f"Faster-Whisper model loaded successfully on {self.device}"
                )

            except Exception as e:
                logger.error(f"Failed to load Faster-Whisper model: {str(e)}")
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

            # Get file size in MB to determine processing approach
            file_size_mb = os.path.getsize(audio_path) / (1024 * 1024)
            logger.info(f"Audio file size: {file_size_mb:.2f} MB")

            # Load model if needed
            await self._load_model()

            # Determine if we should use chunked processing
            if file_size_mb > 20:  # For files larger than 20MB
                return await self._chunked_transcribe(audio_path)

            # Regular processing for smaller files
            # Run in a separate thread to not block the event loop
            result = await asyncio.to_thread(self._perform_transcription, audio_path)

            logger.info(f"Transcription complete: {len(result['text'])} characters")
            return result

        except Exception as e:
            logger.error(f"Transcription error: {str(e)}")
            raise ApplicationError(f"Failed to transcribe audio: {str(e)}")

    def _perform_transcription(self, audio_path: str) -> dict:
        """Perform the actual transcription using Faster-Whisper."""
        # Configure optimized parameters
        beam_size = 5
        if self.use_gpu:
            # Use more aggressive beam search on GPU for speed
            beam_size = 3

        # Transcribe with optimized parameters
        segments, info = self.model.transcribe(
            audio_path,
            language=None,  # Auto-detect language
            beam_size=beam_size,
            word_timestamps=True,
            vad_filter=True,  # Filter out non-speech
            vad_parameters=dict(
                min_silence_duration_ms=500
            ),  # Adjust VAD for better chunking
        )

        # Format the result to match our expected format
        result = self._format_transcription(segments, info)
        return result

    async def _chunked_transcribe(self, audio_path: str) -> dict:
        """Process large audio files in chunks."""
        try:
            logger.info(f"Using chunked processing for large file: {audio_path}")

            # Split audio into chunks
            chunks = await self._split_audio(audio_path)
            logger.info(f"Split audio into {len(chunks)} chunks")

            # Process each chunk in parallel with limited concurrency
            tasks = []
            semaphore = asyncio.Semaphore(3)  # Limit concurrent processing

            async def process_chunk(chunk_path, index):
                async with semaphore:
                    logger.info(f"Processing chunk {index+1}/{len(chunks)}")
                    chunk_result = await asyncio.to_thread(
                        self._perform_transcription, chunk_path
                    )
                    return chunk_result, index

            for i, chunk_path in enumerate(chunks):
                task = asyncio.create_task(process_chunk(chunk_path, i))
                tasks.append(task)

            # Wait for all chunks to complete
            results = await asyncio.gather(*tasks)

            # Sort results by chunk index and merge
            sorted_results = sorted(results, key=lambda x: x[1])
            chunk_results = [result for result, _ in sorted_results]

            # Merge all chunk results
            final_result = self._merge_transcriptions(chunk_results)

            # Clean up temporary chunk files
            for chunk_path in chunks:
                try:
                    os.remove(chunk_path)
                except:
                    pass

            return final_result

        except Exception as e:
            logger.error(f"Chunked transcription error: {str(e)}")
            raise ApplicationError(f"Failed to process audio in chunks: {str(e)}")

    async def _split_audio(
        self, audio_path: str, chunk_seconds: int = 300
    ) -> List[str]:
        """Split audio file into smaller chunks for parallel processing."""
        try:
            # Create temp directory for chunks
            temp_dir = tempfile.mkdtemp(prefix="audio_chunks_")

            # Get audio duration using ffprobe
            duration_cmd = f"ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 {audio_path}"
            process = await asyncio.create_subprocess_shell(
                duration_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                raise Exception(f"Failed to get audio duration: {stderr.decode()}")

            duration = float(stdout.decode().strip())
            chunks_count = max(1, int(duration // chunk_seconds) + 1)

            logger.info(
                f"Audio duration: {duration:.2f}s, creating {chunks_count} chunks"
            )

            # Create chunks using ffmpeg
            chunk_paths = []

            for i in range(chunks_count):
                start_time = i * chunk_seconds
                chunk_path = os.path.join(temp_dir, f"chunk_{i:03d}.wav")

                # Use ffmpeg to extract chunk
                cmd = (
                    f"ffmpeg -y -i {audio_path} -ss {start_time} -t {chunk_seconds} "
                    f"-c:a pcm_s16le -ar 16000 -ac 1 {chunk_path}"
                )

                process = await asyncio.create_subprocess_shell(
                    cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )

                stdout, stderr = await process.communicate()

                if process.returncode != 0:
                    logger.error(f"Failed to create chunk {i}: {stderr.decode()}")
                    continue

                if os.path.exists(chunk_path):
                    chunk_paths.append(chunk_path)

            return chunk_paths

        except Exception as e:
            logger.error(f"Error splitting audio: {str(e)}")
            raise ApplicationError(f"Failed to split audio: {str(e)}")

    def _format_transcription(self, segments, info) -> dict:
        """Format Faster-Whisper output to our expected format."""
        formatted_segments = []
        full_text = ""

        for i, segment in enumerate(segments):
            # Extract segment data
            start = segment.start
            end = segment.end
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
            if segment.words:
                for word in segment.words:
                    formatted_segment["words"].append(
                        {
                            "word": word.word,
                            "start": word.start,
                            "end": word.end,
                            "probability": word.probability,
                        }
                    )

            formatted_segments.append(formatted_segment)

        # Compile final transcription
        return {
            "text": full_text,
            "segments": formatted_segments,
            "language": info.language,
        }

    def _merge_transcriptions(self, chunk_results: List[dict]) -> dict:
        """Merge multiple chunk transcriptions into a single result."""
        if not chunk_results:
            return {"text": "", "segments": [], "language": "en"}

        # Initialize with the first chunk
        merged = {
            "text": chunk_results[0]["text"],
            "segments": chunk_results[0]["segments"].copy(),
            "language": chunk_results[0]["language"],
        }

        # Track time offset for segment merging
        time_offset = merged["segments"][-1]["end"] if merged["segments"] else 0

        # Merge remaining chunks
        for i, chunk in enumerate(chunk_results[1:], 1):
            # Add space between chunks for text
            merged["text"] += " " + chunk["text"]

            # Adjust and merge segments
            for segment in chunk["segments"]:
                new_segment = {
                    "id": len(merged["segments"]),
                    "start": segment["start"] + time_offset,
                    "end": segment["end"] + time_offset,
                    "text": segment["text"],
                    "words": [],
                }

                # Adjust word timings if present
                for word in segment.get("words", []):
                    new_segment["words"].append(
                        {
                            "word": word["word"],
                            "start": word["start"] + time_offset,
                            "end": word["end"] + time_offset,
                            "probability": word.get("probability", 1.0),
                        }
                    )

                merged["segments"].append(new_segment)

            # Update time offset for next chunk
            if chunk["segments"]:
                time_offset += chunk["segments"][-1]["end"]

        return merged
