import React, { useState } from 'react';
import { ExternalLink } from 'lucide-react';

interface SampleJob {
  id: string;
  role: string;
  company: string;
  location: string;
  workModel: 'Remote' | 'Hybrid' | null;
  platform: string;
  salary: string | null;
  posted: string;
  applyUrl: string;
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
    applyUrl: 'https://linear.app/careers',
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
    applyUrl: 'https://paystack.com/careers',
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
    applyUrl: 'https://supabase.com/careers',
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
    applyUrl: 'https://raycast.com/careers',
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
    applyUrl: 'https://moniepoint.com/careers',
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
    applyUrl: 'https://vercel.com/careers',
    region: 'global',
  },
  {
    id: 'job-7',
    role: 'Lead Mobile Engineer (Flutter)',
    company: 'PiggyVest',
    location: 'Lagos, Nigeria',
    workModel: null, // Untracked workplace type left blank per ADR 0001
    platform: 'bamboohr',
    salary: null,
    posted: '6d ago',
    applyUrl: 'https://piggyvest.com/careers',
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
    applyUrl: 'https://flutterwave.com/careers',
    region: 'nigeria',
  },
];

export const SampleResultsSection: React.FC = () => {
  const [workModelFilter, setWorkModelFilter] = useState<'all' | 'remote' | 'hybrid'>('all');
  const [regionFilter, setRegionFilter] = useState<'all' | 'global' | 'nigeria'>('all');

  const filteredJobs = SAMPLE_JOBS.filter((job) => {
    if (workModelFilter === 'remote' && job.workModel !== 'Remote') return false;
    if (workModelFilter === 'hybrid' && job.workModel !== 'Hybrid') return false;
    if (regionFilter !== 'all' && job.region !== regionFilter) return false;
    return true;
  });

  return (
    <section id="how-it-works" className="py-20 sm:py-28 bg-[var(--bg)] border-b border-[var(--border)]">
      <div className="page-shell">
        {/* Section Intro */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 mb-8">
          <div>
            <div className="inline-flex items-center gap-1.5 px-2 py-0.5 border border-[var(--border)] bg-[var(--surface-subtle)] text-xs font-sans text-[var(--ink-muted)] mb-3 select-none">
              <span className="size-1.5 bg-[var(--accent)]" />
              <span>Sample data</span>
            </div>
            <h2 className="text-2xl sm:text-3xl font-semibold tracking-tight text-[var(--ink)]">
              Here&rsquo;s what a search looks like.
            </h2>
            <p className="text-sm sm:text-base text-[var(--ink-muted)] mt-1.5 max-w-xl font-sans">
              Sample results. Every row links to the company&rsquo;s own listing.
            </p>
          </div>

          {/* Quick Filters */}
          <div className="flex flex-wrap items-center gap-2">
            <div className="inline-flex border border-[var(--border)] p-0.5 bg-[var(--surface)]">
              <button
                type="button"
                onClick={() => setWorkModelFilter('all')}
                className={`px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                  workModelFilter === 'all'
                    ? 'bg-[var(--surface-raised)] text-[var(--ink)]'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                All models
              </button>
              <button
                type="button"
                onClick={() => setWorkModelFilter('remote')}
                className={`px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                  workModelFilter === 'remote'
                    ? 'bg-[var(--surface-raised)] text-[var(--ink)]'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                Remote
              </button>
              <button
                type="button"
                onClick={() => setWorkModelFilter('hybrid')}
                className={`px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                  workModelFilter === 'hybrid'
                    ? 'bg-[var(--surface-raised)] text-[var(--ink)]'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                Hybrid
              </button>
            </div>

            <div className="inline-flex border border-[var(--border)] p-0.5 bg-[var(--surface)]">
              <button
                type="button"
                onClick={() => setRegionFilter('all')}
                className={`px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                  regionFilter === 'all'
                    ? 'bg-[var(--surface-raised)] text-[var(--ink)]'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                All regions
              </button>
              <button
                type="button"
                onClick={() => setRegionFilter('nigeria')}
                className={`px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                  regionFilter === 'nigeria'
                    ? 'bg-[var(--surface-raised)] text-[var(--ink)]'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                Nigeria
              </button>
              <button
                type="button"
                onClick={() => setRegionFilter('global')}
                className={`px-2.5 py-1 text-xs font-medium transition-colors cursor-pointer ${
                  regionFilter === 'global'
                    ? 'bg-[var(--surface-raised)] text-[var(--ink)]'
                    : 'text-[var(--ink-muted)] hover:text-[var(--ink)]'
                }`}
              >
                Global
              </button>
            </div>
          </div>
        </div>

        {/* Semantic Results Table with 0-radius square styling */}
        <div className="border border-[var(--border)] bg-[var(--surface)] overflow-x-auto shadow-none">
          <table className="w-full text-left text-sm border-collapse table-fixed">
            <colgroup>
              <col className="w-[38%] min-w-[240px]" />
              <col className="w-[22%] min-w-[150px]" />
              <col className="w-[16%] min-w-[120px]" />
              <col className="w-[14%] min-w-[110px]" />
              <col className="w-[10%] min-w-[80px]" />
            </colgroup>
            <thead>
              <tr className="border-b border-[var(--border)] bg-[var(--surface-subtle)] text-xs text-[var(--ink-muted)] font-medium">
                <th scope="col" className="py-3.5 px-4 font-medium">Role</th>
                <th scope="col" className="py-3.5 px-4 font-medium">Company</th>
                <th scope="col" className="py-3.5 px-4 font-medium">Location</th>
                <th scope="col" className="py-3.5 px-4 font-medium">Work model</th>
                <th scope="col" className="py-3.5 px-4 font-medium">Posted</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[var(--border-subtle)]">
              {filteredJobs.map((job) => (
                <tr
                  key={job.id}
                  className="hover:bg-[var(--surface-hover)] transition-colors group cursor-pointer"
                >
                  {/* Role Column */}
                  <td className="py-3.5 px-4">
                    <a
                      href={job.applyUrl}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="font-medium text-[var(--ink)] group-hover:text-[var(--accent)] inline-flex items-center gap-1.5 transition-colors line-clamp-1"
                    >
                      <span>{job.role}</span>
                      <ExternalLink className="size-3 opacity-0 group-hover:opacity-100 transition-opacity shrink-0" aria-hidden="true" />
                    </a>
                    {job.salary && (
                      <div className="text-xs text-[var(--ink-muted)] font-mono mt-0.5 tabular-nums">
                        {job.salary}
                      </div>
                    )}
                  </td>

                  {/* Company Column */}
                  <td className="py-3.5 px-4">
                    <div className="flex items-center gap-2">
                      <div className="size-6 bg-[var(--surface-raised)] border border-[var(--border)] font-mono text-[10px] font-semibold text-[var(--ink)] flex items-center justify-center shrink-0 uppercase select-none">
                        {job.company.slice(0, 2)}
                      </div>
                      <div className="min-w-0">
                        <div className="font-medium text-[var(--ink)] truncate text-xs sm:text-sm">
                          {job.company}
                        </div>
                        <div className="text-[11px] text-[var(--ink-subtle)] font-mono lowercase">
                          {job.platform}
                        </div>
                      </div>
                    </div>
                  </td>

                  {/* Location Column */}
                  <td className="py-3.5 px-4 text-xs sm:text-sm text-[var(--ink-muted)] truncate">
                    {job.location}
                  </td>

                  {/* Work Model Column */}
                  <td className="py-3.5 px-4">
                    {job.workModel === 'Remote' ? (
                      <span className="inline-flex items-center gap-1.5 text-xs text-[var(--tag-remote-text)] font-medium">
                        <span className="size-1.5 bg-[var(--tag-remote-marker)] shrink-0" />
                        <span>Remote</span>
                      </span>
                    ) : job.workModel === 'Hybrid' ? (
                      <span className="inline-flex items-center gap-1.5 text-xs text-[var(--tag-hybrid-text)] font-medium">
                        <span className="size-1.5 bg-[var(--tag-hybrid-marker)] shrink-0" />
                        <span>Hybrid</span>
                      </span>
                    ) : (
                      <span className="text-xs text-[var(--ink-subtle)] font-mono">&mdash;</span>
                    )}
                  </td>

                  {/* Posted Column */}
                  <td className="py-3.5 px-4 text-xs font-mono text-[var(--ink-subtle)] tabular-nums">
                    {job.posted}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Table Caption Under Rows */}
        <div className="mt-3 text-xs text-[var(--ink-muted)] text-left font-sans">
          Why Remote? The employer&rsquo;s listing says so.
        </div>
      </div>
    </section>
  );
};
