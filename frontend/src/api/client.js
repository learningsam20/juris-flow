import { useAuthStore } from '../auth/store';

export class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : 'Request failed');
    this.status = status;
  }
}

export async function api(path, { method = 'GET', body, form } = {}, isRetry = false) {
  const { token, logout, refreshToken } = useAuthStore.getState();
  const headers = {};
  if (token) headers.Authorization = `Bearer ${token}`;
  let payload;
  if (form) {
    payload = form;
  } else if (body !== undefined) {
    headers['Content-Type'] = 'application/json';
    payload = JSON.stringify(body);
  }
  const res = await fetch(`/api/v1${path}`, { method, headers, body: payload });
  if (res.status === 401) {
    if (!isRetry) {
      const newToken = await refreshToken();
      if (newToken) {
        return api(path, { method, body, form }, true);
      }
    }
    logout();
    window.location.hash = '#/login';
    throw new ApiError(401, 'Session expired. Please sign in.');
  }
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* no JSON body */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return null;
  return res.json();
}

// Consume an SSE endpoint ({api}/.../stream) and invoke `onEvent(name, data)`
// for each `event:` payload as it arrives. Resolves when the stream closes;
// throws ApiError on non-200.
export async function streamJson(path, onEvent, { method = 'POST' } = {}) {
  const { token } = useAuthStore.getState();
  const res = await fetch(`/api/v1${path}`, {
    method,
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      /* no body */
    }
    throw new ApiError(res.status, detail);
  }
  if (!res.body) return;

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let idx;
    while ((idx = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, idx).trim();
      buffer = buffer.slice(idx + 1);
      if (!line) continue;
      const colon = line.indexOf(':');
      if (colon === -1) continue;
      const name = line.slice(0, colon).trim();
      const data = line.slice(colon + 1).trim();
      if (name === 'event') {
        onEvent(data, '');
      } else if (name === 'data') {
        onEvent('__data__', data);
      } else if (name === 'id' || name === 'retry') {
        /* ignore */
      }
    }
  }
}