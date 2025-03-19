import './ExportOptions.css';

interface ExportOptionsProps {
  onExport: (format: 'md' | 'txt' | 'pdf') => void;
  disabled: boolean;
}

function ExportOptions({ onExport, disabled }: ExportOptionsProps) {
  return (
    <div className="export-options-container">
      <h3>Export Options</h3>
      <div className="export-buttons">
        <button
          className="export-button markdown"
          onClick={() => onExport('md')}
          disabled={disabled}
        >
          Export as Markdown
        </button>
        <button
          className="export-button text"
          onClick={() => onExport('txt')}
          disabled={disabled}
        >
          Export as Text
        </button>
        <button
          className="export-button pdf"
          onClick={() => onExport('pdf')}
          disabled={disabled}
        >
          Export as PDF
        </button>
      </div>
    </div>
  );
}

export default ExportOptions;
