import { useState } from 'react';
import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import { open } from '@tauri-apps/api/dialog';
import { appWindow } from '@tauri-apps/api/window';
import './App.css';

// Components
import FileUpload from './components/FileUpload';
import UrlInput from './components/UrlInput';
import ProcessingStatus from './components/ProcessingStatus';
import MarkdownPreview from './components/MarkdownPreview';
import ExportOptions from './components/ExportOptions';

// Types
type JobStatus = {
  job_id: string;
  status: 'queued' | 'processing' | 'complete' | 'error';
  progress: number;
  message?: string;
  result_url?: string;
};

function App() {
  // State
  const [currentJobId, setCurrentJobId] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatus | null>(null);
  const [markdownContent, setMarkdownContent] = useState<string>('');
  const [activeTab, setActiveTab] = useState<'upload' | 'url' | 'preview'>('upload');
  const [isProcessing, setIsProcessing] = useState<boolean>(false);

  // Handle file upload
  const handleFileUpload = async (filePath: string) => {
    try {
      setIsProcessing(true);

      console.log("Uploading file path:", filePath); // Debug log

      // Call Tauri command to upload file
      const jobId = await invoke<string>('upload_file', { path: filePath });

      console.log("Got job ID:", jobId); // Debug log

      // Set current job ID
      setCurrentJobId(jobId);

      // Initialize job status
      setJobStatus({
        job_id: jobId,
        status: 'queued',
        progress: 0,
        message: 'Job queued'
      });

      // Start polling for job status
      pollJobStatus(jobId);

    } catch (error) {
      console.error('Error uploading file:', error);
      setIsProcessing(false);
      alert(`Error uploading file: ${error}`);
    }
  };

  // Handle URL submission
  const handleUrlSubmit = async (url: string) => {
    try {
      setIsProcessing(true);

      // Call Tauri command to process URL
      const jobId = await invoke<string>('process_url', { url });

      // Set current job ID
      setCurrentJobId(jobId);

      // Initialize job status
      setJobStatus({
        job_id: jobId,
        status: 'queued',
        progress: 0,
        message: 'Job queued'
      });

      // Start polling for job status
      pollJobStatus(jobId);

    } catch (error) {
      console.error('Error processing URL:', error);
      setIsProcessing(false);
      alert(`Error processing URL: ${error}`);
    }
  };

  // Poll job status
  const pollJobStatus = async (jobId: string) => {
    try {
      // Poll every second
      const intervalId = setInterval(async () => {
        const status = await invoke<JobStatus>('get_job_status', { jobId });
        setJobStatus(status);

        // If job is complete or error, stop polling
        if (status.status === 'complete' || status.status === 'error') {
          clearInterval(intervalId);
          setIsProcessing(false);

          // If job is complete, fetch markdown content
          if (status.status === 'complete' && status.result_url) {
            fetchMarkdownContent(status.result_url);
            setActiveTab('preview');
          }
        }
      }, 1000);

      // Clean up interval on component unmount
      return () => clearInterval(intervalId);

    } catch (error) {
      console.error('Error polling job status:', error);
      setIsProcessing(false);
      alert(`Error polling job status: ${error}`);
    }
  };

  // Fetch markdown content
  const fetchMarkdownContent = async (resultUrl: string) => {
    try {
      // Extract job ID from result URL
      const jobId = resultUrl.split('/').pop();

      // Open save dialog
      const savePath = await open({
        directory: false,
        multiple: false,
        defaultPath: `QuickScript_Output.md`,
        filters: [{ name: 'Markdown', extensions: ['md'] }]
      });

      if (!savePath) return; // User cancelled

      // Download result
      await invoke<string>('download_result', {
        jobId,
        format: 'md',
        savePath
      });

      // Read file content
      const content = await invoke<string>('read_file', { path: savePath });
      setMarkdownContent(content);

    } catch (error) {
      console.error('Error fetching markdown content:', error);
      alert(`Error fetching markdown content: ${error}`);
    }
  };

  // Handle export
  const handleExport = async (format: 'md' | 'txt' | 'pdf') => {
    try {
      if (!currentJobId) return;

      // Open save dialog
      const savePath = await open({
        directory: false,
        multiple: false,
        defaultPath: `QuickScript_Output.${format}`,
        filters: [{
          name: format.toUpperCase(),
          extensions: [format]
        }]
      });

      if (!savePath) return; // User cancelled

      // Download result
      await invoke<string>('download_result', {
        jobId: currentJobId,
        format,
        savePath
      });

      alert(`Exported to ${savePath}`);

    } catch (error) {
      console.error(`Error exporting as ${format}:`, error);
      alert(`Error exporting as ${format}: ${error}`);
    }
  };

  // Cancel job
  const handleCancel = async () => {
    try {
      if (!currentJobId) return;

      // Call Tauri command to cancel job
      await invoke<boolean>('cancel_job', { jobId: currentJobId });

      // Reset state
      setCurrentJobId(null);
      setJobStatus(null);
      setIsProcessing(false);

    } catch (error) {
      console.error('Error cancelling job:', error);
      alert(`Error cancelling job: ${error}`);
    }
  };

  return (
    <div className="container">
      <header>
        <h1>QuickScript</h1>
        <p className="subtitle">Convert audio/video to structured markdown</p>
      </header>

      <main>
        <div className="tabs">
          <button
            className={`tab ${activeTab === 'upload' ? 'active' : ''}`}
            onClick={() => setActiveTab('upload')}
            disabled={isProcessing}
          >
            Upload File
          </button>
          <button
            className={`tab ${activeTab === 'url' ? 'active' : ''}`}
            onClick={() => setActiveTab('url')}
            disabled={isProcessing}
          >
            Process URL
          </button>
          <button
            className={`tab ${activeTab === 'preview' ? 'active' : ''}`}
            onClick={() => setActiveTab('preview')}
            disabled={!markdownContent}
          >
            Preview
          </button>
        </div>

        <div className="content">
          {activeTab === 'upload' && (
            <FileUpload onUpload={handleFileUpload} disabled={isProcessing} />
          )}

          {activeTab === 'url' && (
            <UrlInput onSubmit={handleUrlSubmit} disabled={isProcessing} />
          )}

          {activeTab === 'preview' && (
            <div className="preview-container">
              <MarkdownPreview content={markdownContent} />
              <ExportOptions
                onExport={handleExport}
                disabled={!currentJobId || isProcessing}
              />
            </div>
          )}

          {isProcessing && (
            <ProcessingStatus
              status={jobStatus}
              onCancel={handleCancel}
            />
          )}
        </div>
      </main>

      <footer>
        <p>QuickScript v1.0.0</p>
      </footer>
    </div>
  );
}

export default App;