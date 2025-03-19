import { useEffect, useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './MarkdownPreview.css';

interface MarkdownPreviewProps {
  content: string;
}

function MarkdownPreview({ content }: MarkdownPreviewProps) {
  const [viewMode, setViewMode] = useState<'preview' | 'source'>('preview');

  if (!content) {
    return (
      <div className="markdown-preview-container empty">
        <p>No content to preview</p>
      </div>
    );
  }

  return (
    <div className="markdown-preview-container">
      <div className="preview-header">
        <div className="view-mode-toggle">
          <button
            className={viewMode === 'preview' ? 'active' : ''}
            onClick={() => setViewMode('preview')}
          >
            Preview
          </button>
          <button
            className={viewMode === 'source' ? 'active' : ''}
            onClick={() => setViewMode('source')}
          >
            Source
          </button>
        </div>
      </div>

      <div className="preview-content">
        {viewMode === 'preview' ? (
          <div className="rendered-markdown">
            <ReactMarkdown>{content}</ReactMarkdown>
          </div>
        ) : (
          <div className="markdown-source">
            <pre>{content}</pre>
          </div>
        )}
      </div>
    </div>
  );
}

export default MarkdownPreview;