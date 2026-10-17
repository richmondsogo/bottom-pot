import React, { useState } from 'react';
import type { SearchParams } from '../types';
import { ALL_PLATFORMS, ROLE_SUGGESTIONS } from '../lib/constants';
import { ChevronDown, ChevronUp, Search, SlidersHorizontal, CheckSquare, Square } from 'lucide-react';

interface SearchFormProps {
  searchParams: SearchParams;
  setSearchParams: React.Dispatch<React.SetStateAction<SearchParams>>;
  onSubmit: (e: React.FormEvent) => void;
  selectedPlatforms: string[];
  setSelectedPlatforms: (platforms: string[]) => void;
}

export const SearchForm: React.FC<SearchFormProps> = ({
  searchParams,
  setSearchParams,
  onSubmit,
  selectedPlatforms,
  setSelectedPlatforms,
}) => {
  const [showMoreFilters, setShowMoreFilters] = useState(false);
  const [platformQuery, setPlatformQuery] = useState('');

  const filteredPlatforms = ALL_PLATFORMS.filter((p) =>
    p.name.toLowerCase().includes(platformQuery.toLowerCase())
  );

  const togglePlatform = (id: string) => {
    if (selectedPlatforms.includes(id)) {
      setSelectedPlatforms(selectedPlatforms.filter((p) => p !== id));
    } else {
      setSelectedPlatforms([...selectedPlatforms, id]);
    }
  };

  const selectAllPlatforms = () => {
    setSelectedPlatforms(ALL_PLATFORMS.map((p) => p.id));
  };

  const selectNonePlatforms = () => {
    setSelectedPlatforms([]);
  };

  return (
    <div style={{ maxWidth: '780px', margin: '0 auto', width: '100%' }}>
      {/* Editorial Hero: No vague gradient blob */}
      <div style={{ textAlign: 'center', marginBottom: 'var(--space-8)', paddingTop: 'var(--space-6)' }}>
        <h1
          style={{
            fontSize: 'var(--text-display)',
            fontWeight: 800,
            letterSpacing: '-0.035em',
            lineHeight: 1.08,
            marginBottom: 'var(--space-3)',
          }}
        >
          Find the signal behind the noise.
        </h1>
        <p
          style={{
            fontSize: 'var(--text-body)',
            color: 'var(--ink-muted)',
            lineHeight: 1.6,
            maxWidth: '560px',
            margin: '0 auto',
          }}
        >
          Search public applicant-tracking systems directly for fresh software and engineering postings.
          No aggregators, no ghost jobs.
        </p>
      </div>

      {/* Main Search Form Card: Hairline borders, flat clean canvas */}
      <div
        style={{
          background: 'var(--surface)',
          border: '1px solid var(--border-strong)',
          padding: 'var(--space-6)',
          boxShadow: '0 4px 20px rgba(24, 24, 22, 0.04)',
          marginBottom: 'var(--space-12)',
        }}
      >
        <form onSubmit={onSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-4)' }}>
          {/* Primary Field 1: Role or Keywords */}
          <div>
            <label
              htmlFor="keywords-input"
              style={{
                display: 'block',
                fontFamily: 'var(--font-mono)',
                fontSize: 'var(--text-xs)',
                fontWeight: 600,
                color: 'var(--ink-muted)',
                marginBottom: 'var(--space-1)',
                textTransform: 'uppercase',
                letterSpacing: '0.08em',
              }}
            >
              Role or keyword <span style={{ color: 'var(--accent)' }}>*</span>
            </label>
            <div style={{ position: 'relative' }}>
              <input
                id="keywords-input"
                name="keywords"
                type="text"
                required
                minLength={2}
                maxLength={100}
                className="control-input"
                placeholder="e.g. Backend Software Engineer, Python, Distributed Systems"
                autoComplete="off"
                value={searchParams.keywords}
                onChange={(e) => setSearchParams({ ...searchParams, keywords: e.target.value })}
              />
            </div>

            {/* Quick role suggestion chips */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', marginTop: 'var(--space-2)', flexWrap: 'wrap' }}>
              <span className="mono" style={{ fontSize: '11px', color: 'var(--ink-subtle)' }}>
                Suggestions:
              </span>
              {ROLE_SUGGESTIONS.map((role) => (
                <button
                  key={role}
                  type="button"
                  className={`chip ${searchParams.keywords === role ? 'active' : ''}`}
                  onClick={() => setSearchParams({ ...searchParams, keywords: role })}
                  aria-pressed={searchParams.keywords === role}
                >
                  {role}
                </button>
              ))}
            </div>
          </div>

          {/* Primary Fields 2 & 3: Location and Work Model in 2-col grid */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))', gap: 'var(--space-4)' }}>
            <div>
              <label
                htmlFor="location-input"
                style={{
                  display: 'block',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  color: 'var(--ink-muted)',
                  marginBottom: 'var(--space-1)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                }}
              >
                Location or Country
              </label>
              <input
                id="location-input"
                name="location"
                type="text"
                className="control-input"
                placeholder="e.g. Nigeria, Lagos, Remote, United Kingdom"
                value={searchParams.location}
                onChange={(e) => setSearchParams({ ...searchParams, location: e.target.value })}
              />
            </div>

            <div>
              <label
                htmlFor="work-model-select"
                style={{
                  display: 'block',
                  fontFamily: 'var(--font-mono)',
                  fontSize: 'var(--text-xs)',
                  fontWeight: 600,
                  color: 'var(--ink-muted)',
                  marginBottom: 'var(--space-1)',
                  textTransform: 'uppercase',
                  letterSpacing: '0.08em',
                }}
              >
                Work Model
              </label>
              <select
                id="work-model-select"
                name="workModel"
                className="control-select"
                value={searchParams.workModel}
                onChange={(e) => setSearchParams({ ...searchParams, workModel: e.target.value })}
              >
                <option value="any">Any work model</option>
                <option value="remote">Remote only</option>
                <option value="onsite">Exclude remote (In-person / Hybrid)</option>
              </select>
            </div>
          </div>

          {/* "More filters" toggle button */}
          <div style={{ paddingTop: 'var(--space-1)' }}>
            <button
              type="button"
              className="btn btn-sm"
              onClick={() => setShowMoreFilters(!showMoreFilters)}
              style={{ display: 'inline-flex', alignItems: 'center', gap: 'var(--space-2)' }}
              aria-expanded={showMoreFilters}
            >
              <SlidersHorizontal size={13} aria-hidden="true" />
              <span>{showMoreFilters ? 'Hide extra filters' : 'More filters (Platform, Recency, Nigerian boards)'}</span>
              {showMoreFilters ? <ChevronUp size={13} /> : <ChevronDown size={13} />}
            </button>
          </div>

          {/* Collapsible "More filters" section */}
          {showMoreFilters && (
            <div
              style={{
                display: 'flex',
                flexDirection: 'column',
                gap: 'var(--space-4)',
                padding: 'var(--space-4)',
                background: 'var(--surface-subtle)',
                border: '1px solid var(--border)',
              }}
            >
              {/* Recency selector */}
              <div>
                <label
                  htmlFor="post-age-select"
                  style={{
                    display: 'block',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 'var(--text-xs)',
                    fontWeight: 600,
                    color: 'var(--ink-muted)',
                    marginBottom: 'var(--space-1)',
                    textTransform: 'uppercase',
                    letterSpacing: '0.08em',
                  }}
                >
                  Posted within
                </label>
                <select
                  id="post-age-select"
                  name="postAge"
                  className="control-select"
                  style={{ maxWidth: '240px' }}
                  value={searchParams.postAge}
                  onChange={(e) => setSearchParams({ ...searchParams, postAge: e.target.value })}
                >
                  <option value="3">Past 3 days</option>
                  <option value="7">Past 7 days</option>
                  <option value="14">Past 14 days</option>
                  <option value="30">Past 30 days</option>
                  <option value="90">Past 90 days</option>
                </select>
              </div>

              {/* Platform Picker */}
              <div>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 'var(--space-2)' }}>
                  <span
                    className="mono"
                    style={{ fontSize: 'var(--text-xs)', fontWeight: 600, textTransform: 'uppercase', color: 'var(--ink-muted)' }}
                  >
                    Target ATS Platforms ({selectedPlatforms.length} of {ALL_PLATFORMS.length} selected)
                  </span>

                  <div style={{ display: 'flex', gap: 'var(--space-2)' }}>
                    <button type="button" className="btn-text" onClick={selectAllPlatforms} style={{ fontSize: '11px' }}>
                      Select all
                    </button>
                    <span style={{ color: 'var(--border-strong)' }}>|</span>
                    <button type="button" className="btn-text" onClick={selectNonePlatforms} style={{ fontSize: '11px' }}>
                      Select none
                    </button>
                  </div>
                </div>

                {/* Filter platform chips input */}
                <input
                  type="text"
                  className="control-input"
                  style={{ height: '32px', fontSize: '12px', marginBottom: 'var(--space-2)' }}
                  placeholder="Filter platform names..."
                  value={platformQuery}
                  onChange={(e) => setPlatformQuery(e.target.value)}
                />

                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--space-1)', maxHeight: '160px', overflowY: 'auto' }}>
                  {filteredPlatforms.map((platform) => {
                    const isSelected = selectedPlatforms.includes(platform.id);
                    return (
                      <button
                        key={platform.id}
                        type="button"
                        className={`chip ${isSelected ? 'active' : ''}`}
                        onClick={() => togglePlatform(platform.id)}
                        aria-pressed={isSelected}
                      >
                        {isSelected ? <CheckSquare size={11} /> : <Square size={11} />}
                        <span>{platform.name}</span>
                      </button>
                    );
                  })}
                </div>
              </div>

              {/* Checkboxes: Nigerian Job Boards & Deep Scrape */}
              <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)', paddingTop: 'var(--space-2)', borderTop: '1px solid var(--border)' }}>
                <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', cursor: 'pointer', fontSize: 'var(--text-ui)' }}>
                  <input
                    type="checkbox"
                    checked={searchParams.includeNigerian}
                    onChange={(e) => setSearchParams({ ...searchParams, includeNigerian: e.target.checked })}
                    style={{ width: '16px', height: '16px', accentColor: 'var(--accent)' }}
                  />
                  <span>Include Nigerian technology job sources (Jobberman, MyJobMag)</span>
                </label>

                <label style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-2)', cursor: 'pointer', fontSize: 'var(--text-ui)' }}>
                  <input
                    type="checkbox"
                    checked={searchParams.deepScrape}
                    onChange={(e) => setSearchParams({ ...searchParams, deepScrape: e.target.checked })}
                    style={{ width: '16px', height: '16px', accentColor: 'var(--accent)' }}
                  />
                  <span>Perform deep scrape extraction on candidate job pages</span>
                </label>
              </div>
            </div>
          )}

          {/* Primary Action Button */}
          <div style={{ paddingTop: 'var(--space-2)' }}>
            <button
              type="submit"
              className="btn btn-primary"
              style={{ width: '100%', height: '46px', fontSize: 'var(--text-body)' }}
            >
              <Search size={16} aria-hidden="true" />
              <span>Search ATS platforms</span>
              <span aria-hidden="true" style={{ marginLeft: '4px' }}>→</span>
            </button>
          </div>
        </form>
      </div>

      {/* "How it works" 3-step section separated by hairlines */}
      <div
        style={{
          borderTop: '1px solid var(--border)',
          borderBottom: '1px solid var(--border)',
          padding: 'var(--space-8) 0',
          marginBottom: 'var(--space-8)',
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 'var(--space-6)' }}>
          <span
            className="mono"
            style={{
              fontSize: 'var(--text-xs)',
              fontWeight: 600,
              textTransform: 'uppercase',
              color: 'var(--ink-muted)',
              letterSpacing: '0.08em',
            }}
          >
            How Bottom Pot Works
          </span>
        </div>

        <div
          style={{
            display: 'grid',
            gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))',
            gap: 'var(--space-6)',
          }}
        >
          {/* Step 1 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <div
              className="mono"
              style={{
                fontSize: '12px',
                fontWeight: 700,
                color: 'var(--accent)',
              }}
            >
              01 / DEFINE QUERY
            </div>
            <div style={{ fontSize: 'var(--text-body)', fontWeight: 700, color: 'var(--ink)' }}>
              Target Role & Location
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-muted)', lineHeight: 1.55 }}>
              Specify your engineering title, experience level, remote requirement, and posting freshness window.
            </div>
          </div>

          {/* Step 2 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <div
              className="mono"
              style={{
                fontSize: '12px',
                fontWeight: 700,
                color: 'var(--accent)',
              }}
            >
              02 / DIRECT ATS DORKING
            </div>
            <div style={{ fontSize: 'var(--text-body)', fontWeight: 700, color: 'var(--ink)' }}>
              Bypass Job Aggregators
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-muted)', lineHeight: 1.55 }}>
              We query verified company job boards on Greenhouse, Lever, Ashby, Workable, and 14+ other ATS hosts.
            </div>
          </div>

          {/* Step 3 */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--space-2)' }}>
            <div
              className="mono"
              style={{
                fontSize: '12px',
                fontWeight: 700,
                color: 'var(--accent)',
              }}
            >
              03 / CLEAN SIGNAL
            </div>
            <div style={{ fontSize: 'var(--text-body)', fontWeight: 700, color: 'var(--ink)' }}>
              Verified Direct Apply Links
            </div>
            <div style={{ fontSize: 'var(--text-sm)', color: 'var(--ink-muted)', lineHeight: 1.55 }}>
              Structured salary ranges, accurate work models, normalized metadata, and direct link to the employer.
            </div>
          </div>
        </div>
      </div>

      {/* Quiet text row of supported platforms */}
      <div style={{ textAlign: 'center', color: 'var(--ink-subtle)', fontSize: 'var(--text-xs)' }}>
        <span className="mono">
          Supported platforms: Greenhouse · Lever · Ashby · Workable · SmartRecruiters · Jobvite · BambooHR · Recruitee · Workday · Taleo · Polywork · Breezy · Rippling · Personio · Jobberman · MyJobMag
        </span>
      </div>
    </div>
  );
};
