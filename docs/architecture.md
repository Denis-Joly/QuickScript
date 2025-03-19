# QuickScript Architecture

## Overview

QuickScript follows a modular architecture with clear separation between frontend and backend components.

## Frontend

- **Framework**: Tauri with React
- **UI Components**: Modular React components for file upload, URL input, processing status, and markdown preview
- **State Management**: React hooks for local state management

## Backend

- **API Framework**: FastAPI
- **Core Services**:
  - Media Service: Handles media file operations including downloading and audio extraction
  - Transcription Service: Converts audio to text using Whisper.cpp
  - Summarization Service: Generates structured markdown from transcriptions
  - Export Service: Handles exporting to different formats

## Communication

- REST API between frontend and backend
- Background processing with status updates

## File Structure

See the project structure document for details on the file organization.

