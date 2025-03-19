# Development Guide

## Setup

### Backend

1. Create a virtual environment:
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Download models:
   ```bash
   mkdir -p models
   # Download example model (replace with actual download command)
   curl -L https://example.com/model.bin -o models/model.bin
   ```

4. Start the backend server:
   ```bash
   uvicorn app.main:app --reload
   ```

### Frontend

1. Install dependencies:
   ```bash
   cd frontend
   npm install
   ```

2. Start the development server:
   ```bash
   npm run tauri dev
   ```

## Project Structure

See the project structure documentation for details.

## Testing

Run backend tests:
```bash
cd backend
pytest
```

