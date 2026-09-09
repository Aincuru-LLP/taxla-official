import axios from 'axios';

// Create an axios instance pointing to our rewrite path /api
export const apiClient = axios.create({
  baseURL: '/api/v1',
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // so the HttpOnly refresh cookie travels on /login & /refresh
});

// Token is held in memory only. The HttpOnly refresh-token cookie handles
// session persistence across reloads (see /auth/refresh interceptor below).
let accessToken = null;

export function setAccessToken(token) {
  accessToken = token;
  if (token) {
    apiClient.defaults.headers.common['Authorization'] = `Bearer ${token}`;
  } else {
    delete apiClient.defaults.headers.common['Authorization'];
  }
}

export function getAccessToken() {
  return accessToken;
}

// Set up the boot-time refresh + 401-refresh-retry interceptor. We
// dynamically import the Zustand store so this module stays importable
// from both client and server contexts (the store pulls in 'use client').
let _storeModule = null;
async function _getStore() {
  if (!_storeModule) {
    _storeModule = await import('@/stores/authStore');
  }
  return _storeModule.useAuthStore;
}

// Axios interceptor: on 401, attempt a silent refresh once. If refresh
// fails, clear the auth store AND route to /login so the user can sign
// back in instead of staring at a broken page.
//
// We trigger a full reload rather than a router.replace: a stale Zustand
// state, a stale React Query cache, or a stale in-memory access token can
// all survive a soft navigation and cause the same 401 to repeat on the
// next page. window.location does the heavy lifting and starts clean.
apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config || {};
    if (error.response?.status === 401 && !originalRequest._retry) {
      // Don't try to refresh /auth/* itself — that's a login-failure
      // signal, not an expired-session signal.
      const url = originalRequest.url || '';
      if (url.includes('/auth/')) {
        return Promise.reject(error);
      }
      originalRequest._retry = true;
      try {
        // /auth/refresh reads the HttpOnly refresh cookie; the response sets a
        // new refresh cookie and returns a new access token.
        const refreshRes = await axios.post('/api/v1/auth/refresh', {}, {
          withCredentials: true,
        });
        const newToken = refreshRes.data?.access_token;
        if (!newToken) throw new Error('Refresh returned no access token');
        setAccessToken(newToken);
        originalRequest.headers = originalRequest.headers || {};
        originalRequest.headers['Authorization'] = `Bearer ${newToken}`;
        return apiClient(originalRequest);
      } catch (refreshErr) {
        setAccessToken(null);
        // Clear the auth store, then route to /login. We do the navigation
        // here (rather than waiting for a layout-level effect) so the page
        // that triggered the 401 doesn't sit there showing console errors
        // until React re-renders.
        try {
          const useStore = await _getStore();
          useStore.getState().clearAuth();
        } catch {
          // Store not loaded (e.g. SSR) — silent.
        }
        if (typeof window !== 'undefined') {
          const here = window.location.pathname + window.location.search;
          // Only navigate if we're not already on /login — otherwise we'd
          // just refresh the page mid-typing.
          if (!here.startsWith('/login')) {
            window.location.assign('/login?from=' + encodeURIComponent(here));
          }
        }
        return Promise.reject(refreshErr);
      }
    }
    return Promise.reject(error);
  }
);

// ────────────────────────────────────────────────────────────────────────────
// Auth
// ────────────────────────────────────────────────────────────────────────────

/**
 * POST /auth/login. Sets the Authorization header on the shared client and
 * returns the user payload so the caller can hydrate the auth store.
 */
export async function loginRequest(username, password) {
  const res = await apiClient.post('/auth/login', {
    username,
    password,
  });
  const { access_token, user } = res.data;
  setAccessToken(access_token);
  return { user, accessToken: access_token };
}

/**
 * POST /auth/logout. Best-effort: even if the call fails, the caller
 * should still clear local auth state and route to /login.
 */
export async function logoutRequest() {
  try {
    await apiClient.post('/auth/logout');
  } finally {
    setAccessToken(null);
  }
}

/**
 * Boot-time refresh. Tries to mint a new access token from the HttpOnly
 * cookie; returns the user if /me succeeds, or null otherwise.
 */
export async function bootRefresh() {
  try {
    const refreshRes = await axios.post('/api/v1/auth/refresh', {}, {
      withCredentials: true,
    });
    const newToken = refreshRes.data?.access_token;
    if (!newToken) return null;
    setAccessToken(newToken);
    const meRes = await apiClient.get('/auth/me');
    return { user: meRes.data, accessToken: newToken };
  } catch {
    return null;
  }
}

// ────────────────────────────────────────────────────────────────────────────
// Application API
// ────────────────────────────────────────────────────────────────────────────

// ────────────────────────────────────────────────────────────────────────────
// Application API
// ────────────────────────────────────────────────────────────────────────────

export const fetchApplications = async () => {
  const res = await apiClient.get('/applications');
  return res.data;
};

export const fetchApplication = async (id) => {
  const res = await apiClient.get(`/applications/${id}`);
  return res.data;
};

export const searchNIC = async (id, businessDescription) => {
  const res = await apiClient.post(`/applications/${id}/nic/search`, {
    business_description: businessDescription,
    location_text: 'India',
  });
  return res.data;
};

export const approveNIC = async (id, suggestionId, overrideCode) => {
  const payload = {};
  if (suggestionId) payload.nic_suggestion_id = suggestionId;
  if (overrideCode) payload.override_code_5digit = overrideCode;

  const res = await apiClient.post(`/applications/${id}/nic/approve`, payload);
  return res.data;
};

export const submitOTP = async (id, otpType, code) => {
  const res = await apiClient.post(`/applications/${id}/otp`, {
    otp_type: otpType,
    code: code,
  });
  return res.data;
};