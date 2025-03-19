# File: backend/app/services/checkpoint_service.py
import asyncio
import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional

import aiofiles

logger = logging.getLogger(__name__)


class CheckpointService:
    """Service for managing processing checkpoints to enable resumable operations."""

    def __init__(self):
        """Initialize the checkpoint service."""
        # Set up checkpoint directory
        self.checkpoint_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "checkpoints"
        )
        os.makedirs(self.checkpoint_dir, exist_ok=True)

        # Lock for preventing concurrent checkpoint operations
        self._lock = asyncio.Lock()

    async def save_checkpoint(
        self, job_id: str, file_path: str, stage: str, data: Dict[str, Any]
    ) -> str:
        """
        Save a processing checkpoint.

        Args:
            job_id: ID of the current job
            file_path: Path to the source file being processed
            stage: Current processing stage (e.g., 'audio_extraction', 'transcription')
            data: Checkpoint data to save

        Returns:
            Checkpoint ID
        """
        async with self._lock:
            try:
                # Generate a checkpoint ID from job_id and stage
                checkpoint_id = f"{job_id}_{stage}"

                # Calculate file hash for verification
                file_hash = await self._calculate_file_hash(file_path)

                # Create checkpoint data
                checkpoint = {
                    "job_id": job_id,
                    "file_path": file_path,
                    "file_hash": file_hash,
                    "stage": stage,
                    "timestamp": datetime.now().isoformat(),
                    "data": data,
                }

                # Save to checkpoint file
                checkpoint_path = os.path.join(
                    self.checkpoint_dir, f"{checkpoint_id}.json"
                )
                async with aiofiles.open(checkpoint_path, "w") as f:
                    await f.write(json.dumps(checkpoint, indent=2))

                logger.info(
                    f"Saved checkpoint {checkpoint_id} for job {job_id} at stage {stage}"
                )
                return checkpoint_id

            except Exception as e:
                logger.error(f"Error saving checkpoint: {str(e)}")
                # Continue processing even if checkpoint fails
                return None

    async def load_checkpoint(
        self, job_id: str, file_path: str, stage: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load a processing checkpoint if available.

        Args:
            job_id: ID of the current job
            file_path: Path to the source file being processed
            stage: Current processing stage

        Returns:
            Checkpoint data or None if no valid checkpoint exists
        """
        async with self._lock:
            try:
                # Generate checkpoint ID
                checkpoint_id = f"{job_id}_{stage}"
                checkpoint_path = os.path.join(
                    self.checkpoint_dir, f"{checkpoint_id}.json"
                )

                # Check if checkpoint exists
                if not os.path.exists(checkpoint_path):
                    return None

                # Read checkpoint
                async with aiofiles.open(checkpoint_path, "r") as f:
                    checkpoint = json.loads(await f.read())

                # Verify file integrity using hash
                current_hash = await self._calculate_file_hash(file_path)
                if checkpoint.get("file_hash") != current_hash:
                    logger.warning(
                        f"File hash mismatch for checkpoint {checkpoint_id}, ignoring checkpoint"
                    )
                    return None

                logger.info(
                    f"Loaded checkpoint {checkpoint_id} for job {job_id} at stage {stage}"
                )
                return checkpoint.get("data")

            except Exception as e:
                logger.error(f"Error loading checkpoint: {str(e)}")
                return None

    async def _calculate_file_hash(self, file_path: str) -> str:
        """
        Calculate a hash of the file for integrity verification.

        Args:
            file_path: Path to the file

        Returns:
            MD5 hash of the file
        """
        try:
            # For large files, hash only the first 1MB and file size
            file_size = os.path.getsize(file_path)

            async with aiofiles.open(file_path, "rb") as f:
                # Read the first 1MB
                data = await f.read(1024 * 1024)

            # Create hash from size and first chunk
            hasher = hashlib.md5()
            hasher.update(str(file_size).encode())
            hasher.update(data)

            return hasher.hexdigest()

        except Exception as e:
            logger.error(f"Error calculating file hash: {str(e)}")
            # Return a timestamp-based hash as fallback
            return hashlib.md5(str(datetime.now().timestamp()).encode()).hexdigest()

    async def clean_old_checkpoints(self, max_age_hours: int = 24) -> int:
        """
        Clean up old checkpoints.

        Args:
            max_age_hours: Maximum age of checkpoints to keep (in hours)

        Returns:
            Number of checkpoints deleted
        """
        async with self._lock:
            try:
                now = datetime.now()
                count = 0

                for filename in os.listdir(self.checkpoint_dir):
                    if not filename.endswith(".json"):
                        continue

                    file_path = os.path.join(self.checkpoint_dir, filename)

                    try:
                        # Read checkpoint
                        async with aiofiles.open(file_path, "r") as f:
                            checkpoint = json.loads(await f.read())

                        # Parse timestamp
                        timestamp = datetime.fromisoformat(
                            checkpoint.get("timestamp", "2000-01-01T00:00:00")
                        )

                        # Check age
                        age_hours = (now - timestamp).total_seconds() / 3600
                        if age_hours > max_age_hours:
                            os.remove(file_path)
                            count += 1

                    except Exception as e:
                        # If any error occurs, consider the file corrupted and remove it
                        os.remove(file_path)
                        count += 1

                logger.info(f"Cleaned up {count} old checkpoints")
                return count

            except Exception as e:
                logger.error(f"Error cleaning old checkpoints: {str(e)}")
                return 0

    async def delete_checkpoints(self, job_id: str) -> int:
        """
        Delete all checkpoints for a specific job.

        Args:
            job_id: ID of the job

        Returns:
            Number of checkpoints deleted
        """
        async with self._lock:
            try:
                count = 0
                prefix = f"{job_id}_"

                for filename in os.listdir(self.checkpoint_dir):
                    if filename.startswith(prefix) and filename.endswith(".json"):
                        os.remove(os.path.join(self.checkpoint_dir, filename))
                        count += 1

                logger.info(f"Deleted {count} checkpoints for job {job_id}")
                return count

            except Exception as e:
                logger.error(f"Error deleting checkpoints: {str(e)}")
                return 0
