import { create } from 'zustand';

const TOKEN_KEY = 'jurislab_access';
const REFRESH_KEY = 'jurislab_refresh';

let refreshPromise = null;

export const useAuthStore = create((set, get) => ({
  token: localStorage.getItem(TOKEN_KEY),
  refresh: localStorage.getItem(REFRESH_KEY),
  user: null,
  loading: false,
  error: null,

  async authenticate(action, payload) {
    set({ loading: true, error: null });
    try {
      const res = await fetch(`/api/v1/auth/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      const body = await res.json();
      if (!res.ok) {
        let msg = 'Authentication failed';
        if (typeof body.detail === 'string') {
          msg = body.detail;
        } else if (Array.isArray(body.detail) && body.detail.length > 0) {
          msg = body.detail.map((d) => d.msg || d.detail || JSON.stringify(d)).join('; ');
        }
        throw new Error(msg);
      }
      if (body.access_token) {
        localStorage.setItem(TOKEN_KEY, body.access_token);
        if (body.refresh_token) localStorage.setItem(REFRESH_KEY, body.refresh_token);
        set({ token: body.access_token, refresh: body.refresh_token || null, loading: false });
        await get().fetchMe();
      } else {
        return await get().authenticate('login', { email: payload.email, password: payload.password });
      }
      return body;
    } catch (err) {
      set({ loading: false, error: err.message });
      throw err;
    }
  },

  async fetchMe() {
    const { token } = get();
    if (!token) return null;
    const res = await fetch('/api/v1/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return null;
    const user = await res.json();
    set({ user });
    return user;
  },

  async refreshToken() {
    const { refresh } = get();
    if (!refresh) return null;
    if (refreshPromise) {
      return refreshPromise;
    }
    refreshPromise = (async () => {
      try {
        const currentRefresh = get().refresh || refresh;
        const res = await fetch('/api/v1/auth/refresh', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ refresh_token: currentRefresh }),
        });
        if (!res.ok) {
          get().logout();
          return null;
        }
        const body = await res.json();
        localStorage.setItem(TOKEN_KEY, body.access_token);
        if (body.refresh_token) localStorage.setItem(REFRESH_KEY, body.refresh_token);
        set({ token: body.access_token, refresh: body.refresh_token || currentRefresh, user: body.user });
        return body.access_token;
      } catch {
        get().logout();
        return null;
      } finally {
        refreshPromise = null;
      }
    })();
    return refreshPromise;
  },

  logout() {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    set({ token: null, refresh: null, user: null, error: null });
  },
}));