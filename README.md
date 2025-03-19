# QuickScript

QuickScript is a macOS desktop application that efficiently converts audio and video content (local files or online URLs) into structured and readable Markdown text. It leverages state-of-the-art open-source technologies for transcription and text summarization to provide high-quality results.

![QuickScript Screenshot](docs/screenshots/quickscript_main.png)

## Features

- **Multiple Input Sources**:
  - Local audio files (.mp3, .wav, etc.)
  - Local video files (.mp4, .mov, .avi, etc.)
  - YouTube and other online video/podcast URLs

- **High-Quality Processing**:
  - Fast and accurate audio extraction
  - Advanced speech-to-text conversion (>95% accuracy)
  - Intelligent structured text generation with headers, bullet points, and timestamps

- **Flexible Output Options**:
  - Export as Markdown (.md)
  - Export as plain text (.txt)
  - Export as PDF (.pdf)

- **User-Friendly Interface**:
  - Drag-and-drop file uploads
  - Real-time progress tracking
  - Live preview of generated content

## System Requirements

- macOS 10.15 (Catalina) or later
- 4GB RAM minimum (8GB recommended)
- 500MB free disk space
- Internet connection (for online URL processing)

## Installation

### From Release

1. Download the latest release from the [Releases](https://github.com/yourorganization/quickscript/releases) page
2. Drag QuickScript.app to your Applications folder
3. Open the app (right-click and select "Open" if you encounter security warnings)

### From Source

#### Prerequisites

- Rust (latest stable)
- Node.js (v16+)
- Python (3.9+)
- FFmpeg (`brew install ffmpeg` on macOS)
- wkhtmltopdf (for PDF export: `brew install wkhtmltopdf` on macOS)

#### Backend Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/yourorganization/quickscript.git
   cd quickscript
   ```

2. Set up the Python backend:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   
   # Install core dependencies
   pip install fastapi uvicorn pydantic python-multipart aiofiles
   pip install ffmpeg-python yt-dlp
   pip install torch transformers
   pip install markdown pdfkit
   pip install pytest httpx
   
   # Install Whisper (speech-to-text)
   pip install git+https://github.com/openai/whisper.git
   ```

3. Start the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```

#### Frontend Setup

1. Navigate to the frontend directory:
   ```bash
   cd ../frontend
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

3. Start the development server:
   ```bash
   npm run tauri dev
   ```

## Building for Production

```bash
cd frontend
npm run tauri build
```

The built application will be available in `frontend/src-tauri/target/release/bundle/`.

## Usage

1. Launch QuickScript
2. Choose an input method:
   - Upload a local audio/video file using drag-and-drop or the browse button
   - Enter a YouTube or other supported online media URL
3. Wait for the processing to complete (progress will be displayed)
4. Review the generated structured markdown in the Preview tab
5. Export the result in your preferred format (Markdown, Text, or PDF)

## Architecture

QuickScript follows a modular architecture with clear separation between frontend and backend:

- **Frontend**: Built with Tauri and React for a native-like experience and responsive UI
- **Backend**: Python with FastAPI for efficient processing and REST API communication
- **Processing Pipeline**:
  1. Audio extraction using FFmpeg
  2. Speech-to-text conversion using Whisper.cpp
  3. Structured text generation using Seamless M4T model

## Technology Stack

- **Frontend**:
  - Tauri (Rust-based framework)
  - React (UI library)
  - TypeScript (type-safe JavaScript)

- **Backend**:
  - Python
  - FastAPI (API framework)
  - FFmpeg (media processing)
  - Whisper.cpp (speech-to-text)
  - HuggingFace Transformers (text processing)

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgements

- [OpenAI Whisper](https://github.com/openai/whisper) - For the speech recognition model
- [Whisper.cpp](https://github.com/ggerganov/whisper.cpp) - For the optimized C++ implementation
- [Facebook Seamless M4T](https://github.com/facebookresearch/seamless_communication) - For the text structuring model
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - For video URL processing
- [FFmpeg](https://ffmpeg.org/) - For audio/video processing
- [Tauri](https://tauri.app/) - For the desktop application framework
