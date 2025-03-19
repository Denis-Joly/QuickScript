import { useState, FormEvent } from 'react';
import './UrlInput.css';

interface UrlInputProps {
  onSubmit: (url: string) => void;
  disabled: boolean;
}

function UrlInput({ onSubmit, disabled }: UrlInputProps) {
  const [url, setUrl] = useState('');
  const [error, setError] = useState('');

  // Validate URL
  const validateUrl = (url: string): boolean => {
    try {
      new URL(url);
      return true;
    } catch (error) {
      return false;
    }
  };

  // Handle form submission
  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    if (disabled) return;

    // Validate URL
    if (!url.trim()) {
      setError('URL cannot be empty');
      return;
    }

    if (!validateUrl(url)) {
      setError('Please enter a valid URL');
      return;
    }

    // Clear error and submit URL
    setError('');
    onSubmit(url);
  };

  return (
    <div className="url-input-container">
      <form onSubmit={handleSubmit}>
        <div className="input-group">
          <label htmlFor="url">Video or Audio URL</label>
          <input
            type="text"
            id="url"
            placeholder="https://www.youtube.com/watch?v=..."
            value={url}
            onChange={(e) => {
              setUrl(e.target.value);
              if (error) setError('');
            }}
            disabled={disabled}
          />
          {error && <div className="error-message">{error}</div>}
        </div>

        <div className="supported-sites">
          <p>Supported sites: YouTube, Vimeo, SoundCloud, and many more</p>
        </div>

        <button
          type="submit"
          className="submit-button"
          disabled={disabled || !url.trim()}
        >
          Process URL
        </button>
      </form>
    </div>
  );
}

export default UrlInput;