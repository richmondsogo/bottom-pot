import React, { useState, useEffect } from 'react';
import { ExternalLink, RotateCcw, ShieldCheck, Terminal, Keyboard, Table as TableIcon } from 'lucide-react';

interface HeroInteractiveStageProps {
  onOpenWorkspace: () => void;
  onOpenCommand: () => void;
}

interface SampleJob {
  id: string;
  role: string;
  company: string;
  location: string;
  workModel: 'Remote' | 'Hybrid' | null;
  platform: string;
  salary: string | null;
  posted: string;
  sourceTier: string;
  sourceKey: string;
  evidence: string;
  region: 'global' | 'nigeria';
}

const SAMPLE_JOBS: SampleJob[] = [
  {
    id: 'job-1',
    role: 'Staff Frontend Engineer (Design Systems)',
    company: 'Linear',
    location: 'Remote (Worldwide)',
    workModel: 'Remote',
    platform: 'ashby',
    salary: '$180k – $220k',
    posted: '2d ago',
    sourceTier: 'Tier 1 of 7',
    sourceKey: 'api_enum',
    evidence: 'workplaceType: "remote" (Ashby GraphQL API endpoint)',
    region: 'global',
  },
  {
    id: 'job-2',
    role: 'Senior Core Systems Developer',
    company: 'Paystack',
    location: 'Lagos, Nigeria (Hybrid)',
    workModel: 'Hybrid',
    platform: 'greenhouse',
    salary: null,
    posted: '3d ago',
    sourceTier: 'Tier 3 of 7',
    sourceKey: 'li_tag',
    evidence: '<li class="posting-category">Hybrid (Ikeja, Lagos)</li>',
    region: 'nigeria',
  },
  {
    id: 'job-3',
    role: 'Distributed Database Engineer',
    company: 'Supabase',
    location: 'Remote (Worldwide)',
    workModel: 'Remote',
    platform: 'lever',
    salary: '$160k – $200k',
    posted: '4d ago',
    sourceTier: 'Tier 2 of 7',
    sourceKey: 'jsonld',
    evidence: '"jobLocationType": "TELECOMMUTE" (Schema.org JSON-LD)',
    region: 'global',
  },
  {
    id: 'job-4',
    role: 'Product Designer (Design Platform)',
    company: 'Raycast',
    location: 'London, UK / Remote EMEA',
    workModel: 'Remote',
    platform: 'ashby',
    salary: '£90k – £120k',
    posted: '1d ago',
    sourceTier: 'Tier 1 of 7',
    sourceKey: 'api_enum',
    evidence: 'workplaceType: "remote" (Ashby GraphQL API)',
    region: 'global',
  },
  {
    id: 'job-5',
    role: 'Principal Backend Architect',
    company: 'Moniepoint',
    location: 'Lagos, Nigeria',
    workModel: 'Hybrid',
    platform: 'workable',
    salary: null,
    posted: '5d ago',
    sourceTier: 'Tier 4 of 7',
    sourceKey: 'location',
    evidence: 'location: "Lagos, NG (Office + 2 days WFH)"',
    region: 'nigeria',
  },
  {
    id: 'job-6',
    role: 'Infrastructure & Edge Engineer',
    company: 'Vercel',
    location: 'Remote (Global)',
    workModel: 'Remote',
    platform: 'greenhouse',
    salary: '$175k – $210k',
    posted: '1d ago',
    sourceTier: 'Tier 2 of 7',
    sourceKey: 'jsonld',
    evidence: '"applicantLocationRequirements": "Worldwide"',
    region: 'global',
  },
  {
    id: 'job-7',
    role: 'Lead Mobile Engineer (Flutter)',
    company: 'PiggyVest',
    location: 'Lagos, Nigeria',
    workModel: null, // ADR 0001: Missing workplace type remains clean null
    platform: 'bamboohr',
    salary: null,
    posted: '6d ago',
    sourceTier: 'Tier 7 of 7',
    sourceKey: 'null',
    evidence: 'Absence of evidence: employer specified no workplace model. Left as whitespace.',
    region: 'nigeria',
  },
  {
    id: 'job-8',
    role: 'Senior Payments SRE',
    company: 'Flutterwave',
    location: 'Lagos, Nigeria / Remote EMEA',
    workModel: 'Remote',
    platform: 'smartrecruiters',
    salary: null,
    posted: '3d ago',
    sourceTier: 'Tier 2 of 7',
    sourceKey: 'jsonld',
    evidence: '"jobLocationType": "TELECOMMUTE" (SmartRecruiters payload)',
    region: 'nigeria',
  },
];

export const HeroInteractiveStage: React.FC<HeroInteractiveStageProps> = ({
  onOpenWorkspace,
  onOpenCommand,
}) => {
  const [activeTab, setActiveTab] = useState<'table' | 'provenance' | 'stream' | 'command'>('table');

  // Tab 1 state
  const [selectedJobId, setSelectedJobId] = useState<string>('job-1');
  const [workModelFilter, setWorkModelFilter] = useState<'all' | 'remote' | 'hybrid'>('all');
  const [regionFilter, setRegionFilter] = useState<'all' | 'global' | 'nigeria'>('all');

  // Tab 2 state
  const [provenanceJobIndex, setProvenanceJobIndex] = useState<number>(0);

  // Tab 3 state (Live SSE Stream Simulation)
  const [streamProgress, setStreamProgress] = useState<number>(0);
  const [streamLines, setStreamLines] = useState<string[]>([]);
  const [isStreaming, setIsStreaming] = useState<boolean>(true);

  // Tab 4 state (Command palette interactive key simulator)
  const [activeCmdKey, setActiveCmdKey] = useState<string | null>(null);

  // Stream simulation loop
  useEffect(() => {
    if (activeTab !== 'stream') return;

    const events = [
      'DISPATCH: site:jobs.ashbyhq.com/linear "Software Engineer"',
      'DISPATCH: site:boards.greenhouse.io/paystack "Backend"',
      'CACHE_HIT: 2-tier SQLite cache validated (hash: 8f4a21e, TTL: 12h)',
      'SSE_CHUNK: +4 Ashby listings extracted via JSON-LD',
      'DISPATCH: site:jobs.lever.co/supabase "Systems"',
      'DEDUPE: Filtered 14 repeated URLs across multi-engine dorks',
      'CIRCUIT_BREAKER: 0 host errors · Concurrency 12/20 active',
      'STREAM_HYDRATE: 24 verified roles rendered with 7-tier provenance',
    ];

    const timer = setTimeout(() => {
      setIsStreaming(true);
      setStreamLines([]);
      setStreamProgress(0);
    }, 0);

    let current = 0;
    const interval = setInterval(() => {
      if (current < events.length) {
        setStreamLines((prev) => [...prev, events[current]]);
        current++;
        setStreamProgress(Math.round((current / events.length) * 100));
      } else {
        setIsStreaming(false);
        clearInterval(interval);
      }
    }, 450);

    return () => {
      clearTimeout(timer);
      clearInterval(interval);
    };
  }, [activeTab]);

  const handleReplayStream = () => {
    setStreamLines([]);
    setStreamProgress(0);
    setIsStreaming(true);
    const events = [
      'DISPATCH: site:jobs.ashbyhq.com/linear "Software Engineer"',
      'DISPATCH: site:boards.greenhouse.io/paystack "Backend"',
      'CACHE_HIT: 2-tier SQLite cache validated (hash: 8f4a21e, TTL: 12h)',
      'SSE_CHUNK: +4 Ashby listings extracted via JSON-LD',
      'DISPATCH: site:jobs.lever.co/supabase "Systems"',
      'DEDUPE: Filtered 14 repeated URLs across multi-engine dorks',
      'CIRCUIT_BREAKER: 0 host errors · Concurrency 12/20 active',
      'STREAM_HYDRATE: 24 verified roles rendered with 7-tier provenance',
    ];
    let current = 0;
    const interval = setInterval(() => {
      if (current < events.length) {
        setStreamLines((prev) => [...prev, events[current]]);
        current++;
        setStreamProgress(Math.round((current / events.length) * 100));
      } else {
        setIsStreaming(false);
        clearInterval(interval);
      }
    }, 450);
  };

  // Filtered jobs for Tab 1
  const filteredJobs = SAMPLE_JOBS.filter((job) => {
    if (workModelFilter === 'remote' && job.workModel !== 'Remote') return false;
    if (workModelFilter === 'hybrid' && job.workModel !== 'Hybrid') return false;
    if (regionFilter !== 'all' && job.region !== regionFilter) return false;
    return true;
  });

  const selectedJob = SAMPLE_JOBS.find((j) => j.id === selectedJobId) || SAMPLE_JOBS[0];
  const provJob = SAMPLE_JOBS[provenanceJobIndex];

  return (
    <section id="stage" className="border-t border-[var(--border)] pt-8 pb-16 bg-[var(--bg)]">
      <div className="page-shell">
        {/* Frame Outer Shell */}
        <div className="border border-[var(--border-strong)] bg-[var(--surface)] shadow-none">
          {/* Stage Control Header Bar */}
          <div className="h-12 border-b border-[var(--border)] px-4 flex flex-wrap items-center justify-between gap-3 bg-[var(--surface-subtle)]">
            {/* Left Chrome Metadata */}
            <div className="flex items-center gap-3 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-[var(--ink-muted)]">
                <span className="w-2 h-2 bg-[var(--accent)]" />
                bottom-pot://workspace/live-preview
              </span>
              <span className="text-[var(--border-strong)] hidden sm:inline">|</span>
              <span className="text-[var(--ink-subtle)] hidden sm:inline">
                24 verified roles · 0 fabricated fields
              </span>
            </div>

            {/* Right Tabs */}
            <div className="flex items-center border border-[var(--border)] bg-[var(--surface)]">
              <button
                type="button"
                onClick={() => setActiveTab('table')}
                className={`h-8 px-3 text-xs font-mono transition-colors flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'table'
                    ? 'bg-[var(--accent)] text-[var(--accent-foreground)] font-medium'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                <TableIcon className="w-3.5 h-3.5" />
                <span>01. Live ATS table</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('provenance')}
                className={`h-8 px-3 text-xs font-mono transition-colors border-l border-[var(--border)] flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'provenance'
                    ? 'bg-[var(--accent)] text-[var(--accent-foreground)] font-medium'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                <ShieldCheck className="w-3.5 h-3.5" />
                <span>02. 7-tier provenance</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('stream')}
                className={`h-8 px-3 text-xs font-mono transition-colors border-l border-[var(--border)] flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'stream'
                    ? 'bg-[var(--accent)] text-[var(--accent-foreground)] font-medium'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                <Terminal className="w-3.5 h-3.5" />
                <span>03. SSE dork stream</span>
              </button>
              <button
                type="button"
                onClick={() => setActiveTab('command')}
                className={`h-8 px-3 text-xs font-mono transition-colors border-l border-[var(--border)] flex items-center gap-1.5 cursor-pointer ${
                  activeTab === 'command'
                    ? 'bg-[var(--accent)] text-[var(--accent-foreground)] font-medium'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                <Keyboard className="w-3.5 h-3.5" />
                <span>04. Command palette (⌘K)</span>
              </button>
            </div>
          </div>

          {/* TAB 1: MINIATURE LIVE RESULTS TABLE */}
          {activeTab === 'table' && (
            <div className="p-4 sm:p-6">
              {/* Filter Sub-bar */}
              <div className="flex flex-wrap items-center justify-between gap-3 pb-4 border-b border-[var(--border)] text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-mono text-[var(--ink-muted)]">Work model:</span>
                  <div className="flex border border-[var(--border)] bg-[var(--surface)]">
                    {(['all', 'remote', 'hybrid'] as const).map((m) => (
                      <button
                        key={m}
                        type="button"
                        onClick={() => setWorkModelFilter(m)}
                        className={`h-7 px-2.5 capitalize font-medium transition-colors cursor-pointer ${
                          workModelFilter === m
                            ? 'bg-[var(--surface-selected)] text-[var(--ink)]'
                            : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                        }`}
                      >
                        {m}
                      </button>
                    ))}
                  </div>
                </div>

                <div className="flex items-center gap-2">
                  <span className="font-mono text-[var(--ink-muted)]">Scope:</span>
                  <div className="flex border border-[var(--border)] bg-[var(--surface)]">
                    <button
                      type="button"
                      onClick={() => setRegionFilter('all')}
                      className={`h-7 px-2.5 font-medium transition-colors cursor-pointer ${
                        regionFilter === 'all'
                          ? 'bg-[var(--surface-selected)] text-[var(--ink)]'
                          : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                      }`}
                    >
                      All
                    </button>
                    <button
                      type="button"
                      onClick={() => setRegionFilter('global')}
                      className={`h-7 px-2.5 font-medium border-l border-[var(--border)] transition-colors cursor-pointer ${
                        regionFilter === 'global'
                          ? 'bg-[var(--surface-selected)] text-[var(--ink)]'
                          : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                      }`}
                    >
                      Global Remote
                    </button>
                    <button
                      type="button"
                      onClick={() => setRegionFilter('nigeria')}
                      className={`h-7 px-2.5 font-medium border-l border-[var(--border)] transition-colors cursor-pointer ${
                        regionFilter === 'nigeria'
                          ? 'bg-[var(--surface-selected)] text-[var(--ink)]'
                          : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                      }`}
                    >
                      Nigeria / EMEA
                    </button>
                  </div>
                </div>

                <button
                  type="button"
                  onClick={onOpenWorkspace}
                  className="font-medium text-[var(--ink)] hover:underline flex items-center gap-1 ml-auto cursor-pointer"
                >
                  <span>Open full workspace</span>
                  <ExternalLink className="w-3.5 h-3.5" />
                </button>
              </div>

              {/* Table Container */}
              <div className="overflow-x-auto mt-4 border border-[var(--border)]">
                <table className="w-full text-left text-xs border-collapse" style={{ tableLayout: 'fixed' }}>
                  <colgroup>
                    <col style={{ width: '38%' }} />
                    <col style={{ width: '22%' }} />
                    <col style={{ width: '22%' }} />
                    <col style={{ width: '18%' }} />
                  </colgroup>
                  <thead>
                    <tr className="border-b border-[var(--border)] bg-[var(--surface-subtle)] text-[var(--ink-subtle)] font-medium">
                      <th className="py-2.5 px-3.5 font-medium">Role</th>
                      <th className="py-2.5 px-3.5 font-medium">Company</th>
                      <th className="py-2.5 px-3.5 font-medium">Location</th>
                      <th className="py-2.5 px-3.5 font-medium">Work model</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[var(--border)]">
                    {filteredJobs.map((job) => {
                      const isSelected = job.id === selectedJobId;
                      return (
                        <tr
                          key={job.id}
                          onClick={() => setSelectedJobId(job.id)}
                          className={`cursor-pointer transition-colors group ${
                            isSelected
                              ? 'bg-[var(--surface-subtle)] shadow-[inset_2px_0_0_0_var(--accent)]'
                              : 'hover:bg-[var(--surface-hover)] hover:shadow-[inset_2px_0_0_0_var(--accent)]'
                          }`}
                        >
                          <td className="py-2.5 px-3.5 font-medium text-[var(--ink)] truncate">
                            {job.role}
                          </td>
                          <td className="py-2.5 px-3.5">
                            <div className="flex items-center gap-2">
                              <span className="w-5 h-5 bg-[var(--surface-raised)] border border-[var(--border)] flex items-center justify-center text-[10px] font-semibold text-[var(--ink)] shrink-0">
                                {job.company.slice(0, 2).toUpperCase()}
                              </span>
                              <div className="truncate">
                                <div className="text-[var(--ink)] font-medium">{job.company}</div>
                                <div className="text-[10px] font-mono text-[var(--ink-subtle)] lowercase">
                                  {job.platform}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td className="py-2.5 px-3.5 text-[var(--ink-muted)] truncate">
                            {job.location}
                          </td>
                          <td className="py-2.5 px-3.5">
                            {job.workModel === 'Remote' && (
                              <span className="inline-flex items-center gap-1.5 px-1.5 py-0.5 bg-[var(--tag-remote-bg)] text-[var(--tag-remote-text)] text-[11px] font-medium">
                                <span className="w-1.5 h-1.5 bg-[var(--tag-remote-marker)]" />
                                Remote
                              </span>
                            )}
                            {job.workModel === 'Hybrid' && (
                              <span className="inline-flex items-center gap-1.5 px-1.5 py-0.5 bg-[var(--tag-hybrid-bg)] text-[var(--tag-hybrid-text)] text-[11px] font-medium">
                                <span className="w-1.5 h-1.5 bg-[var(--tag-hybrid-marker)]" />
                                Hybrid
                              </span>
                            )}
                            {job.workModel === null && (
                              <span className="text-[var(--ink-subtle)] font-mono text-[10px] italic">
                                &mdash;
                              </span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>

              {/* Selected Job Quick Provenance Strip */}
              <div className="mt-4 p-3 border border-[var(--border)] bg-[var(--surface-subtle)] flex flex-wrap items-center justify-between gap-3 text-xs">
                <div className="flex items-center gap-2">
                  <span className="font-semibold text-[var(--ink)]">{selectedJob.company}</span>
                  <span className="font-mono text-[var(--ink-muted)]">·</span>
                  <span className="font-mono text-[var(--ink-muted)]">{selectedJob.sourceTier} ({selectedJob.sourceKey})</span>
                  <span className="text-[var(--ink-subtle)] hidden sm:inline">&mdash;</span>
                  <code className="text-[11px] font-mono text-[var(--ink-muted)] bg-[var(--surface)] px-2 py-0.5 border border-[var(--border)] truncate max-w-[380px]">
                    {selectedJob.evidence}
                  </code>
                </div>
                <button
                  type="button"
                  onClick={onOpenWorkspace}
                  className="px-3 py-1 bg-[var(--accent)] text-[var(--accent-foreground)] text-xs font-medium cursor-pointer"
                >
                  View in full workspace ↗
                </button>
              </div>
            </div>
          )}

          {/* TAB 2: 7-TIER PROVENANCE INSPECTOR */}
          {activeTab === 'provenance' && (
            <div className="p-4 sm:p-6 grid grid-cols-1 lg:grid-cols-12 gap-6">
              {/* Left Column: Sample Roles Picker */}
              <div className="lg:col-span-5 space-y-2">
                <h4 className="text-xs font-mono uppercase tracking-wider text-[var(--ink-subtle)] mb-3">
                  Select sample posting
                </h4>
                {SAMPLE_JOBS.slice(0, 4).map((job, idx) => (
                  <button
                    key={job.id}
                    type="button"
                    onClick={() => setProvenanceJobIndex(idx)}
                    className={`w-full text-left p-3 border transition-colors cursor-pointer ${
                      provenanceJobIndex === idx
                        ? 'border-[var(--ink)] bg-[var(--surface-subtle)] shadow-[inset_2px_0_0_0_var(--accent)]'
                        : 'border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)]'
                    }`}
                  >
                    <div className="flex items-center justify-between text-xs mb-1">
                      <span className="font-semibold text-[var(--ink)]">{job.company}</span>
                      <span className="font-mono text-[11px] text-[var(--ink-muted)]">{job.sourceKey}</span>
                    </div>
                    <div className="text-xs text-[var(--ink-muted)] truncate">{job.role}</div>
                  </button>
                ))}
              </div>

              {/* Right Column: 480px-Style Provenance Card */}
              <div className="lg:col-span-7 border border-[var(--border)] bg-[var(--surface-subtle)] p-5">
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-3 mb-4">
                  <div>
                    <span className="text-xs font-mono text-[var(--ink-muted)]">PROVENANCE AUDIT CARD</span>
                    <h3 className="font-semibold text-sm text-[var(--ink)] mt-0.5">{provJob.company} &mdash; {provJob.role}</h3>
                  </div>
                  <span className="px-2 py-0.5 border border-[var(--border)] bg-[var(--surface)] text-xs font-mono text-[var(--ink)]">
                    {provJob.platform}
                  </span>
                </div>

                <div className="space-y-4 text-xs">
                  <div className="grid grid-cols-2 gap-3">
                    <div className="border border-[var(--border)] bg-[var(--surface)] p-3">
                      <span className="text-[11px] font-mono text-[var(--ink-subtle)] block mb-1">
                        Workplace Classification
                      </span>
                      <span className="font-semibold text-[var(--ink)]">
                        {provJob.workModel ? provJob.workModel : 'Unspecified by Employer (Null)'}
                      </span>
                    </div>

                    <div className="border border-[var(--border)] bg-[var(--surface)] p-3">
                      <span className="text-[11px] font-mono text-[var(--ink-subtle)] block mb-1">
                        Extraction Tier
                      </span>
                      <span className="font-mono font-semibold text-[var(--ink)]">
                        {provJob.sourceTier} ({provJob.sourceKey})
                      </span>
                    </div>
                  </div>

                  <div className="border border-[var(--border)] bg-[var(--surface)] p-3">
                    <span className="text-[11px] font-mono text-[var(--ink-subtle)] block mb-1">
                      Literal ATS Source Evidence (Zero Fabrication)
                    </span>
                    <pre className="mt-1 font-mono text-[11px] bg-[var(--surface-subtle)] p-2.5 border border-[var(--border)] overflow-x-auto text-[var(--ink)]">
                      {provJob.evidence}
                    </pre>
                  </div>

                  <div className="text-[11px] text-[var(--ink-muted)] leading-relaxed">
                    <strong>ADR 0001 (Unknown Beats Wrong):</strong> If an employer leaves workplace parameters blank or uses ambiguous phrasing, Bottom Pot refuses to invent tags. Evidence is captured verbatim.
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* TAB 3: SSE DORK STREAM SIMULATOR */}
          {activeTab === 'stream' && (
            <div className="p-4 sm:p-6 font-mono text-xs">
              <div className="flex items-center justify-between mb-4 border-b border-[var(--border)] pb-3">
                <div className="flex items-center gap-2">
                  <span className={`w-2 h-2 ${isStreaming ? 'bg-[var(--accent)] animate-pulse' : 'bg-[var(--ink-subtle)]'}`} />
                  <span className="font-semibold text-[var(--ink)]">
                    {isStreaming ? 'Live SSE Stream Active' : 'Stream Finished'} &mdash; {streamProgress}% complete
                  </span>
                </div>
                <button
                  type="button"
                  onClick={handleReplayStream}
                  className="px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] flex items-center gap-1.5 cursor-pointer text-[var(--ink)]"
                >
                  <RotateCcw className="w-3 h-3" />
                  <span>Replay stream</span>
                </button>
              </div>

              {/* Progress meter */}
              <div className="w-full h-1 bg-[var(--border)] mb-4 overflow-hidden">
                <div
                  className="h-full bg-[var(--accent)] transition-all duration-300"
                  style={{ width: `${streamProgress}%` }}
                />
              </div>

              {/* Stream output console */}
              <div className="bg-[var(--surface-subtle)] border border-[var(--border)] p-4 space-y-2 h-[240px] overflow-y-auto">
                {streamLines.map((line, idx) => {
                  const isCache = line.startsWith('CACHE_HIT');
                  const isDedupe = line.startsWith('DEDUPE');
                  const isChunk = line.startsWith('SSE_CHUNK');
                  const isHydrate = line.startsWith('STREAM_HYDRATE');

                  return (
                    <div key={idx} className="flex items-start gap-2">
                      <span className="text-[var(--ink-subtle)] select-none">
                        [{String(idx + 1).padStart(2, '0')}]
                      </span>
                      <span
                        className={
                          isCache
                            ? 'text-amber-700 dark:text-amber-400 font-semibold'
                            : isChunk
                            ? 'text-emerald-700 dark:text-emerald-400 font-semibold'
                            : isHydrate
                            ? 'text-[var(--ink)] font-bold'
                            : isDedupe
                            ? 'text-[var(--ink-muted)]'
                            : 'text-[var(--ink)]'
                        }
                      >
                        {line}
                      </span>
                    </div>
                  );
                })}
              </div>
            </div>
          )}

          {/* TAB 4: COMMAND PALETTE PREVIEW */}
          {activeTab === 'command' && (
            <div className="p-4 sm:p-6">
              <div className="max-w-[620px] mx-auto border border-[var(--border-strong)] bg-[var(--surface)] shadow-none">
                <div className="p-3 border-b border-[var(--border)] flex items-center gap-2.5">
                  <span className="text-xs font-mono text-[var(--ink-muted)] select-none">⌘K:</span>
                  <input
                    readOnly
                    value="triage: remote lagos engineer"
                    className="w-full bg-transparent text-xs font-mono text-[var(--ink)] outline-none"
                  />
                  <span className="text-[10px] font-mono text-[var(--ink-subtle)] border border-[var(--border)] px-1.5 py-0.5">
                    ESC
                  </span>
                </div>

                <div className="divide-y divide-[var(--border)] text-xs">
                  {[
                    { key: 'j/k', label: 'Traverse postings up / down', action: 'Move active row bar' },
                    { key: 'Enter', label: 'Inspect 7-tier provenance card', action: 'Open detail sheet' },
                    { key: 'o', label: 'Open ATS posting directly at source', action: 'External link' },
                    { key: '/', label: 'Focus quick filter bar', action: 'Jump to input' },
                    { key: '⌘K', label: 'Open full command deck', action: 'System commands' },
                  ].map((cmd) => (
                    <button
                      key={cmd.key}
                      type="button"
                      onClick={() => {
                        setActiveCmdKey(cmd.key);
                        if (cmd.key === '⌘K') onOpenCommand();
                      }}
                      className={`w-full p-3 flex items-center justify-between text-left transition-colors cursor-pointer ${
                        activeCmdKey === cmd.key
                          ? 'bg-[var(--surface-selected)] text-[var(--ink)]'
                          : 'hover:bg-[var(--surface-hover)] text-[var(--ink-muted)]'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <kbd className="px-2 py-0.5 bg-[var(--surface-raised)] border border-[var(--border)] font-mono text-xs font-semibold text-[var(--ink)]">
                          {cmd.key}
                        </kbd>
                        <span className="text-[var(--ink)] font-medium">{cmd.label}</span>
                      </div>
                      <span className="font-mono text-[11px] text-[var(--ink-subtle)]">
                        {cmd.action}
                      </span>
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
};
