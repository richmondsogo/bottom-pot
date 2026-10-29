import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  PromptInput,
  PromptInputField,
  PromptInputActions,
  PromptInputAction,
} from '../../components/prompt-kit/prompt-input';
import { SearchSummaryBar } from '../../components/SearchSummaryBar';

describe('PromptInput primitives', () => {
  it('renders PromptInput container with square radius and border styles', () => {
    const html = renderToStaticMarkup(
      <PromptInput className="custom-input">
        <PromptInputField placeholder="Search..." />
        <PromptInputActions>
          <PromptInputAction>Action</PromptInputAction>
        </PromptInputActions>
      </PromptInput>
    );

    expect(html).toContain('data-slot="prompt-input"');
    expect(html).toContain('custom-input');
    expect(html).toContain('border-radius:0');
    expect(html).toContain('data-slot="prompt-input-field"');
    expect(html).toContain('placeholder="Search..."');
    expect(html).toContain('data-slot="prompt-input-actions"');
    expect(html).toContain('data-slot="prompt-input-action"');
    expect(html).toContain('Action');
  });

  it('renders error state border correctly on PromptInput', () => {
    const html = renderToStaticMarkup(
      <PromptInput error={true}>
        <PromptInputField />
      </PromptInput>
    );
    expect(html).toContain('border-[var(--destructive)]');
  });

  it('renders dedicated Export button in user mode with visible count and export trigger', () => {
    const html = renderToStaticMarkup(
      <SearchSummaryBar
        searchParams={{ keywords: 'Frontend', location: '', workModel: 'any', postAge: '7', includeNigerian: true, deepScrape: false }}
        totalResults={42}
        filteredCount={15}
        mode="user"
        metrics={null}
        savedTimestamp={null}
        onEditSearch={() => {}}
        onNewSearch={() => {}}
        onRunAgain={() => {}}
        onClearSaved={() => {}}
        onDownloadCsv={() => {}}
        onDownloadJson={() => {}}
      />
    );
    expect(html).toContain('Export');
    expect(html).toContain('aria-label="Export results"');
    expect(html).toContain('Edit search');
  });

  it('renders dedicated Export button in both user and admin modes', () => {
    const userHtml = renderToStaticMarkup(
      <SearchSummaryBar
        searchParams={{ keywords: 'Frontend', location: '', workModel: 'any', postAge: '7', includeNigerian: true, deepScrape: false }}
        totalResults={42}
        mode="user"
        metrics={null}
        savedTimestamp={null}
        onEditSearch={() => {}}
        onNewSearch={() => {}}
        onRunAgain={() => {}}
        onClearSaved={() => {}}
        onDownloadCsv={() => {}}
        onDownloadJson={() => {}}
      />
    );
    expect(userHtml).toContain('aria-label="Export results"');

    const adminHtml = renderToStaticMarkup(
      <SearchSummaryBar
        searchParams={{ keywords: 'Backend', location: '', workModel: 'any', postAge: '7', includeNigerian: true, deepScrape: false }}
        totalResults={10}
        mode="admin"
        metrics={null}
        savedTimestamp={null}
        onEditSearch={() => {}}
        onNewSearch={() => {}}
        onRunAgain={() => {}}
        onClearSaved={() => {}}
        onDownloadCsv={() => {}}
        onDownloadJson={() => {}}
      />
    );
    expect(adminHtml).toContain('aria-label="Export results"');
    expect(adminHtml).toContain('aria-label="More actions"');
  });
});
