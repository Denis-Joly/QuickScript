import os
import aiofiles
import aiohttp
import tempfile
import asyncio
import logging
from typing import Optional
import ffmpeg
from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

from app.core.errors import ApplicationError
from app.utils.url_utils import is_youtube_url, is_media_url

logger = logging.getLogger(__name__)


class MediaService:
    """Service for handling media file operations, including downloading and audio extraction."""

    async def download_media(self, url: str) -> str:
        """
        Download media from a URL and save to a temporary file.

        Args:
            url: The URL to download from

        Returns:
            Path to the downloaded file

        Raises:
            ApplicationError: If download fails
        """
        try:
            logger.info(f"Downloading media from {url}")

            # Create temp directory if it doesn't exist
            os.makedirs("temp", exist_ok=True)

            # Generate a temporary file name
            temp_file = tempfile.NamedTemporaryFile(
                delete=False, dir="temp", suffix=".tmp"
            )
            temp_file_path = temp_file.name
            temp_file.close()

            if is_youtube_url(url) or not is_media_url(url):
                # Use yt-dlp for YouTube or other streaming sites
                ydl_opts = {
                    "format": "bestaudio/best",
                    "outtmpl": temp_file_path,
                    "quiet": True,
                    "no_warnings": True,
                }

                with YoutubeDL(ydl_opts) as ydl:
                    ydl.download([url])

                logger.info(f"Downloaded media to {temp_file_path}")
                return temp_file_path

            else:
                # For direct media URLs, use aiohttp
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        if response.status != 200:
                            raise ApplicationError(
                                f"Failed to download media: HTTP {response.status}"
                            )

                        async with aiofiles.open(temp_file_path, "wb") as f:
                            await f.write(await response.read())

                logger.info(f"Downloaded media to {temp_file_path}")
                return temp_file_path

        except DownloadError as e:
            logger.error(f"yt-dlp error: {str(e)}")
            raise ApplicationError(f"Failed to download media: {str(e)}")
        except Exception as e:
            logger.error(f"Download error: {str(e)}")
            raise ApplicationError(f"Failed to download media: {str(e)}")

    async def extract_audio(self, file_path: str, output_format: str = "wav") -> str:
        """
        Extract audio from a media file.

        Args:
            file_path: Path to the media file
            output_format: Audio format to extract to (default: wav)

        Returns:
            Path to the extracted audio file

        Raises:
            ApplicationError: If extraction fails
        """
        try:
            logger.info(f"Extracting audio from {file_path}")

            # Create output file path
            output_path = os.path.splitext(file_path)[0] + f".{output_format}"

            # Run FFmpeg process asynchronously
            process = await asyncio.create_subprocess_exec(
                "ffmpeg",
                "-i",
                file_path,
                "-vn",  # No video
                "-acodec",
                "pcm_s16le",  # PCM 16-bit audio for maximum compatibility
                "-ar",
                "16000",  # 16kHz sample rate (optimal for Whisper)
                "-ac",
                "1",  # Mono channel
                "-y",  # Overwrite output file
                output_path,
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

            logger.info(f"Extracted audio to {output_path}")
            return output_path

        except Exception as e:
            logger.error(f"Audio extraction error: {str(e)}")
            raise ApplicationError(f"Failed to extract audio: {str(e)}")
