import React from 'react';
import type { AppRoute } from '../lib/router';

export interface TermsPageProps {
  onNavigate?: (route: AppRoute) => void;
}

export const TermsPage: React.FC<TermsPageProps> = () => {
  return (
    <div className="w-full">
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Terms of Service
          </h1>
        </div>
      </section>
    </div>
  );
};
