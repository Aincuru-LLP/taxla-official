"use client";

/**
 * Boot-time auth hydration.
 *
 * Fires once when the app mounts: calls POST /api/v1/auth/refresh (which
 * reads the HttpOnly cookie and mints a new access token), then GET
 * /api/v1/auth/me to load the user. On success, hydrates the Zustand store;
 * on failure (no cookie, expired, revoked), clears the store AND routes to
 * /login so protected pages don't fire API calls that will just 401.
 *
 * Why the redirect lives here (not middleware):
 *   - The refresh cookie is HttpOnly — middleware on the Node side can't
 *     read it. Boot is purely client-side.
 *   - Sending the user to /login while we still hold isBooting=true would
 *     flash a blank page; we redirect only after we've decided the session
 *     is gone.
 *
 * Run-once contract:
 *   The effect MUST only run on mount. Earlier versions included
 *   ``pathname`` in the deps, which caused the boot flow to re-fire on
 *   every sidebar navigation — and on a session-less boot that's a free
 *   ticket to /login. We read the current path at decision time via
 *   ``window.location.pathname`` instead of subscribing to it.
 *
 * Renders nothing visible. Lives in the root layout.
 */

import { useEffect } from "react";
import { useRouter } from "next/navigation";

import { bootRefresh } from "@/api/workflow";
import { useAuthStore } from "@/stores/authStore";

export function BootAuth() {
  const setAuth = useAuthStore((s) => s.setAuth);
  const setBooting = useAuthStore((s) => s.setBooting);
  const isBooting = useAuthStore((s) => s.isBooting);
  const router = useRouter();

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const result = await bootRefresh();
      if (cancelled) return;
      if (result) {
        setAuth(result);
        return;
      }
      // No usable session. Clear any leftover state and send the user to
      // /login. Skip the redirect if they're already on the login page
      // — otherwise we'd just churn history.
      useAuthStore.getState().clearAuth();
      // Read the URL at decision time, NOT from a subscribed hook — we
      // explicitly don't want boot to re-run when the path changes.
      const currentPath =
        typeof window !== "undefined" ? window.location.pathname : "/";
      if (currentPath !== "/login") {
        // Use replace so the back-button doesn't bring us back to the
        // protected page they were trying to load.
        router.replace("/login");
      }
      // setBooting is handled by clearAuth() above (it also flips
      // isBooting=false), but call again defensively in case a caller
      // patched clearAuth to not touch the flag.
      setBooting(false);
    })();
    return () => {
      cancelled = true;
    };
    // Run-once: empty deps. The Zustand setters + router are stable
    // references; reading window.location at decision time means we
    // don't need to subscribe to pathname.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // While booting, render nothing — the rest of the UI can show a
  // loading state via useAuthStore((s) => s.isBooting) if it wants to.
  if (!isBooting) return null;
  return null;
}
