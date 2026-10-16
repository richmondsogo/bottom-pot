import React from 'react';

interface ToolbarProps {
  totalRawCount: number;
  filteredCount: number;
  currentPage: number;
  totalPages: number;
  density: 'comfortable' | 'compact';
  onSetDensity: (density: 'comfortable' | 'compact') => void;
  onResetColumns: () => void;
  onDownloadCsv: () => void;
  onDownloadJson: () => void;
}

export const Toolbar: React.FC<ToolbarProps> = ({
  totalRawCount,
  filteredCount,
  currentPage,
  totalPages,
  density,
  onSetDensity,
  onResetColumns,
  onDownloadCsv,
  onDownloadJson,
}) => {
  const countText =
    totalRawCount === filteredCount
      ? `${totalRawCount} result${totalRawCount === 1 ? '' : 's'}`
      : `Showing ${filteredCount} of ${totalRawCount} results`;

  const pageText = totalPages > 1 ? ` · Page ${currentPage} of ${totalPages}` : '';

  return (
    <div className="table-toolbar">
      <div className="toolbar-left">
        <p id="filterSummary" aria-live="polite" className="result-count-label">
          {countText}{pageText}
        </p>
      </div>
      <div className="toolbar-right">
        {/* Segmented density control */}
        <div
          id="densityToggleBtn"
          className="segmented-control"
          role="group"
          aria-label="Table density"
        >
          <button
            type="button"
            id="densityComfortableBtn"
            className={`seg-btn ${density === 'comfortable' ? 'active' : ''}`}
            aria-pressed={density === 'comfortable'}
            onClick={() => onSetDensity('comfortable')}
          >
            Comfortable
          </button>
          <button
            type="button"
            id="densityCompactBtn"
            className={`seg-btn ${density === 'compact' ? 'active' : ''}`}
            aria-pressed={density === 'compact'}
            onClick={() => onSetDensity('compact')}
          >
            Compact
          </button>
        </div>

        <button
          id="resetColsBtn"
          className="btn btn-text"
          type="button"
          onClick={onResetColumns}
          title="Reset column widths to default"
        >
          Reset columns
        </button>

        <button
          id="downloadBtn"
          className="btn btn-secondary"
          type="button"
          onClick={onDownloadCsv}
        >
          Download CSV
        </button>

        <button
          id="downloadJsonBtn"
          className="btn btn-secondary"
          type="button"
          onClick={onDownloadJson}
        >
          Download JSON
        </button>
      </div>
    </div>
  );
};
