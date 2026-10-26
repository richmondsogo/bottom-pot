import React, { useState } from 'react';
import { Check, ExternalLink } from 'lucide-react';

interface AtsPlatformMatrixProps {
  onSearchPlatforms: (platformIds: string[]) => void;
}

interface PlatformDetail {
  id: string;
  name: string;
  dorkPattern: string;
  fidelity: string;
  category: 'global' | 'nigeria';
}

const PLATFORM_DETAILS: PlatformDetail[] = [
  { id: 'greenhouse', name: 'Greenhouse', dorkPattern: 'boards.greenhouse.io/*', fidelity: 'Tier 1–2 API/JSON-LD', category: 'global' },
  { id: 'lever', name: 'Lever', dorkPattern: 'jobs.lever.co/*', fidelity: 'Tier 2–3 JSON-LD/HTML', category: 'global' },
  { id: 'ashby', name: 'Ashby', dorkPattern: 'jobs.ashbyhq.com/*', fidelity: 'Tier 1 GraphQL API', category: 'global' },
  { id: 'workable', name: 'Workable', dorkPattern: 'apply.workable.com/*', fidelity: 'Tier 2–4 Meta', category: 'global' },
  { id: 'smartrecruiters', name: 'SmartRecruiters', dorkPattern: 'jobs.smartrecruiters.com/*', fidelity: 'Tier 1–2 API/JSON-LD', category: 'global' },
  { id: 'bamboohr', name: 'BambooHR', dorkPattern: '*.bamboohr.com/jobs/*', fidelity: 'Tier 2 JSON-LD', category: 'global' },
  { id: 'recruitee', name: 'Recruitee', dorkPattern: '*.recruitee.com/*', fidelity: 'Tier 2–3 Meta', category: 'global' },
  { id: 'breezy', name: 'Breezy HR', dorkPattern: '*.breezy.hr/*', fidelity: 'Tier 2–3 HTML', category: 'global' },
  { id: 'jobvite', name: 'Jobvite', dorkPattern: 'jobs.jobvite.com/*', fidelity: 'Tier 2–3 Meta', category: 'global' },
  { id: 'workday', name: 'Workday', dorkPattern: '*.myworkdayjobs.com/*', fidelity: 'Tier 2–4 Meta', category: 'global' },
  { id: 'personio', name: 'Personio', dorkPattern: '*.jobs.personio.de/*', fidelity: 'Tier 2 JSON-LD', category: 'global' },
  { id: 'pinpointhq', name: 'Pinpoint', dorkPattern: '*.pinpointhq.com/*', fidelity: 'Tier 1–2 API', category: 'global' },
  { id: 'rippling', name: 'Rippling', dorkPattern: 'ats.rippling.com/*', fidelity: 'Tier 1–2 API', category: 'global' },
  { id: 'taleo', name: 'Taleo', dorkPattern: '*.taleo.net/*', fidelity: 'Tier 3–4 Meta', category: 'global' },
  { id: 'teamtailor', name: 'Teamtailor', dorkPattern: '*.teamtailor.com/*', fidelity: 'Tier 2 JSON-LD', category: 'global' },
  { id: 'polywork', name: 'Polywork', dorkPattern: 'polywork.com/*', fidelity: 'Tier 2–3 Meta', category: 'global' },
  { id: 'jobberman', name: 'Jobberman (NG)', dorkPattern: 'jobberman.com/listings/*', fidelity: 'Tier 3 Adapter (NG)', category: 'nigeria' },
  { id: 'myjobmag', name: 'MyJobMag (NG)', dorkPattern: 'myjobmag.com/job/*', fidelity: 'Tier 3 Adapter (NG)', category: 'nigeria' },
];

export const AtsPlatformMatrix: React.FC<AtsPlatformMatrixProps> = ({
  onSearchPlatforms,
}) => {
  const [selected, setSelected] = useState<Set<string>>(
    () => new Set(PLATFORM_DETAILS.map((p) => p.id))
  );

  const togglePlatform = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  };

  const handleSelectAll = () => {
    setSelected(new Set(PLATFORM_DETAILS.map((p) => p.id)));
  };

  const handleSelectTop5 = () => {
    setSelected(new Set(['greenhouse', 'lever', 'ashby', 'workable', 'smartrecruiters']));
  };

  const handleClear = () => {
    setSelected(new Set());
  };

  return (
    <section id="platforms" className="py-16 bg-[var(--bg)] border-b border-[var(--border)]">
      <div className="page-shell">
        {/* Section Heading */}
        <div className="flex flex-wrap items-end justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-2 px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] text-xs font-mono text-[var(--ink-muted)] mb-3">
              coverage &amp; system of record
            </div>
            <h2 className="font-semibold text-2xl sm:text-3xl tracking-tight text-[var(--ink)]">
              18+ ATS engines queried at the source.
            </h2>
            <p className="text-sm text-[var(--ink-muted)] max-w-[64ch] mt-2">
              Select the platforms you trust&mdash;or query every supported ATS board in a single pass. Every slug is normalized, deduplicated, and mapped to its canonical company identifier.
            </p>
          </div>

          {/* Quick Platform Filters */}
          <div className="flex items-center gap-2 text-xs font-mono">
            <button
              type="button"
              onClick={handleSelectAll}
              className="px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)] cursor-pointer"
            >
              Select all (18)
            </button>
            <button
              type="button"
              onClick={handleSelectTop5}
              className="px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink)] cursor-pointer"
            >
              Top 5 ATS
            </button>
            <button
              type="button"
              onClick={handleClear}
              className="px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] text-[var(--ink-muted)] cursor-pointer"
            >
              Clear
            </button>
          </div>
        </div>

        {/* 18-Platform Architectural Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
          {PLATFORM_DETAILS.map((platform) => {
            const isSelected = selected.has(platform.id);

            return (
              <button
                key={platform.id}
                type="button"
                onClick={() => togglePlatform(platform.id)}
                className={`p-3.5 text-left border transition-all cursor-pointer flex flex-col justify-between min-h-[110px] ${
                  isSelected
                    ? 'border-[var(--ink)] bg-[var(--surface-subtle)] text-[var(--ink)]'
                    : 'border-[var(--border)] bg-[var(--surface)] text-[var(--ink-muted)] hover:border-[var(--border-strong)] hover:text-[var(--ink)]'
                }`}
              >
                <div>
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="font-mono text-xs font-semibold lowercase">
                      {platform.id}
                    </span>
                    {isSelected && (
                      <Check className="w-3.5 h-3.5 text-[var(--accent)] shrink-0" />
                    )}
                  </div>
                  <div className="text-xs font-medium text-[var(--ink)]">
                    {platform.name}
                  </div>
                </div>

                <div className="mt-2 pt-2 border-t border-[var(--border)]">
                  <div className="text-[10px] font-mono text-[var(--ink-subtle)] truncate">
                    {platform.dorkPattern}
                  </div>
                  <div className="text-[10px] font-mono text-[var(--ink-muted)] mt-0.5">
                    {platform.fidelity}
                  </div>
                </div>
              </button>
            );
          })}
        </div>

        {/* Bottom Action Strip */}
        <div className="mt-8 flex flex-wrap items-center justify-between gap-4 p-4 border border-[var(--border)] bg-[var(--surface)]">
          <div className="text-xs text-[var(--ink-muted)]">
            <span className="font-semibold text-[var(--ink)]">{selected.size} platforms</span> selected for search.
          </div>
          <button
            type="button"
            onClick={() => onSearchPlatforms(Array.from(selected))}
            className="h-9 px-4 bg-[var(--accent)] text-[var(--accent-foreground)] text-xs font-medium rounded-none hover:bg-[var(--accent-hover)] transition-colors flex items-center gap-1.5 cursor-pointer select-none"
          >
            <span>Search selected platforms in Workspace</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </section>
  );
};
