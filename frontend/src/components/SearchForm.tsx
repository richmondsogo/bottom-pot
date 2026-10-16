import React from 'react';
import type { SearchParams } from '../types';

export const ROLE_SUGGESTIONS = [
  'Backend Engineer',
  'Full-Stack Developer',
  'Python / FastAPI',
  'Frontend React',
  'DevOps / Cloud',
  'Product Designer',
];

export const LOCATION_SUGGESTIONS = ['Nigeria', 'Lagos', 'Remote', 'London'];

interface SearchFormProps {
  searchParams: SearchParams;
  setSearchParams: React.Dispatch<React.SetStateAction<SearchParams>>;
  onSubmit: (e: React.FormEvent) => void;
}

export const SearchForm: React.FC<SearchFormProps> = ({
  searchParams,
  setSearchParams,
  onSubmit,
}) => {
  return (
    <form id="queryForm" onSubmit={onSubmit} className="search-form">
      <label className="field field-wide">
        <span className="label">Role or keyword <b>*</b></span>
        <input
          id="keywords"
          name="keywords"
          type="text"
          required
          minLength={2}
          maxLength={100}
          placeholder="e.g. Backend Software Engineer"
          autoComplete="off"
          value={searchParams.keywords}
          onChange={(e) => setSearchParams({ ...searchParams, keywords: e.target.value })}
        />
      </label>

      {/* 1-Click Role Suggestions */}
      <div className="chips-row">
        <span className="chips-label label">Quick search:</span>
        <div className="chips-wrap">
          {ROLE_SUGGESTIONS.map((role) => (
            <button
              key={role}
              type="button"
              className={`chip ${searchParams.keywords === role ? 'active' : ''}`}
              aria-pressed={searchParams.keywords === role}
              onClick={() => setSearchParams({ ...searchParams, keywords: role })}
            >
              {role}
            </button>
          ))}
        </div>
      </div>

      <div className="field-grid">
        <label className="field">
          <span className="label">Location</span>
          <input
            id="location"
            name="location"
            type="text"
            maxLength={100}
            placeholder="Anywhere"
            value={searchParams.location}
            onChange={(e) => setSearchParams({ ...searchParams, location: e.target.value })}
          />
        </label>

        <label className="field">
          <span className="label">Work model</span>
          <select
            id="workModel"
            name="workModel"
            value={searchParams.workModel}
            onChange={(e) => setSearchParams({ ...searchParams, workModel: e.target.value })}
          >
            <option value="any">Any model</option>
            <option value="remote">Remote only</option>
            <option value="onsite">Exclude remote</option>
          </select>
        </label>

        <label className="field">
          <span className="label">Posted within</span>
          <select
            id="postAge"
            name="postAge"
            value={searchParams.postAge}
            onChange={(e) => setSearchParams({ ...searchParams, postAge: e.target.value })}
          >
            <option value="3">3 days</option>
            <option value="7">7 days</option>
            <option value="14">14 days</option>
            <option value="30">30 days</option>
            <option value="90">90 days</option>
          </select>
        </label>
      </div>

      {/* Location Suggestions */}
      <div className="chips-row">
        <span className="chips-label label">Popular:</span>
        <div className="chips-wrap">
          {LOCATION_SUGGESTIONS.map((loc) => (
            <button
              key={loc}
              type="button"
              className={`chip ${searchParams.location === loc ? 'active' : ''}`}
              aria-pressed={searchParams.location === loc}
              onClick={() => setSearchParams({ ...searchParams, location: loc })}
            >
              {loc}
            </button>
          ))}
        </div>
      </div>

      <div className="checkboxes-wrap">
        <label className="check-field">
          <input
            id="includeNigerian"
            type="checkbox"
            checked={searchParams.includeNigerian}
            onChange={(e) =>
              setSearchParams({ ...searchParams, includeNigerian: e.target.checked })
            }
          />
          <span>Include Nigerian job boards</span>
        </label>

        <label className="check-field">
          <input
            id="deepScrape"
            type="checkbox"
            checked={searchParams.deepScrape}
            onChange={(e) =>
              setSearchParams({ ...searchParams, deepScrape: e.target.checked })
            }
          />
          <span>Deep scrape matched job pages</span>
        </label>
      </div>

      <button className="btn btn-primary submit-btn" type="submit">
        <span>Search ATS platforms</span>
        <span aria-hidden="true">→</span>
      </button>
    </form>
  );
};
