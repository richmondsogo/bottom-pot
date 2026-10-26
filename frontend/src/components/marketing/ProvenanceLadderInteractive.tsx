import React, { useState } from 'react';
import { ShieldCheck } from 'lucide-react';

interface TierItem {
  tier: number;
  key: string;
  name: string;
  source: string;
  confidence: string;
  snippet: string;
  explanation: string;
}

const TIERS: TierItem[] = [
  {
    tier: 1,
    key: 'api_enum',
    name: 'Structured API Enumeration',
    source: 'Ashby / SmartRecruiters GraphQL & REST API',
    confidence: '100% Deterministic',
    snippet: `{\n  "jobPosting": {\n    "id": "fe941a80-0a2b",\n    "workplaceType": "remote",\n    "isRemote": true\n  }\n}`,
    explanation: 'Direct ATS backend enum. The hiring team explicitly selected "Remote" in their system of record.',
  },
  {
    tier: 2,
    key: 'jsonld',
    name: 'Schema.org JSON-LD Metadata',
    source: 'Greenhouse / Lever Embedded Meta',
    confidence: '95% Deterministic',
    snippet: `{\n  "@context": "https://schema.org",\n  "@type": "JobPosting",\n  "jobLocationType": "TELECOMMUTE",\n  "applicantLocationRequirements": {\n    "@type": "Country",\n    "name": "Worldwide"\n  }\n}`,
    explanation: 'Canonical search engine metadata embedded in the ATS page markup before render.',
  },
  {
    tier: 3,
    key: 'li_tag',
    name: 'Structured Category List Tag',
    source: 'Lever / Workable Metadata List',
    confidence: '90% High Signal',
    snippet: `<div class="posting-categories">\n  <li class="posting-category workplace-type">Hybrid</li>\n  <li class="posting-category location">Lagos, Nigeria</li>\n</div>`,
    explanation: 'Dedicated HTML category badges rendered specifically for workplace parameters.',
  },
  {
    tier: 4,
    key: 'location',
    name: 'Location Field Normalizer',
    source: 'Workable / BambooHR Location Header',
    confidence: '80% Normalized',
    snippet: `{\n  "location": "Lagos, Nigeria (Office + 2 Days WFH)",\n  "normalized": "Hybrid",\n  "evidence": "matched keyword: '2 Days WFH'"\n}`,
    explanation: 'Extracted from the primary location string when explicit tags are absent.',
  },
  {
    tier: 5,
    key: 'title',
    name: 'Job Title Keyword Matching',
    source: 'All Supported Platforms',
    confidence: '70% Fallback',
    snippet: `{\n  "title": "Senior Backend Engineer - Fully Remote (EMEA)",\n  "matched_token": "Fully Remote"\n}`,
    explanation: 'Conservative regex matching on explicit remote tokens inside the job title itself.',
  },
  {
    tier: 6,
    key: 'description',
    name: 'Deep Description Text Scan',
    source: 'Deep Scrape HTML Parsing',
    confidence: '60% Heuristic',
    snippet: `<blockquote>\n  "This is a hybrid role requiring attendance at our Victoria Island office on Tuesdays and Thursdays."\n</blockquote>`,
    explanation: 'Carefully scoped contextual keyword scanning across the body of the job description.',
  },
  {
    tier: 7,
    key: 'null',
    name: 'Unspecified / Clean Whitespace',
    source: 'ADR 0001 (Unknown Beats Wrong)',
    confidence: 'Zero Guesswork',
    snippet: `{\n  "work_model": null,\n  "evidence": null,\n  "rendered_cell": " "\n}`,
    explanation: 'If the employer provided no evidence, the cell stays empty. We never invent "N/A" or "Unknown".',
  },
];

export const ProvenanceLadderInteractive: React.FC = () => {
  const [selectedTier, setSelectedTier] = useState<number>(1);
  const currentTier = TIERS.find((t) => t.tier === selectedTier) || TIERS[0];

  return (
    <div className="border border-[var(--border)] bg-[var(--surface)] p-4 sm:p-6 flex flex-col justify-between h-full">
      <div>
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-[var(--accent)]" />
            <h4 className="font-semibold text-sm text-[var(--ink)]">
              Auditable work-model provenance
            </h4>
          </div>
          <span className="font-mono text-xs text-[var(--ink-muted)]">
            Tier {currentTier.tier} of 7
          </span>
        </div>

        <p className="text-xs text-[var(--ink-muted)] leading-relaxed mb-4">
          Most job boards slap an inaccurate &ldquo;Remote&rdquo; tag on roles that require office attendance. Bottom Pot evaluates a deterministic 7-tier ladder and captures the literal snippet.
        </p>

        {/* 7-Step Horizontal or Compact Selector */}
        <div className="grid grid-cols-7 gap-1 mb-4">
          {TIERS.map((tier) => {
            const isActive = tier.tier === selectedTier;
            return (
              <button
                key={tier.tier}
                type="button"
                onClick={() => setSelectedTier(tier.tier)}
                className={`h-8 flex flex-col items-center justify-center border font-mono text-[11px] transition-colors cursor-pointer ${
                  isActive
                    ? 'border-[var(--ink)] bg-[var(--surface-selected)] font-bold text-[var(--ink)] shadow-[inset_0_-2px_0_0_var(--accent)]'
                    : 'border-[var(--border)] bg-[var(--surface-subtle)] text-[var(--ink-muted)] hover:text-[var(--ink)] hover:bg-[var(--surface-hover)]'
                }`}
                title={`Tier ${tier.tier}: ${tier.key}`}
              >
                T{tier.tier}
              </button>
            );
          })}
        </div>

        {/* Selected Tier Diagnostic Box */}
        <div className="border border-[var(--border)] bg-[var(--surface-subtle)] p-3 text-xs">
          <div className="flex items-center justify-between mb-1.5">
            <span className="font-semibold text-[var(--ink)]">{currentTier.name}</span>
            <span className="font-mono text-[11px] text-[var(--ink-muted)]">{currentTier.confidence}</span>
          </div>
          <div className="font-mono text-[11px] text-[var(--ink-subtle)] mb-2">
            source: {currentTier.source}
          </div>
          <pre className="font-mono text-[11px] bg-[var(--surface)] p-2.5 border border-[var(--border)] overflow-x-auto text-[var(--ink)] leading-snug">
            {currentTier.snippet}
          </pre>
          <p className="text-[11px] text-[var(--ink-muted)] mt-2 leading-relaxed">
            {currentTier.explanation}
          </p>
        </div>
      </div>
    </div>
  );
};
