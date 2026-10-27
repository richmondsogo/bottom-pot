import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { verifyAdminSession, loginAdmin, logoutAdmin } from '../adminAuth';

describe('adminAuth client', () => {
  const originalFetch = globalThis.fetch;

  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  describe('verifyAdminSession', () => {
    it('returns true when status is 200 and authenticated is true', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ authenticated: true }),
      });

      const authed = await verifyAdminSession();
      expect(authed).toBe(true);
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/admin/verify', {
        method: 'GET',
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
    });

    it('returns false when status is 401', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
        json: async () => ({ detail: 'Not authenticated' }),
      });

      const authed = await verifyAdminSession();
      expect(authed).toBe(false);
    });

    it('returns false when fetch rejects (network error)', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error('Network error'));

      const authed = await verifyAdminSession();
      expect(authed).toBe(false);
    });
  });

  describe('loginAdmin', () => {
    it('returns success on 200', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
      });

      const result = await loginAdmin('correct-password');
      expect(result.success).toBe(true);
      expect(result.status).toBe(200);
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/admin/login', {
        method: 'POST',
        credentials: 'same-origin',
        headers: {
          'Content-Type': 'application/json',
          Accept: 'application/json',
        },
        body: JSON.stringify({ password: 'correct-password' }),
      });
    });

    it('returns friendly message on 401 (wrong password)', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 401,
      });

      const result = await loginAdmin('wrong-password');
      expect(result.success).toBe(false);
      expect(result.status).toBe(401);
      expect(result.message).toBe('Incorrect admin password.');
    });

    it('returns rate limit message on 429', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 429,
      });

      const result = await loginAdmin('password');
      expect(result.success).toBe(false);
      expect(result.status).toBe(429);
      expect(result.message).toContain('Too many login attempts');
    });

    it('returns admin disabled message on 503', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 503,
      });

      const result = await loginAdmin('password');
      expect(result.success).toBe(false);
      expect(result.status).toBe(503);
      expect(result.message).toContain('ADMIN_PASSWORD is not configured');
    });

    it('handles network failure gracefully', async () => {
      globalThis.fetch = vi.fn().mockRejectedValue(new Error('Connection dropped'));

      const result = await loginAdmin('password');
      expect(result.success).toBe(false);
      expect(result.status).toBe(0);
      expect(result.message).toContain('Unable to reach the authentication service');
    });
  });

  describe('logoutAdmin', () => {
    it('returns true on 200', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
      });

      const ok = await logoutAdmin();
      expect(ok).toBe(true);
      expect(globalThis.fetch).toHaveBeenCalledWith('/api/admin/logout', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { Accept: 'application/json' },
      });
    });

    it('returns false on error', async () => {
      globalThis.fetch = vi.fn().mockResolvedValue({
        ok: false,
        status: 500,
      });

      const ok = await logoutAdmin();
      expect(ok).toBe(false);
    });
  });
});
