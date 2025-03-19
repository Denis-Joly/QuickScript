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
