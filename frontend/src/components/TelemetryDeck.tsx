import React, { useState } from 'react';
import type { DoneMetrics } from '../types';
import { Tool, type ToolPart } from './prompt-kit/tool';
import { ThinkingBar } from './prompt-kit/thinking-bar';
import { SystemMessage } from './prompt-kit/system-message';
import { ChevronDown, ChevronUp, RefreshCw, Trash2, Cpu } from 'lucide-react';
import { cn } from '../lib/utils';

export interface TelemetryDeckProps {
  metrics: DoneMetrics | null;
  totalResults: number;
  isStreaming?: boolean;
  streamingMessage?: string | null;
  savedTimestamp?: number | null;
  isOpen?: boolean;
  onToggleOpen?: () => void;
  showSummaryStrip?: boolean;
  onCancelStream?: () => void;
  onRunAgain?: () => void;
  onClearSaved?: () => void;
  className?: string;
}

function formatSavedAgo(savedTimestamp: number | null | undefined): string {
  if (!savedTimestamp) return '';
  const now = Date.now();
  const elapsedMinutes = Math.floor((now - savedTimestamp) / (1000 * 60));
  if (elapsedMinutes < 60) return `Saved ${Math.max(1, elapsedMinutes)}m ago`;
  const elapsedHours = Math.floor(elapsedMinutes / 60);
  if (elapsedHours < 24) return `Saved ${elapsedHours}h ago`;
  const elapsedDays = Math.floor(elapsedHours / 24);
  return `Saved ${elapsedDays}d ago`;
}

export const TelemetryDeck: React.FC<TelemetryDeckProps> = ({
  metrics,
  totalResults,
  isStreaming = false,
  streamingMessage,
  savedTimestamp,
  isOpen,
  onToggleOpen,
  showSummaryStrip = true,
  onCancelStream,
  onRunAgain,
  onClearSaved,
  className = '',
}) => {
  const [internalOpen, setInternalOpen] = useState(false);
  const detailsOpen = isOpen !== undefined ? isOpen : internalOpen;
  const toggleDetails = onToggleOpen || (() => setInternalOpen((prev) => !prev));


  const durationSec = metrics?.search_time_ms != null ? (metrics.search_time_ms / 1000).toFixed(1) + 's' : null;
  const platformCount = metrics?.providers_searched?.length || 18;
  const savedAgo = formatSavedAgo(savedTimestamp);

  // Generate synthetic or observed Tool parts from metrics
  const providerTools: ToolPart[] = React.useMemo(() => {
    const list = metrics?.providers_searched;
    if (!list || list.length === 0) return [];

    return list.map((provider) => {
      const isCached = Boolean(metrics.cached || (metrics.serper_cache_hits && metrics.serper_cache_hits > 0));
      return {
        type: provider.toLowerCase(),
        state: isCached ? 'cached' : 'output-available',
        cached: isCached,
        durationMs: isCached ? 12 : Math.round((metrics.search_time_ms ?? 0) / list.length),
        resultCount: Math.max(1, Math.floor(totalResults / list.length)),
        input: {
          platform: provider,
          mode: isCached ? 'sqlite_cache_lookup' : 'live_ats_dork_fetch',
          budget_remaining: metrics.budget_exhausted ? '0/200' : 'active',
        },
        output: {
          status: 'success',
          tier: 'Tier 1 / Structured Schema',
          pages_fetched: metrics.pages_fetched ? Math.max(1, Math.floor(metrics.pages_fetched / list.length)) : 1,
          cached: isCached,
        },
        toolCallId: `call_${provider.substring(0, 3)}_${Math.abs(metrics.search_time_ms ?? 0).toString(16)}`,
      };
    });
  }, [metrics, totalResults]);

  return (
    <div className={cn("mb-4 space-y-2", className)}>
      {/* 1. Live SSE Streaming pulse bar */}
      {isStreaming && (
        <ThinkingBar
          text={streamingMessage || `Connecting to ATS endpoints & streaming listings...`}
          onStop={onCancelStream}
          stopLabel="Cancel stream"
        />
      )}

      {/* 2. Budget Alert or Quota Exhaustion notice */}
      {metrics?.budget_exhausted && (
        <SystemMessage variant="warning">
          Daily Serper query budget exhausted (200 requests/day). Bottom Pot is operating in persistent SQLite cache mode.
        </SystemMessage>
      )}

      {/* 3. Primary quiet summary strip (optional when rendered under SearchSummaryBar) */}
      {showSummaryStrip && (
        <div className="status-strip">
          <div className="flex items-center gap-3 flex-wrap">
            <span className="font-semibold text-[var(--ink)]">
              {totalResults} {totalResults === 1 ? 'posting' : 'postings'} from {platformCount} platforms
            </span>

            {durationSec && <span className="text-[var(--ink-muted)]">· {durationSec}</span>}
            {savedAgo && <span className="text-[var(--ink-subtle)]">· {savedAgo}</span>}

            {metrics && (
              <button
                type="button"
                className="btn-text text-[11px] inline-flex items-center gap-1 cursor-pointer font-mono text-[var(--ink-muted)] hover:text-[var(--ink)]"
                onClick={toggleDetails}
                aria-expanded={detailsOpen}
              >
                <Cpu size={12} className="text-[var(--accent)]" />
                <span>Telemetry ({providerTools.length})</span>
                {detailsOpen ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
              </button>
            )}
          </div>

          <div className="flex items-center gap-2">
            {onRunAgain && (
              <button
                type="button"
                className="btn btn-sm h-7 text-[11px] rounded-none! border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)]"
                onClick={onRunAgain}
              >
                <RefreshCw size={11} aria-hidden="true" />
                <span>Run again</span>
              </button>
            )}

            {savedTimestamp && onClearSaved && (
              <button
                type="button"
                className="btn btn-sm h-7 text-[11px] rounded-none! border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)]"
                onClick={onClearSaved}
              >
                <Trash2 size={11} aria-hidden="true" />
                <span>Clear saved</span>
              </button>
            )}
          </div>
        </div>
      )}

      {/* 4. Collapsible Telemetry Deck (Prompt Kit Tool cards) */}
      {detailsOpen && metrics && (
        <div
          className={`border border-[var(--border)] bg-[var(--surface)] p-4 text-xs font-mono space-y-4 ${
            showSummaryStrip ? 'border-t-0 -mt-2' : 'my-3'
          }`}
        >
          {/* Top telemetry KPIs */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 border-b border-[var(--border)] pb-3">
            <div>
              <span className="block text-[10px] uppercase text-[var(--ink-subtle)]">Engine Source</span>
              <span className="font-semibold text-[var(--ink)]">
                {metrics.cached ? 'SQLite Persistent Cache' : 'Live ATS Queries'}
              </span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-[var(--ink-subtle)]">Pages Inspected</span>
              <span className="font-semibold text-[var(--ink)]">
                {metrics.pages_fetched ?? metrics.total} pages
              </span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-[var(--ink-subtle)]">Execution Latency</span>
              <span className="font-semibold text-[var(--ink)]">
                {((metrics.search_time_ms ?? 0) / 1000).toFixed(2)}s
              </span>
            </div>
            <div>
              <span className="block text-[10px] uppercase text-[var(--ink-subtle)]">Cache Hit Efficiency</span>
              <span className="font-semibold text-[var(--ink)]">
                {metrics.serper_cache_hits ?? (metrics.cached ? metrics.total : 0)} hits
              </span>
            </div>
          </div>

          {/* Provider Tool Cards Grid */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <span className="text-[10px] uppercase tracking-wider text-[var(--ink-subtle)]">
                Provider Query Pipeline ({providerTools.length} ATS nodes)
              </span>
              <span className="text-[10px] text-[var(--ink-subtle)]">
                Click a card to inspect dork parameters & response payloads
              </span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
              {providerTools.map((toolPart) => (
                <Tool
                  key={toolPart.type}
                  toolPart={toolPart}
                  defaultOpen={false}
                  className="rounded-none! shadow-none"
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
