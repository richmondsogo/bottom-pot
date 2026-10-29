import { describe, it, expect } from 'vitest';
import { renderToStaticMarkup } from 'react-dom/server';
import {
  PromptInput,
  PromptInputField,
  PromptInputActions,
  PromptInputAction,
} from '../../components/prompt-kit/prompt-input';

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
});
