"use client";

/**
 * Auth state for the TAXLA frontend.
 *
 * The access token lives in memory only — never in localStorage, never on
 * disk. The HttpOnly refresh cookie set by /api/v1/auth/login is what
 * actually persists the session across reloads. On boot, the layout
 * (frontend/src/app/layout.tsx) should fire a /api/v1/auth/refresh request
 * via the shared apiClient; if it returns 200, call `setAuth(...)`. If it
 * 401s, call `clearAuth()` so middleware can redirect to /login.
 *
 * The login page calls `setAuth(...)` after a successful POST. The Sidebar
 * logout button calls `clearAuth()` after POST /api/v1/auth/logout.
 */

import { create } from "zustand";
import type { AuthUser } from "@/types/auth";

interface AuthState {
  user: AuthUser | null;
  accessToken: string | null;
  /** True while the boot-time /refresh attempt is in flight. */
  isBooting: boolean;
  setAuth: (payload: { user: AuthUser; accessToken: string }) => void;
  setBooting: (value: boolean) => void;
  clearAuth: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  user: null,
  accessToken: null,
  isBooting: true,
  setAuth: ({ user, accessToken }) =>
    set({ user, accessToken, isBooting: false }),
  setBooting: (value) => set({ isBooting: value }),
  clearAuth: () => set({ user: null, accessToken: null, isBooting: false }),
}));