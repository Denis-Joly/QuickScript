// File: frontend/src/components/FileUpload.tsx
import { useState, useRef, DragEvent, ChangeEvent } from 'react';
import { open } from '@tauri-apps/api/dialog';
import './FileUpload.css';

interface FileUploadProps {
  onUpload: (filePath: string) => void;
  disabled: boolean;
}

function FileUpload({ onUpload, disabled }: FileUploadProps) {
  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Handle drag events
  const handleDragEnter = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    setIsDragging(true);
  };

  const handleDragLeave = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    setIsDragging(true);
  };

  const handleDrop = async (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    e.stopPropagation();
    if (disabled) return;
    setIsDragging(false);

    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      // We need to get the actual file path
      // In Tauri, the dataTransfer doesn't include the path property as expected
      // Use the browse dialog API instead
      handleBrowseClick();
    }
  };

  // Handle file selection via input
  const handleFileChange = async (e: ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;

    // Use the browse dialog API instead since file input doesn't provide paths in Tauri
    handleBrowseClick();
  };

  // Handle browse button click
  const handleBrowseClick = async () => {
    if (disabled) return;
    try {
      const selected = await open({
        multiple: false,
        filters: [
          {
            name: 'Media',
            extensions: ['mp3', 'wav', 'mp4', 'mov', 'avi', 'mkv']
          }
        ]
      });

      if (selected && !Array.isArray(selected)) {
        // Send the full path to the parent component
        onUpload(selected);
      } else if (selected && Array.isArray(selected) && selected.length > 0) {
        // If multiple is somehow true, use the first file
        onUpload(selected[0]);
      }
    } catch (error) {
      console.error('Error selecting file:', error);
    }
  };

  // Trigger file input click
  const triggerFileInput = () => {
    if (disabled) return;
    // Instead of using the file input, use the Tauri dialog directly
    handleBrowseClick();
  };

  return (
    <div className="file-upload-container">
      <div
        className={`drop-area ${isDragging ? 'dragging' : ''} ${disabled ? 'disabled' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
        onClick={triggerFileInput}
      >
        <div className="drop-content">
          <svg
            xmlns="http://www.w3.org/2000/svg"
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
            <polyline points="14 2 14 8 20 8"></polyline>
            <line x1="12" y1="18" x2="12" y2="12"></line>
            <line x1="9" y1="15" x2="15" y2="15"></line>
          </svg>
          <p className="drop-text">
            Drag and drop your audio or video file here<br />
            or click to browse
          </p>
          <p className="file-types">
            Supported formats: MP3, WAV, MP4, MOV, AVI, MKV
          </p>
        </div>
      </div>

      <div className="upload-actions">
        <button
          className="upload-button"
          onClick={handleBrowseClick}
          disabled={disabled}
        >
          Browse Files
        </button>
      </div>
    </div>
  );
}

export default FileUpload;