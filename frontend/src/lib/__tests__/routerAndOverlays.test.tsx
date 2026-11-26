import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { resolveRoute, routeToPath } from '../router';
import { HomePage } from '../../pages/HomePage';
import { ProductPage } from '../../pages/ProductPage';
import { SourcesPage } from '../../pages/SourcesPage';
import { AboutPage } from '../../pages/AboutPage';
import { Header } from '../../components/Header';
import { Footer } from '../../components/Footer';
import { BottomPotEasterEgg } from '../../components/BottomPotEasterEgg';
import { apiUrl, apiCredentials, getApiBaseUrl } from '../apiBase';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../components/ui/select';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from '../../components/ui/dropdown-menu';
import { Popover, PopoverTrigger, PopoverContent } from '../../components/ui/popover';
import selectSrc from '../../components/ui/select.tsx?raw';
import dropdownSrc from '../../components/ui/dropdown-menu.tsx?raw';
import popoverSrc from '../../components/ui/popover.tsx?raw';

describe('Multi-Page Router & Overlay Primitive Defaults', () => {
  it('resolves all multi-page paths and workspace entry params without hash fragments', () => {
    expect(resolveRoute('/')).toBe('home');
    expect(resolveRoute('/product')).toBe('product');
    expect(resolveRoute('/sources')).toBe('sources');
    expect(resolveRoute('/about')).toBe('about');
    expect(resolveRoute('/app')).toBe('search');
    expect(resolveRoute('/search')).toBe('search');
    expect(resolveRoute('/admin')).toBe('admin');

    expect(resolveRoute('/', '?q=Backend')).toBe('search');
    expect(resolveRoute('/', '?mock=1')).toBe('search');
    expect(resolveRoute('/', '?view=app')).toBe('search');
    expect(resolveRoute('/', '?saved=1')).toBe('search');

    expect(routeToPath('home')).toBe('/');
    expect(routeToPath('search')).toBe('/app');
    expect(routeToPath('product')).toBe('/product');
    expect(routeToPath('sources')).toBe('/sources');
    expect(routeToPath('about')).toBe('/about');
    expect(routeToPath('admin')).toBe('/admin');
  });

  it('renders HomePage with embedded SearchForm and editorial pages with zero competitor names, zero dev jargon, and zero hash links', () => {
    const pages = [
      renderToStaticMarkup(<HomePage onNavigate={() => {}} />),
      renderToStaticMarkup(<ProductPage onNavigate={() => {}} />),
      renderToStaticMarkup(<SourcesPage onNavigate={() => {}} onSearchPlatforms={() => {}} />),
      renderToStaticMarkup(<AboutPage onNavigate={() => {}} />),
    ];

    expect(pages[0]).toContain('<form');
    expect(pages[0]).toContain('Role or keyword');
    expect(pages[0]).toContain('How it works');
    expect(pages[0]).toContain('Find live jobs you can actually apply to.');
    expect(pages[1]).toContain('Skip dead links and surprise location rules.');
    expect(pages[2]).toContain('13 sources, all direct to the employer.');
    expect(pages[3]).toContain('Built for people tired of dead job links.');

    for (const html of pages) {
      expect(html).not.toContain('href="#');
      expect(html).not.toContain('\u2014');
      expect(html).not.toMatch(/linkedin|indeed|ziprecruiter|glassdoor/i);
      expect(html).not.toMatch(/JSON\/XML|career tenants|mailto domains|GraphQL|ATS adapters/i);
    }
  });

  it('uses square tactile active indicator instead of bottom underline in Header navigation', () => {
    const headerHtml = renderToStaticMarkup(
      <Header
        activeRoute="sources"
        onNavigate={() => {}}
        onOpenShortcuts={() => {}}
        onOpenCommand={() => {}}
        theme="light"
        onToggleTheme={() => {}}
      />
    );
    expect(headerHtml).toContain('aria-current="page"');
    expect(headerHtml).toContain('bg-[var(--surface-subtle)] border-[var(--border-strong)]');
    expect(headerHtml).toContain('size-1.5 bg-[var(--accent)]');
    expect(headerHtml).not.toContain('border-b-2');
    expect(headerHtml).toContain('Open search');

    const homeHeaderHtml = renderToStaticMarkup(
      <Header
        activeRoute="home"
        onNavigate={() => {}}
        onOpenShortcuts={() => {}}
        onOpenCommand={() => {}}
        theme="light"
        onToggleTheme={() => {}}
      />
    );
    expect(homeHeaderHtml).toContain('>Search<');
    expect(homeHeaderHtml).not.toContain('Open search');
  });

  it('uses soft-square radius tokens and neutral hover surface tokens in overlay primitives', () => {
    const overlayHtml = renderToStaticMarkup(
      <div>
        <Select value="all">
          <SelectTrigger>
            <SelectValue placeholder="Select" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="all">All</SelectItem>
          </SelectContent>
        </Select>
        <DropdownMenu open>
          <DropdownMenuTrigger>Actions</DropdownMenuTrigger>
          <DropdownMenuContent>
            <DropdownMenuItem>Run again</DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
        <Popover open>
          <PopoverTrigger>Sources</PopoverTrigger>
          <PopoverContent>Source list</PopoverContent>
        </Popover>
      </div>
    );

    expect(overlayHtml).not.toContain('focus:bg-accent');
    expect(overlayHtml).not.toContain('rounded-xl');
    expect(overlayHtml).not.toContain('rounded-4xl');
    expect(overlayHtml).not.toContain('rounded-none');
    expect(overlayHtml).toContain('rounded-md');

    // Popup surfaces render in portals (not in static markup), so assert their token classes from source.
    // Computed 8px values for the open surfaces are verified in Playwright (run 3 part 2).
    for (const src of [selectSrc, dropdownSrc, popoverSrc]) {
      expect(src).toMatch(/overflow-[^"]*rounded-lg|rounded-lg border border-\[var\(--border\)\]/);
      expect(src).not.toContain('rounded-xl');
      expect(src).not.toContain('rounded-4xl');
    }
    expect(selectSrc).toContain('rounded-sm');
    expect(dropdownSrc).toContain('rounded-sm');
  });

  it('uses human-readable platform names on SourcesPage, resolves apiUrl defaults cleanly, and includes footer links', () => {
    const sourcesHtml = renderToStaticMarkup(
      <SourcesPage onNavigate={() => {}} onSearchPlatforms={() => {}} />
    );
    expect(sourcesHtml).toContain('Search Greenhouse');
    expect(sourcesHtml).toContain('Search HotNigerianJobs');
    expect(sourcesHtml).not.toContain('Search hotnigerianjobs');

    const footerHtml = renderToStaticMarkup(
      <Footer onNavigate={() => {}} onNewSearch={() => {}} onOpenShortcuts={() => {}} />
    );
    expect(footerHtml).toContain('Search jobs');
    expect(footerHtml).toContain('New search');

    expect(getApiBaseUrl()).toBe('');
    expect(apiUrl('/search?q=go')).toBe('/search?q=go');
    expect(apiUrl('health')).toBe('/health');
    expect(apiCredentials()).toBe('same-origin');
  });

  it('renders clean Bottom of the Pot easter egg copy without 00 //, esc to close, or em dashes', () => {
    const eggHtml = renderToStaticMarkup(
      <BottomPotEasterEgg open={true} onClose={() => {}} theme="light" />
    );
    expect(eggHtml).toContain('Bottom of the Pot');
    expect(eggHtml).toContain('You scraped all the way to the bottom.');
    expect(eggHtml).toContain('Try Party Jollof accent');
    expect(eggHtml).not.toContain('00 //');
    expect(eggHtml).not.toContain('esc to close');
    expect(eggHtml).not.toContain('recycled job links');
    expect(eggHtml).not.toContain('\u2014');
  });
});
