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
