"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

/**
 * Wraps the app in a single React Query client.
 *
 * The client is created inside a ``useState`` so it's instantiated exactly
 * once per mount of the provider tree (a fresh client on every render
 * would defeat caching).
 *
 * Defaults are tuned for an operator dashboard:
 *   - 30 s stale time keeps the kanban snappy without hammering the API.
 *   - ``refetchOnWindowFocus: true`` because operators often switch tabs to
 *     copy a number from an SMS or portal and come back.
 *   - One retry on read failures; mutations rely on per-call error UI.
 *   - ``networkMode: 'online'`` so the WebSocket fallback can drive cache
 *     updates without the fetch layer fighting it.
 */
export function QueryProvider({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 5 * 60_000,
            refetchOnWindowFocus: true,
            retry: 1,
            networkMode: "online",
          },
          mutations: {
            retry: 0,
            networkMode: "online",
          },
        },
      }),
  );

  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}