# File: backend/app/services/summarization_service.py
import os
import tempfile
import logging
import torch
import hashlib
import asyncio
import aiofiles
from typing import Dict, List, Optional
import json

from app.core.errors import ApplicationError
from app.core.config import settings

logger = logging.getLogger(__name__)


class SummarizationService:
    """Service for generating structured Markdown summaries from transcriptions."""

    def __init__(self):
        # Initialize models
        self.llm = None
        self.model_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "models",
            "phi-2.gguf",  # We'll use Phi-2 as a compact but effective model
        )

        # Set up cache directory
        self.cache_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "cache",
            "summaries",
        )
        os.makedirs(self.cache_dir, exist_ok=True)

        # Determine device
        self.use_gpu = torch.cuda.is_available()
        logger.info(f"SummarizationService initialized with GPU={self.use_gpu}")

    async def _load_model(self):
        """Load the local LLM if not already loaded."""
        if self.llm is None:
            try:
                logger.info(f"Loading local LLM from: {self.model_path}")

                # Ensure model directory exists
                os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

                # Check if model exists, if not download it
                if not os.path.exists(self.model_path):
                    await self._download_model()

                # Import here to avoid loading at startup
                from llama_cpp import Llama

                # Set optimal parameters based on hardware
                n_gpu_layers = -1 if self.use_gpu else 0
                n_threads = 4 if not self.use_gpu else 1

                # Load the model with optimized settings
                self.llm = Llama(
                    model_path=self.model_path,
                    n_ctx=4096,  # Context size for processing
                    n_threads=n_threads,
                    n_gpu_layers=n_gpu_layers,
                )

                logger.info("Local LLM loaded successfully")

            except Exception as e:
                logger.error(f"Failed to load local LLM: {str(e)}")
                logger.info("Falling back to basic summarization without LLM")
                self.llm = None

    async def _download_model(self):
        """Download the Phi-2 model."""
        try:
            logger.info(f"Downloading Phi-2 model to {self.model_path}")

            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

            # Use huggingface-hub to download
            try:
                import huggingface_hub

                huggingface_hub.hf_hub_download(
                    repo_id="TheBloke/Phi-2-GGUF",
                    filename="phi-2.Q4_K_M.gguf",
                    local_dir=os.path.dirname(self.model_path),
                    local_dir_use_symlinks=False,
                )

                # Rename the file to match our expected path
                downloaded_path = os.path.join(
                    os.path.dirname(self.model_path), "phi-2.Q4_K_M.gguf"
                )
                if os.path.exists(downloaded_path):
                    os.rename(downloaded_path, self.model_path)

            except ImportError:
                # Fallback to direct download
                raise ApplicationError(
                    "Please install huggingface_hub to download models"
                )

            logger.info("Model downloaded successfully")

        except Exception as e:
            logger.error(f"Failed to download model: {str(e)}")
            raise ApplicationError(f"Failed to download model: {str(e)}")

    async def summarize(self, transcription: dict) -> str:
        """
        Generate structured Markdown text from transcription.

        Args:
            transcription: Transcription dictionary with text and segments

        Returns:
            Structured Markdown text

        Raises:
            ApplicationError: If summarization fails
        """
        try:
            logger.info("Generating structured text from transcription")

            # Extract full text
            full_text = transcription["text"]

            # Calculate cache key based on content hash
            cache_key = hashlib.md5(full_text.encode()).hexdigest()
            cache_file = os.path.join(self.cache_dir, f"{cache_key}.md")

            # Check if we have a cached result
            if os.path.exists(cache_file):
                async with aiofiles.open(cache_file, "r") as f:
                    markdown = await f.read()
                    logger.info(f"Using cached summary for {cache_key}")
                    return markdown

            # Process based on text length
            if len(full_text) > 10000:
                # Long text - process in chunks
                markdown = await self._process_long_text(transcription)
            else:
                # Normal text - process directly
                markdown = await self._generate_markdown(transcription)

            # Cache the result
            async with aiofiles.open(cache_file, "w") as f:
                await f.write(markdown)

            logger.info(
                f"Structured text generation complete: {len(markdown)} characters"
            )
            return markdown

        except Exception as e:
            logger.error(f"Summarization error: {str(e)}")
            raise ApplicationError(f"Failed to generate structured text: {str(e)}")

    async def _generate_markdown(self, transcription: dict) -> str:
        """Generate markdown using local LLM or basic structure."""
        # Load model if needed and available
        await self._load_model()

        # Extract text and segments
        full_text = transcription["text"]
        segments = transcription["segments"]

        if self.llm:
            # Use local LLM for generation
            return await asyncio.to_thread(self._generate_with_llm, full_text, segments)
        else:
            # Fallback to basic structure
            return self._generate_basic_structure(full_text, segments)

    def _generate_with_llm(self, text: str, segments: List[Dict]) -> str:
        """Generate structured markdown using local LLM."""
        # Limit text length to fit context window
        max_text_length = 3000
        if len(text) > max_text_length:
            text = text[:max_text_length] + "..."

        # Create a prompt for the LLM
        prompt = f"""Below is a transcript. Convert it to a well-structured Markdown document.

Follow these guidelines:
- Create a descriptive title based on the content
- Add clear section headers for major topics or themes
- Use bullet points for key information and important points
- Include timestamps where appropriate
- Summarize key ideas concisely

Transcript:
{text}

Create a well-structured Markdown document:

"""

        # Generate markdown with the LLM
        try:
            response = self.llm(
                prompt,
                max_tokens=2048,
                temperature=0.1,
                top_p=0.9,
                repeat_penalty=1.1,
                stop=["<END>"],
            )

            generated_text = response["choices"][0]["text"].strip()

            # Add timestamps from segments
            enhanced_markdown = self._enrich_with_timestamps(generated_text, segments)

            return enhanced_markdown

        except Exception as e:
            logger.error(f"LLM generation error: {str(e)}")
            # Fallback to basic structure
            return self._generate_basic_structure(text, segments)

    def _generate_basic_structure(self, text: str, segments: List[Dict]) -> str:
        """Generate basic structured text without LLM."""
        # Create a title from the beginning of the text
        first_words = text.split()[:10]
        title = " ".join(first_words) + "..."

        # Start building markdown
        markdown = f"# {title}\n\n"

        # Add a summary section
        markdown += "## Summary\n\n"
        markdown += f"{text[:300]}...\n\n"

        # Add content sections with timestamps
        current_section = ""
        current_section_time = 0

        for i, segment in enumerate(segments):
            # Format timestamp
            minutes = int(segment["start"] // 60)
            seconds = int(segment["start"] % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"

            # Create new section every ~2 minutes or at first segment
            if segment["start"] - current_section_time > 120 or i == 0:
                section_title = segment["text"][:50].strip()
                markdown += f"\n## {section_title} {timestamp}\n\n"
                current_section_time = segment["start"]
                current_section = ""

            # Add segment text with timestamp
            if i % 3 == 0:  # Add timestamp every few segments
                current_section += f"{segment['text']} {timestamp} "
            else:
                current_section += f"{segment['text']} "

            # Add paragraph after few segments
            if (i + 1) % 5 == 0:
                markdown += current_section.strip() + "\n\n"
                current_section = ""

        # Add any remaining text
        if current_section:
            markdown += current_section.strip() + "\n\n"

        # Add a concluding section if there's enough content
        if len(segments) > 10:
            markdown += "\n## Key Points\n\n"

            # Extract a few segments as key points
            key_indices = [
                len(segments) // 4,
                len(segments) // 2,
                len(segments) * 3 // 4,
            ]
            for idx in key_indices:
                if idx < len(segments):
                    markdown += f"- {segments[idx]['text']}\n"

        return markdown

    def _enrich_with_timestamps(self, markdown: str, segments: List[Dict]) -> str:
        """Add timestamps to generated markdown based on segments."""
        if not segments:
            return markdown

        lines = markdown.split("\n")
        enriched_lines = []

        for line in lines:
            # Check for section headers
            if line.startswith("## ") or line.startswith("# "):
                # Try to find best matching segment for this header
                header_text = line.lstrip("#").strip()

                best_match = None
                best_score = 0

                for segment in segments:
                    # Calculate simple word overlap
                    segment_words = set(segment["text"].lower().split())
                    header_words = set(header_text.lower().split())
                    overlap = len(segment_words.intersection(header_words))

                    if overlap > best_score:
                        best_score = overlap
                        best_match = segment

                # Add timestamp if we found a matching segment
                if best_match and best_score > 0:
                    minutes = int(best_match["start"] // 60)
                    seconds = int(best_match["start"] % 60)
                    timestamp = f"[{minutes:02d}:{seconds:02d}]"

                    if not any(
                        f"[{m:02d}:{s:02d}]" in line
                        for m in range(60)
                        for s in range(60)
                    ):
                        line = f"{line} {timestamp}"

            enriched_lines.append(line)

        return "\n".join(enriched_lines)

    async def _process_long_text(self, transcription: dict) -> str:
        """Process very long transcriptions by splitting into chunks."""
        # Extract text and segments
        full_text = transcription["text"]
        segments = transcription["segments"]

        # Calculate chunk size (aim for ~5000 characters per chunk)
        chunk_size = 5000

        # Prepare chunks
        text_chunks = []
        segment_chunks = []

        current_chunk = ""
        current_segments = []

        for segment in segments:
            # Add segment to current chunk
            current_chunk += segment["text"] + " "
            current_segments.append(segment)

            # If chunk is full, save it and start a new one
            if len(current_chunk) >= chunk_size:
                text_chunks.append(current_chunk)
                segment_chunks.append(current_segments)
                current_chunk = ""
                current_segments = []

        # Add the last chunk if there's any remaining
        if current_chunk:
            text_chunks.append(current_chunk)
            segment_chunks.append(current_segments)

        logger.info(f"Split long transcription into {len(text_chunks)} chunks")

        # Process each chunk in parallel with semaphore to limit concurrency
        results = []
        semaphore = asyncio.Semaphore(2)  # Process 2 chunks at a time

        async def process_chunk(chunk_idx):
            async with semaphore:
                # Create a mini-transcription for this chunk
                chunk_transcription = {
                    "text": text_chunks[chunk_idx],
                    "segments": segment_chunks[chunk_idx],
                    "language": transcription.get("language", "en"),
                }

                # Generate markdown for this chunk
                chunk_markdown = await self._generate_markdown(chunk_transcription)
                return chunk_idx, chunk_markdown

        # Create tasks for all chunks
        tasks = [asyncio.create_task(process_chunk(i)) for i in range(len(text_chunks))]
        chunk_results = await asyncio.gather(*tasks)

        # Sort results by chunk index
        chunk_results.sort(key=lambda x: x[0])

        # Combine results
        combined_markdown = ""

        for i, (_, chunk_markdown) in enumerate(chunk_results):
            # For the first chunk, keep everything
            if i == 0:
                combined_markdown += chunk_markdown
            else:
                # For subsequent chunks, skip the title
                lines = chunk_markdown.split("\n")
                if lines and lines[0].startswith("# "):
                    lines = lines[2:]  # Skip title and blank line
                combined_markdown += "\n" + "\n".join(lines)

        return combined_markdown
