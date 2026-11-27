import React from 'react';
import { Mail } from 'lucide-react';
import { DEFAULT_CONTACT_EMAIL, getConfiguredContactEmail } from '../lib/contactConfig';
import type { AppRoute } from '../lib/router';

export interface ContactPageProps {
  onNavigate?: (route: AppRoute) => void;
  contactEmailOverride?: string | null;
}

export const ContactPage: React.FC<ContactPageProps> = ({
  contactEmailOverride,
}) => {
  const contactEmail = getConfiguredContactEmail(contactEmailOverride) ?? DEFAULT_CONTACT_EMAIL;

  return (
    <div className="w-full">
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Get in touch.
          </h1>
          <p className="text-lead text-[var(--ink-muted)] mt-5 leading-relaxed">
            Found a broken link, incorrect job detail or confusing eligibility label? Have feedback
            about the search experience? Send us a message. Useful reports help us make Bottom Pot
            better.
          </p>
        </div>
      </section>

      <section className="py-14">
        <div className="page-shell max-w-3xl flex flex-col gap-6">
          <div
            data-testid="contact-direct-email"
            className="rounded-lg border border-[var(--border)] bg-[var(--surface)] p-6 flex flex-col gap-3 items-start"
          >
            <h2 className="text-sm font-semibold text-[var(--ink)]">Email us</h2>
            <p className="text-sm text-[var(--ink-muted)] leading-relaxed max-w-[60ch]">
              Tell us what happened and include the company, role title or listing link when
              relevant.
            </p>
            <div className="flex flex-wrap items-center gap-3">
              <a
                href={`mailto:${contactEmail}`}
                className="h-10 max-md:h-11 max-md:min-w-11 px-4 rounded-md inline-flex items-center gap-2 text-sm font-medium border border-[var(--border-strong)] bg-[var(--bg)] text-[var(--ink)] hover:bg-[var(--surface-hover)] transition-[background-color,transform] duration-140 ease-out active:scale-[0.97]"
              >
                <Mail className="size-4 text-[var(--ink-muted)]" aria-hidden="true" />
                <span>Send an email</span>
              </a>
              <span className="text-xs text-[var(--ink-muted)]">{contactEmail}</span>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
};
