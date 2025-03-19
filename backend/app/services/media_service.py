# File: backend/app/services/media_service.py
import os
import aiofiles
import aiohttp
import tempfile
import asyncio
import logging
import subprocess
import shutil
from typing import Optional, Tuple, Dict
from urllib.parse import urlparse

from app.core.errors import ApplicationError
from app.utils.url_utils import is_youtube_url, is_media_url
from app.services.checkpoint_service import CheckpointService

logger = logging.getLogger(__name__)


class MediaService:
    """Service for handling media file operations, including downloading and audio extraction."""

    def __init__(self):
        """Initialize the media service."""
        # Set up temp directory
        self.temp_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "temp"
        )
        os.makedirs(self.temp_dir, exist_ok=True)

        # Initialize checkpoint service
        self.checkpoint_service = CheckpointService()

        # Detect GPU availability for hardware acceleration
        self.has_gpu = self._check_gpu_available()
        logger.info(f"Media service initialized with GPU acceleration: {self.has_gpu}")

    def _check_gpu_available(self) -> bool:
        """Check if GPU acceleration is available for FFmpeg."""
        try:
            # Check for NVIDIA GPU (NVENC)
            result = subprocess.run(
                ["ffmpeg", "-hide_banner", "-encoders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )

            return "nvenc" in result.stdout.lower()

        except Exception as e:
            logger.warning(f"Error checking GPU availability: {str(e)}")
            return False

    async def download_media(self, url: str, job_id: str = None) -> str:
        """
        Download media from a URL and save to a temporary file.

        Args:
            url: The URL to download from
            job_id: Optional job ID for checkpointing

        Returns:
            Path to the downloaded file

        Raises:
            ApplicationError: If download fails
        """
        try:
            logger.info(f"Downloading media from {url}")

            # Create temp directory if it doesn't exist
            os.makedirs(self.temp_dir, exist_ok=True)

            # Generate a temporary file name with a proper extension
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, dir=self.temp_dir, suffix=".tmp"
            )
            temp_file_path = temp_file.name
            temp_file.close()

            # Check for checkpoint if job_id is provided
            if job_id:
                checkpoint_data = await self.checkpoint_service.load_checkpoint(
                    job_id, url, "download_media"
                )

                if checkpoint_data and os.path.exists(
                    checkpoint_data.get("file_path", "")
                ):
                    logger.info(f"Resuming download from checkpoint for {url}")
                    return checkpoint_data.get("file_path")

            if is_youtube_url(url) or not is_media_url(url):
                # Use yt-dlp for YouTube or other streaming sites with optimized settings
                output_path = await self._download_with_ytdlp(url, temp_file_path)

                # Save checkpoint if job_id is provided
                if job_id:
                    await self.checkpoint_service.save_checkpoint(
                        job_id, url, "download_media", {"file_path": output_path}
                    )

                return output_path
            else:
                # For direct media URLs, use optimized aiohttp
                output_path = await self._download_with_aiohttp(url, temp_file_path)

                # Save checkpoint
                if job_id:
                    await self.checkpoint_service.save_checkpoint(
                        job_id, url, "download_media", {"file_path": output_path}
                    )

                return output_path

        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            raise ApplicationError(f"Failed to download media: {str(e)}")

    async def _download_with_ytdlp(self, url: str, temp_file_path: str) -> str:
        """Download media using yt-dlp with optimized settings."""
        try:
            # Create a better output filename with extension
            output_template = os.path.splitext(temp_file_path)[0] + ".%(ext)s"

            # Configure yt-dlp for optimal downloads
            ydl_opts = {
                "format": "bestaudio/best",  # Prefer audio for faster downloads
                "outtmpl": output_template,
                "quiet": True,
                "no_warnings": True,
                "extract_audio": True,  # Extract audio for efficient processing
                "postprocessors": [
                    {
                        "key": "FFmpegExtractAudio",
                        "preferredcodec": "wav",  # Convert to WAV for better compatibility
                        "preferredquality": "192",
                    }
                ],
                "noprogress": True,
                "retries": 3,  # Retry a few times on failure
                "fragment_retries": 3,
                "skip_download": False,
                "keepvideo": False,  # Don't keep video after extracting audio
            }

            # Run yt-dlp in a way that doesn't block the event loop
            process = await asyncio.create_subprocess_exec(
                "yt-dlp",
                url,
                "--format",
                ydl_opts["format"],
                "--output",
                ydl_opts["outtmpl"],
                "--extract-audio",
                "--audio-format",
                "wav",
                "--audio-quality",
                "192",
                "--no-progress",
                "--quiet",
                "--no-warnings",
                "--retries",
                "3",
                "--fragment-retries",
                "3",
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(
                    f"yt-dlp error: {stderr.decode() if stderr else 'Unknown error'}"
                )
                raise Exception(
                    f"Failed to download with yt-dlp: {stderr.decode() if stderr else 'Unknown error'}"
                )

            # Find the output file (it will have .wav extension now)
            output_path = os.path.splitext(temp_file_path)[0] + ".wav"
            if not os.path.exists(output_path):
                # Try to find any file with the same base name
                base_dir = os.path.dirname(temp_file_path)
                base_name = os.path.basename(os.path.splitext(temp_file_path)[0])

                for filename in os.listdir(base_dir):
                    if filename.startswith(base_name) and filename.endswith(
                        (".wav", ".mp3", ".m4a")
                    ):
                        output_path = os.path.join(base_dir, filename)
                        break

            if not os.path.exists(output_path):
                raise Exception("Failed to locate downloaded file")

            logger.info(f"Downloaded media to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"yt-dlp download error: {str(e)}")
            raise ApplicationError(f"Failed to download media: {str(e)}")

    async def _download_with_aiohttp(self, url: str, temp_file_path: str) -> str:
        """Download media using aiohttp with streaming and progress tracking."""
        try:
            # Add proper extension based on URL
            parsed_url = urlparse(url)
            path = parsed_url.path.lower()

            # Determine file extension from URL
            extension = os.path.splitext(path)[1]
            if not extension:
                extension = ".mp3"  # Default to mp3 if no extension

            # Create a better temp file with proper extension
            output_path = os.path.splitext(temp_file_path)[0] + extension

            # Download with aiohttp in chunks
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    if response.status != 200:
                        raise ApplicationError(
                            f"Failed to download media: HTTP {response.status}"
                        )

                    # Get content length if available
                    total_size = int(response.headers.get("content-length", 0))
                    downloaded = 0

                    # Stream to file
                    async with aiofiles.open(output_path, "wb") as f:
                        chunk_size = 64 * 1024  # 64KB chunks
                        async for chunk in response.content.iter_chunked(chunk_size):
                            await f.write(chunk)
                            downloaded += len(chunk)

                            # Log progress for large files
                            if (
                                total_size > 10 * 1024 * 1024
                                and downloaded % (5 * 1024 * 1024) == 0
                            ):
                                percent = (
                                    (downloaded / total_size) * 100 if total_size else 0
                                )
                                logger.debug(
                                    f"Download progress: {percent:.1f}% ({downloaded/(1024*1024):.1f} MB)"
                                )

            logger.info(f"Downloaded media to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"aiohttp download error: {str(e)}")
            raise ApplicationError(f"Failed to download media: {str(e)}")

    async def extract_audio(self, file_path: str, job_id: str = None) -> str:
        """
        Extract audio from a media file with optimized settings.

        Args:
            file_path: Path to the media file
            job_id: Optional job ID for checkpointing

        Returns:
            Path to the extracted audio file

        Raises:
            ApplicationError: If extraction fails
        """
        try:
            logger.info(f"Extracting audio from {file_path}")

            # Check if file is already an audio file
            if await self._is_audio_file(file_path):
                logger.info(f"File is already audio, optimizing format")
                return await self._optimize_audio_format(file_path, job_id)

            # Check for checkpoint if job_id is provided
            if job_id:
                checkpoint_data = await self.checkpoint_service.load_checkpoint(
                    job_id, file_path, "extract_audio"
                )

                if checkpoint_data and os.path.exists(
                    checkpoint_data.get("audio_path", "")
                ):
                    logger.info(
                        f"Resuming from audio extraction checkpoint for {file_path}"
                    )
                    return checkpoint_data.get("audio_path")

            # Create output file path
            output_path = os.path.splitext(file_path)[0] + ".wav"

            # Set up ffmpeg command with optimized parameters
            ffmpeg_cmd = ["ffmpeg", "-i", file_path]

            # Add GPU acceleration if available
            if self.has_gpu:
                ffmpeg_cmd.extend(["-hwaccel", "cuda"])

            # Add optimization parameters
            ffmpeg_cmd.extend(
                [
                    "-vn",  # No video
                    "-acodec",
                    "pcm_s16le",  # PCM 16-bit audio for maximum compatibility
                    "-ar",
                    "16000",  # 16kHz sample rate (optimal for Whisper)
                    "-ac",
                    "1",  # Mono channel
                    "-threads",
                    "4",  # Use 4 threads
                    "-y",  # Overwrite output file
                    "-loglevel",
                    "error",  # Minimal logging
                    output_path,
                ]
            )

            # Run FFmpeg process
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for FFmpeg to complete
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"FFmpeg error: {stderr.decode()}")
                raise ApplicationError(
                    f"Failed to extract audio: FFmpeg error {process.returncode}"
                )

            # Save checkpoint
            if job_id:
                await self.checkpoint_service.save_checkpoint(
                    job_id, file_path, "extract_audio", {"audio_path": output_path}
                )

            logger.info(f"Extracted audio to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Audio extraction error: {str(e)}")
            raise ApplicationError(f"Failed to extract audio: {str(e)}")

    async def _optimize_audio_format(self, file_path: str, job_id: str = None) -> str:
        """Optimize audio format for transcription."""
        try:
            # Check if audio is already in optimal format (16kHz mono WAV)
            is_optimal = await self._check_audio_format(file_path)
            if is_optimal:
                logger.info(f"Audio already in optimal format: {file_path}")
                return file_path

            # Create output file path
            output_path = os.path.splitext(file_path)[0] + "_optimized.wav"

            # Set up ffmpeg command with optimized parameters
            ffmpeg_cmd = ["ffmpeg", "-i", file_path]

            # Add optimization parameters
            ffmpeg_cmd.extend(
                [
                    "-acodec",
                    "pcm_s16le",  # PCM 16-bit audio
                    "-ar",
                    "16000",  # 16kHz sample rate
                    "-ac",
                    "1",  # Mono channel
                    "-y",  # Overwrite output file
                    output_path,
                ]
            )

            # Run FFmpeg process
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait for FFmpeg to complete
            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.error(f"FFmpeg optimization error: {stderr.decode()}")
                # Return original file if optimization fails
                return file_path

            # Save checkpoint
            if job_id:
                await self.checkpoint_service.save_checkpoint(
                    job_id, file_path, "optimize_audio", {"audio_path": output_path}
                )

            logger.info(f"Optimized audio to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Audio optimization error: {str(e)}")
            # Return original file if optimization fails
            return file_path

    async def _is_audio_file(self, file_path: str) -> bool:
        """Check if a file is an audio file."""
        try:
            # Get file extension
            _, ext = os.path.splitext(file_path)
            ext = ext.lower()

            # Check against common audio extensions
            audio_extensions = [".mp3", ".wav", ".ogg", ".flac", ".m4a", ".aac"]
            if ext in audio_extensions:
                return True

            # If extension check is inconclusive, probe with ffmpeg
            process = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-show_entries",
                "stream=codec_type",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return False

            # Check if file contains only audio streams
            streams = stdout.decode().strip().split("\n")
            return (
                all(stream.strip() == "audio" for stream in streams)
                and len(streams) > 0
            )

        except Exception as e:
            logger.error(f"Error checking if file is audio: {str(e)}")
            return False

    async def _check_audio_format(self, file_path: str) -> bool:
        """Check if audio is already in optimal format for transcription."""
        try:
            # Probe audio format
            process = await asyncio.create_subprocess_exec(
                "ffprobe",
                "-v",
                "error",
                "-select_streams",
                "a:0",
                "-show_entries",
                "stream=codec_name,sample_rate,channels",
                "-of",
                "json",
                file_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                return False

            # Parse JSON output
            import json

            probe_data = json.loads(stdout.decode())

            if "streams" not in probe_data or not probe_data["streams"]:
                return False

            stream = probe_data["streams"][0]

            # Check if format is optimal (16kHz mono PCM)
            is_optimal = (
                stream.get("codec_name") == "pcm_s16le"
                and int(stream.get("sample_rate", 0)) == 16000
                and int(stream.get("channels", 0)) == 1
            )

            return is_optimal

        except Exception as e:
            logger.error(f"Error checking audio format: {str(e)}")
            return False
