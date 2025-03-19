import './ProcessingStatus.css';

interface JobStatus {
  job_id: string;
  status: 'queued' | 'processing' | 'complete' | 'error';
  progress: number;
  message?: string;
}

interface ProcessingStatusProps {
  status: JobStatus | null;
  onCancel: () => void;
}

function ProcessingStatus({ status, onCancel }: ProcessingStatusProps) {
  if (!status) return null;

  const { progress, message, status: jobStatus } = status;

  // Format progress as percentage
  const progressPercent = Math.round(progress * 100);

  // Determine status class
  const statusClass = jobStatus === 'error' ? 'error' : '';

  return (
    <div className="processing-status-container">
      <div className="processing-status">
        <div className="status-header">
          <h3>Processing Status</h3>
          <button
            className="cancel-button"
            onClick={onCancel}
            disabled={jobStatus === 'complete'}
          >
            Cancel
          </button>
        </div>

        <div className="status-content">
          <div className="status-message">
            <span className={statusClass}>{message}</span>
          </div>

          <div className="progress-container">
            <div
              className="progress-bar"
              style={{ width: `${progressPercent}%` }}
            ></div>
          </div>

          <div className="progress-value">{progressPercent}%</div>
        </div>
      </div>
    </div>
  );
}

export default ProcessingStatus;