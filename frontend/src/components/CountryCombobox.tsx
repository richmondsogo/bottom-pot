import React, { useMemo, useState } from 'react';
import { Check, ChevronDown, Globe, Search } from 'lucide-react';
import {
  COUNTRIES,
  PRIORITY_COUNTRY_CODES,
  getCountryByCode,
  normalizeCountryCode,
  type CountryEntry,
} from '../lib/countries';
import { Input } from './ui/input';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';

interface CountryComboboxProps {
  value: string;
  onChange: (code: string) => void;
  compact?: boolean;
  align?: 'start' | 'end';
  idPrefix?: string;
  placeholder?: string;
  className?: string;
}

const PRIORITY_SET = new Set(PRIORITY_COUNTRY_CODES);

export const CountryCombobox: React.FC<CountryComboboxProps> = ({
  value,
  onChange,
  compact = false,
  align = 'start',
  idPrefix = 'applicant-country',
  placeholder = 'Any country (not set)',
  className = '',
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const selectedEntry = useMemo(() => (value ? getCountryByCode(value) : null), [value]);

  const { priorityCountries, otherCountries } = useMemo(() => {
    const q = query.trim().toLowerCase();
    const aliasCode = q ? normalizeCountryCode(q) : null;

    const matchesQuery = (country: CountryEntry): boolean => {
      if (!q) return true;
      if (aliasCode && country.code === aliasCode) return true;
      return (
        country.name.toLowerCase().includes(q) ||
        country.code.toLowerCase().includes(q) ||
        country.region.toLowerCase().includes(q)
      );
    };

    const byCode = new Map(COUNTRIES.map((c) => [c.code, c]));
    const priorityList: CountryEntry[] = [];
    for (const code of PRIORITY_COUNTRY_CODES) {
      const entry = byCode.get(code);
      if (entry && matchesQuery(entry)) {
        priorityList.push(entry);
      }
    }

    const restList = COUNTRIES.filter(
      (country) => !PRIORITY_SET.has(country.code) && matchesQuery(country)
    );

    return { priorityCountries: priorityList, otherCountries: restList };
  }, [query]);

  const handleSelect = (nextCode: string) => {
    onChange(nextCode);
    setOpen(false);
    setQuery('');
  };

  const triggerDisplay = selectedEntry
    ? compact
      ? `Work from: ${selectedEntry.name}`
      : `${selectedEntry.name} (${selectedEntry.code})`
    : compact
      ? 'Where can you work from?'
      : placeholder;

  return (
    <div className={`relative ${className}`}>
      <Popover
        open={open}
        onOpenChange={(nextOpen) => {
          setOpen(nextOpen);
          if (!nextOpen) setQuery('');
        }}
      >
        <PopoverTrigger
          id={`${idPrefix}-trigger`}
          type="button"
          role="combobox"
          aria-expanded={open}
          aria-controls={`${idPrefix}-listbox`}
          aria-label={`Choose applicant country (${selectedEntry ? selectedEntry.name : 'not set'})`}
          className={`flex items-center justify-between gap-2 border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--ink)] hover:bg-[var(--surface-hover)] focus-visible:outline-none focus-visible:border-[var(--accent)] transition-colors cursor-pointer select-none shadow-none ${
            compact ? 'h-9 w-full sm:w-auto sm:min-w-[205px]' : 'h-10 sm:h-9 w-full'
          }`}
          style={{ borderRadius: 0 }}
        >
          <span className="flex items-center gap-2 min-w-0">
            <Globe className="size-3.5 text-[var(--ink-subtle)] shrink-0" aria-hidden="true" />
            <span
              className={`truncate ${
                selectedEntry ? 'text-[var(--ink)] font-medium' : 'text-[var(--ink-muted)]'
              }`}
            >
              {triggerDisplay}
            </span>
          </span>
          <ChevronDown className="size-3.5 text-[var(--ink-subtle)] shrink-0" aria-hidden="true" />
        </PopoverTrigger>

        <PopoverContent
          align={align}
          side="bottom"
          sideOffset={4}
          className="min-w-(--anchor-width) w-[min(20rem,calc(100vw-2rem))] p-0 bg-[var(--surface)] border border-[var(--border)] shadow-sm"
          style={{ borderRadius: 0 }}
        >
          <div className="p-2 border-b border-[var(--border-subtle)] bg-[var(--surface)]">
            <div className="relative flex items-center">
              <Search
                className="absolute left-3 size-3.5 text-[var(--ink-subtle)] pointer-events-none"
                aria-hidden="true"
              />
              <Input
                id={`${idPrefix}-search`}
                type="text"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="Search country, ISO code, or region..."
                aria-label="Search country"
                className="h-9 !pl-9 pr-3 text-sm bg-[var(--bg)] border-[var(--border)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] rounded-none shadow-none focus-visible:border-[var(--accent)] focus-visible:ring-0"
                style={{ borderRadius: 0 }}
                autoFocus
              />
            </div>
          </div>

          <div
            id={`${idPrefix}-listbox`}
            role="listbox"
            aria-label="Selectable countries"
            className="max-h-64 overflow-y-auto divide-y divide-[var(--border-subtle)]"
          >
            <button
              type="button"
              role="option"
              aria-selected={!value}
              onClick={() => handleSelect('')}
              className={`w-full h-9 px-3 flex items-center justify-between text-left text-xs transition-colors cursor-pointer select-none ${
                !value
                  ? 'bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                  : 'bg-[var(--surface)] text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]'
              }`}
              style={{ borderRadius: 0 }}
            >
              <span className="truncate">Any country (not set)</span>
              {!value && <Check className="size-3.5 text-[var(--ink)] shrink-0" aria-hidden="true" />}
            </button>

            {priorityCountries.length > 0 && (
              <div>
                <div className="px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-[var(--ink-subtle)] bg-[var(--bg)] border-b border-[var(--border-subtle)]">
                  Common markets
                </div>
                {priorityCountries.map((country) => {
                  const isSelected = value === country.code;
                  return (
                    <button
                      key={`priority-${country.code}`}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => handleSelect(country.code)}
                      className={`w-full h-9 px-3 flex items-center justify-between text-left text-sm transition-colors cursor-pointer select-none ${
                        isSelected
                          ? 'bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                          : 'bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)]'
                      }`}
                      style={{ borderRadius: 0 }}
                    >
                      <span className="truncate">
                        {country.name}{' '}
                        <span className="font-mono text-xs text-[var(--ink-subtle)]">
                          {country.code}
                        </span>
                      </span>
                      {isSelected && (
                        <Check className="size-3.5 text-[var(--ink)] shrink-0 ml-2" aria-hidden="true" />
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {otherCountries.length > 0 && (
              <div>
                <div className="px-3 py-1.5 text-[11px] font-medium uppercase tracking-wider text-[var(--ink-subtle)] bg-[var(--bg)] border-y border-[var(--border-subtle)]">
                  All countries
                </div>
                {otherCountries.map((country) => {
                  const isSelected = value === country.code;
                  return (
                    <button
                      key={country.code}
                      type="button"
                      role="option"
                      aria-selected={isSelected}
                      onClick={() => handleSelect(country.code)}
                      className={`w-full h-9 px-3 flex items-center justify-between text-left text-sm transition-colors cursor-pointer select-none ${
                        isSelected
                          ? 'bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                          : 'bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)]'
                      }`}
                      style={{ borderRadius: 0 }}
                    >
                      <span className="truncate">
                        {country.name}{' '}
                        <span className="font-mono text-xs text-[var(--ink-subtle)]">
                          {country.code}
                        </span>
                      </span>
                      {isSelected && (
                        <Check className="size-3.5 text-[var(--ink)] shrink-0 ml-2" aria-hidden="true" />
                      )}
                    </button>
                  );
                })}
              </div>
            )}

            {priorityCountries.length === 0 && otherCountries.length === 0 && (
              <div className="px-3 py-4 text-xs text-[var(--ink-muted)] text-center">
                No matching countries found.
              </div>
            )}
          </div>
        </PopoverContent>
      </Popover>

      <select
        id={`${idPrefix}-select`}
        name="applicantCountry"
        aria-label="Where can you work from?"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="sr-only"
        tabIndex={-1}
      >
        <option value="">Any country (not set)</option>
        {COUNTRIES.map((country) => (
          <option key={country.code} value={country.code}>
            {country.name} ({country.code})
          </option>
        ))}
      </select>
    </div>
  );
};
