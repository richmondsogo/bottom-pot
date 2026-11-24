import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import { resolveRoute, routeToPath } from '../router';
import { HomePage } from '../../pages/HomePage';
import { ProductPage } from '../../pages/ProductPage';
import { SourcesPage } from '../../pages/SourcesPage';
import { AboutPage } from '../../pages/AboutPage';
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '../../components/ui/select';
import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent, DropdownMenuItem } from '../../components/ui/dropdown-menu';
import { Popover, PopoverTrigger, PopoverContent } from '../../components/ui/popover';

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

  it('renders calm editorial pages with zero forms on HomePage and zero hash anchor links', () => {
    const pages = [
      renderToStaticMarkup(<HomePage onNavigate={() => {}} />),
      renderToStaticMarkup(<ProductPage onNavigate={() => {}} />),
      renderToStaticMarkup(<SourcesPage onNavigate={() => {}} onSearchPlatforms={() => {}} />),
      renderToStaticMarkup(<AboutPage onNavigate={() => {}} />),
    ];

    expect(pages[0]).not.toContain('<form');
    expect(pages[0]).toContain('Jobs straight from the company.');
    expect(pages[1]).toContain('Built for verifiable job search.');
    expect(pages[2]).toContain('Thirteen verified sources.');
    expect(pages[3]).toContain('Why Bottom Pot exists.');

    for (const html of pages) {
      expect(html).not.toContain('href="#');
    }
  });

  it('keeps square geometry and neutral hover surface tokens in overlay primitives', () => {
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
    expect(overlayHtml).not.toContain('rounded-md');
    expect(overlayHtml).not.toContain('rounded-lg');
  });
});
