import React from 'react';
import { Layers } from 'lucide-react';

interface ToolbarProps {
  extractionSummary: string;
  density: 'comfortable' | 'compact';
  onToggleDensity: () => void;
  onDownloadCsv: () => void;
  onDownloadJson: () => void;
  onReset: () => void;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  extractionSummary,
  density,
  onToggleDensity,
  onDownloadCsv,
  onDownloadJson,
  onReset,
}) => {
  return (
    <div className="result-toolbar">
      <div>
        <p className="eyebrow">Search complete</p>
        <h2 id="resultTitle">Results are ready</h2>
        <p id="extractionSummary" className="muted">
          {extractionSummary}
        </p>
      </div>
      <div className="toolbar-actions">
        {/* Density Toggle */}
        <button
          id="densityToggleBtn"
          className="density-toggle"
          type="button"
          title={`Current: ${density}. Click to switch.`}
          onClick={onToggleDensity}
        >
          <Layers className="w-3.5 h-3.5" />
          <span>{density === 'compact' ? 'Compact' : 'Comfortable'}</span>
        </button>

        <button
          id="downloadBtn"
          className="secondary-button"
          type="button"
          onClick={onDownloadCsv}
        >
          Download CSV
        </button>
        <button
          id="downloadJsonBtn"
          className="secondary-button secondary-button-muted"
          type="button"
          onClick={onDownloadJson}
        >
          Download JSON
        </button>
        <button
          id="resetBtn"
          className="text-button"
          type="button"
          onClick={onReset}
        >
          New search
        </button>
      </div>
    </div>
  );
};
