import React, { useMemo, useState } from 'react';
import { Check, ChevronDown, Globe, Search } from 'lucide-react';
import {
  COUNTRIES,
  filterCountries,
  getCountryByCode,
} from '../lib/countries';
import { Input } from './ui/input';
import { Popover, PopoverContent, PopoverTrigger } from './ui/popover';

interface CountryComboboxProps {
  value: string;
  onChange: (code: string) => void;
  compact?: boolean;
  flushMobile?: boolean;
  align?: 'start' | 'end';
  idPrefix?: string;
  placeholder?: string;
  className?: string;
}

export const CountryCombobox: React.FC<CountryComboboxProps> = ({
  value,
  onChange,
  compact = false,
  flushMobile = false,
  align = 'start',
  idPrefix = 'applicant-country',
  placeholder = 'Any country',
  className = '',
}) => {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState('');

  const selectedEntry = useMemo(() => (value ? getCountryByCode(value) : null), [value]);

  const filteredCountries = useMemo(() => filterCountries(query), [query]);

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
  const mobileCompactDisplay = selectedEntry ? selectedEntry.name : 'Country';

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
          className={`flex items-center justify-between gap-2 rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm text-[var(--ink)] hover:bg-[var(--surface-hover)] focus-visible:border-[var(--accent)] focus-visible:ring-2 focus-visible:ring-[var(--accent-border)] transition-[background-color,border-color,box-shadow,transform] duration-140 ease-out active:scale-[0.99] motion-reduce:transform-none cursor-pointer select-none shadow-none ${
            compact
              ? 'h-9 max-md:h-11 w-auto md:min-w-[205px] whitespace-nowrap'
              : `h-10 max-md:h-11 sm:h-9 w-full${
                  flushMobile
                    ? ' max-md:border-0 max-md:bg-transparent max-md:px-0 max-md:rounded-none max-md:hover:bg-transparent max-md:text-[15px] max-md:focus-visible:ring-0 max-md:focus-visible:outline-2 max-md:focus-visible:outline-[var(--accent)] max-md:focus-visible:outline-offset-2'
                    : ''
                }`
          }`}
        >
          <span className={`flex items-center gap-2 min-w-0${flushMobile ? ' max-md:gap-2.5' : ''}`}>
            <Globe
              className={`size-3.5 text-[var(--ink-subtle)] shrink-0${
                flushMobile ? ' max-md:size-4 max-md:text-[var(--ink-muted)]' : ''
              }`}
              aria-hidden="true"
            />
            {compact ? (
              <>
                <span
                  className={`truncate max-md:hidden ${
                    selectedEntry ? 'text-[var(--ink)] font-medium' : 'text-[var(--ink-muted)]'
                  }`}
                >
                  {triggerDisplay}
                </span>
                <span
                  className={`truncate md:hidden ${
                    selectedEntry ? 'text-[var(--ink)] font-medium' : 'text-[var(--ink-muted)]'
                  }`}
                >
                  {mobileCompactDisplay}
                </span>
              </>
            ) : (
              <span
                className={`truncate ${
                  selectedEntry ? 'text-[var(--ink)] font-medium' : 'text-[var(--ink-muted)]'
                }`}
              >
                {triggerDisplay}
              </span>
            )}
          </span>
          <ChevronDown
            className={`size-3.5 text-[var(--ink-subtle)] shrink-0 transition-transform duration-150 ease-out motion-reduce:transition-none ${
              open ? 'rotate-180' : ''
            }`}
            aria-hidden="true"
          />
        </PopoverTrigger>

        <PopoverContent
          align={align}
          side="bottom"
          sideOffset={4}
          className="min-w-(--anchor-width) w-[min(20rem,calc(100vw-2rem))] overflow-hidden p-0 bg-[var(--surface)] border border-[var(--border)] shadow-sm"
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
                placeholder="Search for a country…"
                aria-label="Search countries"
                className="h-9 max-md:h-11 !pl-9 pr-3 text-sm bg-[var(--bg)] border-[var(--border)] text-[var(--ink)] placeholder:text-[var(--ink-subtle)] shadow-none focus-visible:border-[var(--accent)]"
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
              className={`w-full h-9 max-md:h-11 px-3 rounded-none flex items-center justify-between text-left text-xs transition-colors cursor-pointer select-none ${
                !value
                  ? 'bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                  : 'bg-[var(--surface)] text-[var(--ink-muted)] hover:bg-[var(--surface-hover)] hover:text-[var(--ink)]'
              }`}
            >
              <span className="truncate">Any country</span>
              {!value && <Check className="size-3.5 text-[var(--ink)] shrink-0" aria-hidden="true" />}
            </button>

            {filteredCountries.map((country) => {
              const isSelected = value === country.code;
              return (
                <button
                  key={country.code}
                  type="button"
                  role="option"
                  aria-selected={isSelected}
                  onClick={() => handleSelect(country.code)}
                  className={`w-full h-9 max-md:h-11 px-3 rounded-none flex items-center justify-between text-left text-sm transition-colors cursor-pointer select-none ${
                    isSelected
                      ? 'bg-[var(--surface-subtle)] text-[var(--ink)] font-medium'
                      : 'bg-[var(--surface)] text-[var(--ink)] hover:bg-[var(--surface-hover)]'
                  }`}
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

            {filteredCountries.length === 0 && (
              <div className="px-3 py-4 text-xs text-[var(--ink-muted)] text-center">
                No countries found.
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
        <option value="">Any country</option>
        {COUNTRIES.map((country) => (
          <option key={country.code} value={country.code}>
            {country.name} ({country.code})
          </option>
        ))}
      </select>
    </div>
  );
};
