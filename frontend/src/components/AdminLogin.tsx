import React, { useState } from 'react';
import { Button } from './ui/button';
import { Input } from './ui/input';
import { FieldSet, Field, FieldLabel } from './ui/field';
import { loginAdmin } from '../lib/adminAuth';
import { LogoLockup } from './BottomPotLogo';

interface AdminLoginProps {
  onLoginSuccess: () => void;
}

export const AdminLogin: React.FC<AdminLoginProps> = ({ onLoginSuccess }) => {
  const [password, setPassword] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!password.trim() || isSubmitting) return;

    setIsSubmitting(true);
    setErrorMessage(null);

    const result = await loginAdmin(password);
    setIsSubmitting(false);

    if (result.success) {
      onLoginSuccess();
    } else {
      setErrorMessage(result.message || 'Login failed. Please check your credentials.');
    }
  };

  return (
    <div
      className="min-h-screen w-full flex items-center justify-center p-4 transition-colors duration-150"
      style={{ backgroundColor: 'var(--bg)' }}
    >
      <div
        className="w-full max-w-[420px] border border-[var(--border)] p-6 sm:p-8"
        style={{ backgroundColor: 'var(--surface)' }}
      >
        {/* Brand header */}
        <div className="flex items-center gap-2.5 mb-6 select-none text-[var(--ink)]">
          <LogoLockup className="h-[18px] sm:h-7 w-auto" />
          <span
            className="text-[11px] font-mono font-semibold px-2 py-0.5 border border-[var(--border-strong)] bg-[var(--surface-subtle)] text-[var(--ink)] ml-auto"
            title="Administrator Access"
          >
            ADMIN
          </span>
        </div>

        <div className="mb-6">
          <h1 className="text-xl font-semibold tracking-[-0.02em] text-[var(--ink)] mb-1">
            Sign in to Admin
          </h1>
          <p className="text-xs text-[var(--ink-muted)]">
            Administrator sign-in.
          </p>
        </div>

        {/* Error Alert */}
        {errorMessage && (
          <div
            role="alert"
            className="mb-5 p-3 text-xs border border-destructive/40 bg-destructive/10 text-destructive font-mono"
          >
            {errorMessage}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <FieldSet className="gap-4">
            <Field>
              <FieldLabel
                htmlFor="admin-password"
                className="text-xs font-mono uppercase tracking-wider text-[var(--ink-muted)]"
              >
                Password
              </FieldLabel>
              <Input
                id="admin-password"
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                disabled={isSubmitting}
                required
                className="rounded-none h-10 border-[var(--border)] bg-[var(--bg)] text-[var(--ink)] focus-visible:border-[var(--ink)] focus-visible:ring-0"
                placeholder="Enter admin password"
              />
            </Field>

            {/* Neutral ink submit button (ADR 0021 compliance: zero green) */}
            <Button
              type="submit"
              disabled={isSubmitting || !password.trim()}
              className="h-10 w-full rounded-none border border-transparent bg-[var(--ink)] text-[var(--bg)] hover:bg-[var(--ink)]/90 font-medium text-sm transition-colors cursor-pointer select-none"
            >
              {isSubmitting ? 'Verifying…' : 'Access Admin Workspace'}
            </Button>
          </FieldSet>
        </form>
      </div>
    </div>
  );
};
