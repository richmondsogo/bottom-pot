/**
 * Admin authentication utilities and session API client.
 */

export interface LoginResult {
  success: boolean;
  status: number;
  message?: string;
}

export async function verifyAdminSession(): Promise<boolean> {
  try {
    const res = await fetch('/api/admin/verify', {
      method: 'GET',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    if (res.ok) {
      const data = await res.json();
      return Boolean(data.authenticated);
    }
    return false;
  } catch {
    return false;
  }
}

export async function loginAdmin(password: string): Promise<LoginResult> {
  try {
    const res = await fetch('/api/admin/login', {
      method: 'POST',
      credentials: 'same-origin',
      headers: {
        'Content-Type': 'application/json',
        Accept: 'application/json',
      },
      body: JSON.stringify({ password }),
    });
    if (res.ok) {
      return { success: true, status: res.status };
    }
    if (res.status === 401) {
      return { success: false, status: 401, message: 'Incorrect admin password.' };
    }
    if (res.status === 429) {
      return {
        success: false,
        status: 429,
        message: 'Too many login attempts. Please wait a minute and try again.',
      };
    }
    if (res.status === 503) {
      return {
        success: false,
        status: 503,
        message: 'Admin access is disabled on this server (ADMIN_PASSWORD is not configured).',
      };
    }
    return { success: false, status: res.status, message: 'Login failed. Unexpected server response.' };
  } catch {
    return {
      success: false,
      status: 0,
      message: 'Unable to reach the authentication service. Check your connection.',
    };
  }
}

export async function logoutAdmin(): Promise<boolean> {
  try {
    const res = await fetch('/api/admin/logout', {
      method: 'POST',
      credentials: 'same-origin',
      headers: { Accept: 'application/json' },
    });
    return res.ok;
  } catch {
    return false;
  }
}
