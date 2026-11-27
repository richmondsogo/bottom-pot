import React from 'react';
import type { AppRoute } from '../lib/router';

export interface PrivacyPageProps {
  onNavigate?: (route: AppRoute) => void;
}

export const PrivacyPage: React.FC<PrivacyPageProps> = () => {
  return (
    <div className="w-full">
      <section className="py-16 sm:py-20 border-b border-[var(--border)]">
        <div className="page-shell max-w-3xl bp-fade-up">
          <h1 className="text-display font-semibold tracking-tight text-[var(--ink)]">
            Privacy Policy
          </h1>
        </div>
      </section>
    </div>
  );
};
