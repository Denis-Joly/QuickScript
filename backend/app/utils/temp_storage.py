import os
import tempfile
import aiofiles
import shutil
import logging
from typing import Optional
import uuid

from app.core.errors import ApplicationError

logger = logging.getLogger(__name__)

class TempStorage:
    """Utility class for managing temporary file storage."""
    
    def __init__(self, base_dir: str = "temp"):
        """
        Initialize temp storage.
        
        Args:
            base_dir: Base directory for temporary files
        """
        self.base_dir = base_dir
        os.makedirs(base_dir, exist_ok=True)
        logger.info(f"Initialized temporary storage in {base_dir}")
    
    async def save_file(self, file) -> str:
        """
        Save an uploaded file to temporary storage.
        
        Args:
            file: FastAPI UploadFile object
            
        Returns:
            Path to the saved file
            
        Raises:
            ApplicationError: If file save fails
        """
        try:
            # Generate unique filename
            filename = f"{uuid.uuid4()}_{file.filename}"
            filepath = os.path.join(self.base_dir, filename)
            
            # Save file
            async with aiofiles.open(filepath, 'wb') as f:
                content = await file.read()
                await f.write(content)
            
            logger.info(f"Saved file to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"File save error: {str(e)}")
            raise ApplicationError(f"Failed to save file: {str(e)}")
    
    async def save_text(self, text: str, prefix: str = "", suffix: str = "") -> str:
        """
        Save text content to a temporary file.
        
        Args:
            text: Text content to save
            prefix: Filename prefix
            suffix: Filename suffix
            
        Returns:
            Path to the saved file
            
        Raises:
            ApplicationError: If text save fails
        """
        try:
            # Generate unique filename
            filename = f"{prefix}_{uuid.uuid4()}{suffix}"
            filepath = os.path.join(self.base_dir, filename)
            
            # Save text
            async with aiofiles.open(filepath, 'w') as f:
                await f.write(text)
            
            logger.info(f"Saved text to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Text save error: {str(e)}")
            raise ApplicationError(f"Failed to save text: {str(e)}")
    
    async def delete_file(self, filepath: str) -> bool:
        """
        Delete a temporary file.
        
        Args:
            filepath: Path to the file to delete
            
        Returns:
            True if deletion was successful
            
        Raises:
            ApplicationError: If file deletion fails
        """
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
                logger.info(f"Deleted file {filepath}")
                return True
            else:
                logger.info(f"File not found for deletion: {filepath}")
                return False
                
        except Exception as e:
            logger.error(f"File deletion error: {str(e)}")
            raise ApplicationError(f"Failed to delete file: {str(e)}")
    
    async def cleanup(self, max_age_hours: int = 24) -> int:
        """
        Clean up old temporary files.
        
        Args:
            max_age_hours: Maximum age of files to keep (in hours)
            
        Returns:
            Number of files deleted
            
        Raises:
            ApplicationError: If cleanup fails
        """
        try:
            import time
            
            now = time.time()
            count = 0
            
            for filename in os.listdir(self.base_dir):
                filepath = os.path.join(self.base_dir, filename)
                
                # Skip directories
                if os.path.isdir(filepath):
                    continue
                
                # Check file age
                file_age_hours = (now - os.path.getmtime(filepath)) / 3600
                
                if file_age_hours > max_age_hours:
                    os.remove(filepath)
                    count += 1
            
            logger.info(f"Cleaned up {count} old files")
            return count
            
        except Exception as e:
            logger.error(f"Cleanup error: {str(e)}")
            raise ApplicationError(f"Failed to clean up temporary files: {str(e)}")


# File: backend/app/utils/url_utils.py
import re
import logging
from typing import List, Optional
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

def is_youtube_url(url: str) -> bool:
    """
    Check if a URL is a YouTube video.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL is a YouTube video
    """
    youtube_patterns = [
        r'(https?://)?(www\.)?youtube\.com/watch\?v=[\w-]+',
        r'(https?://)?(www\.)?youtu\.be/[\w-]+'
    ]
    
    for pattern in youtube_patterns:
        if re.match(pattern, url):
            return True
    
    return False

def is_media_url(url: str) -> bool:
    """
    Check if a URL points to a media file.
    
    Args:
        url: URL to check
        
    Returns:
        True if URL points to a media file
    """
    # Check file extension
    parsed_url = urlparse(url)
    path = parsed_url.path.lower()
    
    media_extensions = [
        # Audio
        '.mp3', '.wav', '.ogg', '.flac', '.aac', '.m4a',
        # Video
        '.mp4', '.mov', '.avi', '.mkv', '.webm', '.flv'
    ]
    
    for ext in media_extensions:
        if path.endswith(ext):
            return True
    
    return False

def extract_video_id(url: str) -> Optional[str]:
    """
    Extract video ID from a YouTube URL.
    
    Args:
        url: YouTube URL
        
    Returns:
        Video ID or None if not a valid YouTube URL
    """
    if not is_youtube_url(url):
        return None
    
    # youtube.com/watch?v=VIDEO_ID
    match = re.search(r'youtube\.com/watch\?v=([\w-]+)', url)
    if match:
        return match.group(1)
    
    # youtu.be/VIDEO_ID
    match = re.search(r'youtu\.be/([\w-]+)', url)
    if match:
        return match.group(1)
    
    return None

def get_supported_sites() -> List[str]:
    """
    Get list of supported sites for media extraction.
    
    Returns:
        List of supported site names
    """
    # These are just examples, yt-dlp supports many more
    return [
        "YouTube",
        "Vimeo",
        "SoundCloud",
        "Spotify",
        "Facebook",
        "Twitter",
        "Instagram",
        "TikTok",
        "Twitch",
        "Dailymotion"
    ]


# File: backend/app/utils/file_utils.py
import os
import mimetypes
import magic
import logging
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def get_file_type(file_path: str) -> Tuple[str, str]:
    """
    Get MIME type and extension for a file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Tuple of (mime_type, extension)
    """
    try:
        # Use python-magic for better MIME type detection
        mime = magic.Magic(mime=True)
        mime_type = mime.from_file(file_path)
        
        # Get extension
        _, extension = os.path.splitext(file_path)
        if not extension and mime_type:
            # Try to guess extension from MIME type
            extension = mimetypes.guess_extension(mime_type) or ""
        
        return mime_type, extension.lstrip(".")
        
    except Exception as e:
        logger.error(f"Error getting file type: {str(e)}")
        # Fallback to mimetypes
        mime_type, _ = mimetypes.guess_type(file_path)
        _, extension = os.path.splitext(file_path)
        return mime_type or "application/octet-stream", extension.lstrip(".")

def is_audio_file(file_path: str) -> bool:
    """
    Check if a file is an audio file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file is an audio file
    """
    mime_type, _ = get_file_type(file_path)
    return mime_type.startswith("audio/")

def is_video_file(file_path: str) -> bool:
    """
    Check if a file is a video file.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if file is a video file
    """
    mime_type, _ = get_file_type(file_path)
    return mime_type.startswith("video/")

def get_file_size_mb(file_path: str) -> float:
    """
    Get file size in megabytes.
    
    Args:
        file_path: Path to the file
        
    Returns:
        File size in MB
    """
    return os.path.getsize(file_path) / (1024 * 1024)

def get_media_duration(file_path: str) -> Optional[float]:
    """
    Get duration of a media file in seconds.
    
    Args:
        file_path: Path to the media file
        
    Returns:
        Duration in seconds or None if unavailable
    """
    try:
        import ffmpeg
        
        probe = ffmpeg.probe(file_path)
        # Get duration from the first stream that has it
        for stream in probe.get("streams", []):
            if "duration" in stream:
                return float(stream["duration"])
        
        # Or from format information
        if "format" in probe and "duration" in probe["format"]:
            return float(probe["format"]["duration"])
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting media duration: {str(e)}")
        return None
