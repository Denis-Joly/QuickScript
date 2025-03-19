import os
import tempfile
import logging
import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
from typing import Dict, List, Optional

from app.core.errors import ApplicationError
from app.core.config import settings

logger = logging.getLogger(__name__)

class SummarizationService:
    """Service for generating structured Markdown summaries from transcriptions."""
    
    def __init__(self):
        # Initialize summarization model
        self.model = None
        self.tokenizer = None
        self.model_name = "facebook/seamless-m4t-v2-large"  # Using Seamless M4T model
    
    async def _load_model(self):
        """Load the summarization model if not already loaded."""
        if self.model is None or self.tokenizer is None:
            try:
                logger.info(f"Loading summarization model: {self.model_name}")
                
                # Load tokenizer and model
                self.tokenizer = AutoTokenizer.from_pretrained(self.model_name)
                self.model = AutoModelForSeq2SeqLM.from_pretrained(self.model_name)
                
                # Move model to GPU if available
                if torch.cuda.is_available():
                    self.model = self.model.to("cuda")
                    logger.info("Model loaded on GPU")
                else:
                    logger.info("Model loaded on CPU")
                
            except Exception as e:
                logger.error(f"Failed to load summarization model: {str(e)}")
                raise ApplicationError(f"Failed to load summarization model: {str(e)}")
    
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
            
            # Load model if needed
            await self._load_model()
            
            # Extract full text
            full_text = transcription["text"]
            
            # Process in chunks if text is too long
            chunk_size = 1024  # Max token length for model
            markdown_chunks = []
            
            # Get segments with timestamps
            segments = transcription["segments"]
            current_position = 0
            
            while current_position < len(full_text):
                # Get chunk of text and corresponding segments
                end_position = min(current_position + chunk_size, len(full_text))
                chunk_text = full_text[current_position:end_position]
                
                # Find segments that correspond to this chunk
                chunk_segments = []
                for segment in segments:
                    if segment["start"] >= current_position and segment["start"] < end_position:
                        chunk_segments.append(segment)
                
                # Create prompt for structured text generation
                prompt = f"""
                Generate structured markdown from this transcript:
                
                {chunk_text}
                
                Format as markdown with:
                - Main title
                - Section headers
                - Bullet points for key points
                - Include timestamps [MM:SS] for important sections
                - Summarize key ideas
                """
                
                # Tokenize input
                inputs = self.tokenizer(prompt, return_tensors="pt", truncation=True, max_length=chunk_size)
                if torch.cuda.is_available():
                    inputs = {k: v.to("cuda") for k, v in inputs.items()}
                
                # Generate structured text
                outputs = self.model.generate(
                    **inputs,
                    max_length=1024,
                    num_beams=4,
                    length_penalty=1.0,
                    early_stopping=True
                )
                
                # Decode output
                markdown_text = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
                markdown_chunks.append(markdown_text)
                
                # Move to next chunk
                current_position = end_position
            
            # Combine chunks into final markdown
            final_markdown = "\n\n".join(markdown_chunks)
            
            logger.info(f"Structured text generation complete: {len(final_markdown)} characters")
            return final_markdown
            
        except Exception as e:
            logger.error(f"Summarization error: {str(e)}")
            raise ApplicationError(f"Failed to generate structured text: {str(e)}")


# File: backend/app/services/export_service.py
import os
import tempfile
import logging
import asyncio
import aiofiles
from typing import Optional
import markdown
import pdfkit

from app.core.errors import ApplicationError

logger = logging.getLogger(__name__)

class ExportService:
    """Service for exporting Markdown to different formats."""
    
    async def export(self, markdown_path: str, format: str = "md") -> str:
        """
        Export Markdown to the specified format.
        
        Args:
            markdown_path: Path to the Markdown file
            format: Output format (md, txt, pdf)
            
        Returns:
            Path to the exported file
            
        Raises:
            ApplicationError: If export fails
        """
        try:
            logger.info(f"Exporting markdown to {format} format")
            
            # Read markdown content
            async with aiofiles.open(markdown_path, 'r') as f:
                markdown_content = await f.read()
            
            # Create output file path
            base_path = os.path.splitext(markdown_path)[0]
            output_path = f"{base_path}.{format}"
            
            if format.lower() == "md":
                # Just copy the file if format is already markdown
                async with aiofiles.open(output_path, 'w') as f:
                    await f.write(markdown_content)
                    
            elif format.lower() == "txt":
                # Convert to plain text (strip markdown)
                async with aiofiles.open(output_path, 'w') as f:
                    # Simple markdown stripping (for more complex needs, use a proper library)
                    plain_text = markdown_content
                    # Remove headers
                    plain_text = re.sub(r'#+\s+', '', plain_text)
                    # Remove bold/italic
                    plain_text = re.sub(r'\*\*(.*?)\*\*', r'\1', plain_text)
                    plain_text = re.sub(r'\*(.*?)\*', r'\1', plain_text)
                    # Remove links
                    plain_text = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', plain_text)
                    await f.write(plain_text)
                    
            elif format.lower() == "pdf":
                # Convert to PDF using markdown->HTML->PDF
                html_content = markdown.markdown(markdown_content)
                
                # Create temporary HTML file
                temp_html = f"{base_path}.html"
                async with aiofiles.open(temp_html, 'w') as f:
                    await f.write(f"""
                    <!DOCTYPE html>
                    <html>
                    <head>
                        <meta charset="UTF-8">
                        <style>
                            body {{ font-family: Arial, sans-serif; margin: 40px; }}
                            h1 {{ color: #333; }}
                            h2 {{ color: #444; }}
                            code {{ background-color: #f4f4f4; padding: 2px 5px; }}
                            pre {{ background-color: #f4f4f4; padding: 10px; }}
                        </style>
                    </head>
                    <body>
                        {html_content}
                    </body>
                    </html>
                    """)
                
                # Convert HTML to PDF
                try:
                    pdfkit.from_file(temp_html, output_path)
                    # Delete temporary HTML file
                    os.remove(temp_html)
                except Exception as e:
                    logger.error(f"PDF conversion error: {str(e)}")
                    raise ApplicationError(f"Failed to generate PDF: {str(e)}")
            else:
                raise ApplicationError(f"Unsupported export format: {format}")
            
            logger.info(f"Exported to {output_path}")
            return output_path
            
        except Exception as e:
            logger.error(f"Export error: {str(e)}")
            raise ApplicationError(f"Failed to export to {format}: {str(e)}")
