import React, { useState } from 'react';
import { ProvenanceLadderInteractive } from './ProvenanceLadderInteractive';
import { Database, Globe, Cpu, Eye } from 'lucide-react';

export const BentoFeatureGrid: React.FC = () => {
  // Cell 2 state (Cache & SSE diagnostics simulation)
  const [cacheMode, setCacheMode] = useState<'hit' | 'live'>('hit');

  // Cell 3 state (Location & ecosystem switcher)
  const [scopeSelection, setScopeSelection] = useState<'global' | 'nigeria' | 'emea'>('global');

  // Cell 4 state (Keyboard triage & visited memory)
  const [activeRow, setActiveRow] = useState<number>(0);
  const [visitedSet, setVisitedSet] = useState<Set<number>>(new Set([1]));

  const sampleTriageRows = [
    { id: 0, title: 'Staff Frontend Engineer', company: 'Linear', model: 'Remote' },
    { id: 1, title: 'Senior Backend Engineer', company: 'Paystack', model: 'Hybrid (Lagos)' },
    { id: 2, title: 'Systems Infrastructure Engineer', company: 'Supabase', model: 'Remote' },
  ];

  const handleRowNav = (direction: 'up' | 'down') => {
    setActiveRow((prev) => {
      const next = direction === 'up' ? Math.max(0, prev - 1) : Math.min(sampleTriageRows.length - 1, prev + 1);
      return next;
    });
  };

  const handleToggleVisited = (idx: number) => {
    setVisitedSet((prev) => {
      const next = new Set(prev);
      if (next.has(idx)) next.delete(idx);
      else next.add(idx);
      return next;
    });
  };

  const ecosystemRoles = [
    { company: 'Paystack', role: 'Staff Backend Engineer', location: 'Lagos / Remote NG', scope: 'nigeria', mono: 'PS' },
    { company: 'Moniepoint', role: 'Lead DevOps / Cloud Architect', location: 'Lagos, Nigeria', scope: 'nigeria', mono: 'MP' },
    { company: 'Linear', role: 'Product Designer (Design Systems)', location: 'Remote (Worldwide)', scope: 'global', mono: 'LN' },
    { company: 'GitLab', role: 'Senior Security Specialist', location: 'Remote (EMEA Friendly)', scope: 'emea', mono: 'GL' },
  ];

  const filteredEcosystem = ecosystemRoles.filter((r) => {
    if (scopeSelection === 'global') return r.scope === 'global' || r.scope === 'emea';
    if (scopeSelection === 'nigeria') return r.scope === 'nigeria';
    return r.scope === 'emea' || r.scope === 'global';
  });

  return (
    <section id="provenance" className="py-16 bg-[var(--bg)] border-b border-[var(--border)]">
      <div className="page-shell">
        <div className="text-center max-w-[680px] mx-auto mb-12">
          <div className="inline-flex items-center gap-2 px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] text-xs font-mono text-[var(--ink-muted)] mb-3">
            architectural principles · adr-0001..0021
          </div>
          <h2 className="font-semibold text-2xl sm:text-3xl tracking-tight text-[var(--ink)] text-balance">
            Engineered for signal density and zero hallucination.
          </h2>
          <p className="text-sm text-[var(--ink-muted)] mt-2">
            Every layer of Bottom Pot is designed for software professionals who demand auditable source evidence and extreme ergonomic speed.
          </p>
        </div>

        {/* 2x2 Bento Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-px bg-[var(--border)] border border-[var(--border)]">
          {/* Bento Cell 1: 7-Tier Provenance Ladder */}
          <div className="bg-[var(--surface)]">
            <ProvenanceLadderInteractive />
          </div>

          {/* Bento Cell 2: Concurrent SSE & SQLite Caching */}
          <div className="bg-[var(--surface)] p-6 sm:p-8 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Database className="w-4 h-4 text-[var(--accent)]" />
                  <h4 className="font-semibold text-sm text-[var(--ink)]">
                    Real-time SSE orchestration &amp; budget defense
                  </h4>
                </div>
                <div className="flex border border-[var(--border)] bg-[var(--surface)]">
                  <button
                    type="button"
                    onClick={() => setCacheMode('hit')}
                    className={`px-2 py-0.5 text-xs font-mono transition-colors cursor-pointer ${
                      cacheMode === 'hit'
                        ? 'bg-[var(--surface-selected)] text-[var(--ink)] font-semibold'
                        : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                    }`}
                  >
                    cache: hit
                  </button>
                  <button
                    type="button"
                    onClick={() => setCacheMode('live')}
                    className={`px-2 py-0.5 text-xs font-mono border-l border-[var(--border)] transition-colors cursor-pointer ${
                      cacheMode === 'live'
                        ? 'bg-[var(--surface-selected)] text-[var(--ink)] font-semibold'
                        : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                    }`}
                  >
                    cache: live
                  </button>
                </div>
              </div>

              <p className="text-xs text-[var(--ink-muted)] leading-relaxed mb-4">
                Instead of blocking on a monolithic 20-second scrape, Bottom Pot streams each ATS platform over Server-Sent Events the millisecond it resolves&mdash;backed by a two-tier SQLite cache and 50/day credit circuit breaker.
              </p>

              {/* Interactive Diagnostic Card */}
              <div className="border border-[var(--border)] bg-[var(--surface-subtle)] p-4 text-xs font-mono space-y-2.5">
                <div className="flex items-center justify-between border-b border-[var(--border)] pb-2">
                  <span className="text-[var(--ink-subtle)]">query_hash:</span>
                  <span className="font-semibold text-[var(--ink)]">sha256:d8a209b4...</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--ink-subtle)]">two_tier_cache:</span>
                  <span className={cacheMode === 'hit' ? 'text-emerald-700 dark:text-emerald-400 font-semibold' : 'text-amber-700 dark:text-amber-400 font-semibold'}>
                    {cacheMode === 'hit' ? 'HIT (data/cache.sqlite · TTL 12h)' : 'MISS (Dispatching live Serper calls)'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--ink-subtle)]">serper_credits_consumed:</span>
                  <span className="font-semibold text-[var(--ink)]">
                    {cacheMode === 'hit' ? '0 credits' : '4 credits (budget: 196 remaining)'}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-[var(--ink-subtle)]">deduplicated_urls:</span>
                  <span className="font-semibold text-[var(--ink)]">38 URLs filtered</span>
                </div>

                {/* Per-Platform Latency Meter */}
                <div className="pt-2 border-t border-[var(--border)] space-y-1.5">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="text-[var(--ink-muted)]">ashby (api_graphql):</span>
                    <span className="text-[var(--ink)]">114ms</span>
                  </div>
                  <div className="w-full h-1 bg-[var(--border)] overflow-hidden">
                    <div className="h-full bg-[var(--accent)]" style={{ width: '25%' }} />
                  </div>
                  <div className="flex items-center justify-between text-[11px] pt-1">
                    <span className="text-[var(--ink-muted)]">greenhouse (jsonld):</span>
                    <span className="text-[var(--ink)]">240ms</span>
                  </div>
                  <div className="w-full h-1 bg-[var(--border)] overflow-hidden">
                    <div className="h-full bg-[var(--accent)]" style={{ width: '52%' }} />
                  </div>
                </div>
              </div>
            </div>
          </div>

          {/* Bento Cell 3: Nigerian Tech & Global Remote Ecosystem */}
          <div className="bg-[var(--surface)] p-6 sm:p-8 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Globe className="w-4 h-4 text-[var(--accent)]" />
                  <h4 className="font-semibold text-sm text-[var(--ink)]">
                    Engineered for global remote &amp; Nigerian tech talent
                  </h4>
                </div>
              </div>

              <p className="text-xs text-[var(--ink-muted)] leading-relaxed mb-4">
                Filter effortlessly between worldwide remote roles, EMEA timezones, and verified engineering &amp; product openings across Lagos, Abuja, and international companies hiring in Nigeria.
              </p>

              {/* Location Scope Switcher */}
              <div className="flex border border-[var(--border)] bg-[var(--surface)] mb-3">
                <button
                  type="button"
                  onClick={() => setScopeSelection('global')}
                  className={`flex-1 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                    scopeSelection === 'global'
                      ? 'bg-[var(--surface-selected)] text-[var(--ink)]'
                      : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                  }`}
                >
                  Global Remote
                </button>
                <button
                  type="button"
                  onClick={() => setScopeSelection('nigeria')}
                  className={`flex-1 py-1.5 text-xs font-medium border-l border-[var(--border)] transition-colors cursor-pointer ${
                    scopeSelection === 'nigeria'
                      ? 'bg-[var(--surface-selected)] text-[var(--ink)]'
                      : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                  }`}
                >
                  Nigeria (Lagos / Abuja)
                </button>
                <button
                  type="button"
                  onClick={() => setScopeSelection('emea')}
                  className={`flex-1 py-1.5 text-xs font-medium border-l border-[var(--border)] transition-colors cursor-pointer ${
                    scopeSelection === 'emea'
                      ? 'bg-[var(--surface-selected)] text-[var(--ink)]'
                      : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                  }`}
                >
                  EMEA Friendly
                </button>
              </div>

              {/* Mini Table */}
              <div className="border border-[var(--border)] divide-y divide-[var(--border)] text-xs">
                {filteredEcosystem.map((row) => (
                  <div key={row.company} className="p-2.5 flex items-center justify-between bg-[var(--surface-subtle)]">
                    <div className="flex items-center gap-2.5">
                      <span className="w-6 h-6 bg-[var(--surface-raised)] border border-[var(--border)] flex items-center justify-center font-mono text-[10px] font-bold text-[var(--ink)]">
                        {row.mono}
                      </span>
                      <div>
                        <div className="font-semibold text-[var(--ink)]">{row.company}</div>
                        <div className="text-[11px] text-[var(--ink-muted)]">{row.role}</div>
                      </div>
                    </div>
                    <span className="text-[11px] font-mono text-[var(--ink-muted)] text-right">
                      {row.location}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Bento Cell 4: Keyboard-First Ergonomics & Visited Memory */}
          <div className="bg-[var(--surface)] p-6 sm:p-8 flex flex-col justify-between">
            <div>
              <div className="flex items-center justify-between mb-4">
                <div className="flex items-center gap-2">
                  <Cpu className="w-4 h-4 text-[var(--accent)]" />
                  <h4 className="font-semibold text-sm text-[var(--ink)]">
                    Built for high-velocity daily triage
                  </h4>
                </div>
                <span className="font-mono text-xs text-[var(--ink-muted)]">j / k / o / ⌘K</span>
              </div>

              <p className="text-xs text-[var(--ink-muted)] leading-relaxed mb-4">
                Navigate hundreds of postings without touching your mouse. Traverse rows with j/k, inspect provenance with Enter, open the original ATS application with o, and rely on automatic visited-row dimming so you never read the same posting twice.
              </p>

              {/* Interactive Keyboard Controls Deck */}
              <div className="flex flex-wrap items-center gap-2 mb-3">
                <button
                  type="button"
                  onClick={() => handleRowNav('up')}
                  className="px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] font-mono text-xs cursor-pointer text-[var(--ink)]"
                >
                  j (up)
                </button>
                <button
                  type="button"
                  onClick={() => handleRowNav('down')}
                  className="px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] font-mono text-xs cursor-pointer text-[var(--ink)]"
                >
                  k (down)
                </button>
                <button
                  type="button"
                  onClick={() => handleToggleVisited(activeRow)}
                  className="px-2.5 py-1 border border-[var(--border)] bg-[var(--surface)] hover:bg-[var(--surface-hover)] font-mono text-xs cursor-pointer text-[var(--ink)] flex items-center gap-1"
                >
                  <Eye className="w-3 h-3" />
                  <span>toggle visited</span>
                </button>
              </div>

              {/* Interactive 3-row mini list with 2px green bar and visited dimming */}
              <div className="border border-[var(--border)] divide-y divide-[var(--border)] text-xs">
                {sampleTriageRows.map((row) => {
                  const isActive = row.id === activeRow;
                  const isVisited = visitedSet.has(row.id);

                  return (
                    <div
                      key={row.id}
                      onClick={() => setActiveRow(row.id)}
                      className={`p-3 flex items-center justify-between cursor-pointer transition-colors ${
                        isActive
                          ? 'bg-[var(--surface-subtle)] shadow-[inset_2px_0_0_0_var(--accent)]'
                          : 'bg-[var(--surface)] hover:bg-[var(--surface-hover)]'
                      }`}
                    >
                      <div className="flex items-center gap-2">
                        <span className={`text-xs ${isVisited ? 'text-[var(--ink-muted)] font-normal' : 'text-[var(--ink)] font-semibold'}`}>
                          {row.company}
                        </span>
                        <span className="text-[var(--ink-muted)]">&mdash;</span>
                        <span className={`text-xs ${isVisited ? 'text-[var(--ink-muted)] line-through' : 'text-[var(--ink)]'}`}>
                          {row.title}
                        </span>
                      </div>
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] text-[var(--ink-muted)]">{row.model}</span>
                        {isVisited && (
                          <span className="text-[10px] font-mono text-[var(--ink-muted)] border border-[var(--border)] px-1">
                            read
                          </span>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
