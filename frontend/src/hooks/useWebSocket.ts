/**
 * Typed WebSocket hook — Phase 11.
 *
 * Wraps the raw ``new WebSocket(url)`` in a React hook that:
 *
 * * Closes on unmount (no leaked sockets on navigation).
 * * Survives a short offline window — exponential backoff reconnect (capped at
 *   30 s) so a transient backend hiccup doesn't kick the operator back to a
 *   stale view.
 * * Debounces bursts of inbound messages so a single busy workflow event
 *   doesn't fire 30 React Query refetches in a row.
 * * Sends the bearer access token in the WebSocket subprotocol slot so the
 *   backend can authenticate the upgrade. The access token is refreshed by
 *   ``api/workflow.js`` so we re-read it on every reconnect.
 * * Lets callers pass a typed ``z`` schema for the inbound payload — anything
 *   that fails parsing is logged once and dropped, never thrown.
 *
 * The hook is intentionally minimal: callers do their own React Query
 * ``invalidateQueries`` inside ``onMessage`` because which cache entries need
 * to refresh is application-specific.
 */
import { useEffect, useRef } from "react";
import type { ZodType } from "zod";

import { getAccessToken } from "@/api/workflow";

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------
const DEFAULT_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;
const DEFAULT_DEBOUNCE_MS = 250;

export interface WebSocketMessage<T = unknown> {
  /** Parsed JSON body. Schema-validated when ``schema`` is provided. */
  data: T;
  /** Raw event for callers that need it (origin, etc.). */
  raw: MessageEvent;
}

export interface UseWebSocketOptions<T> {
  /** Path appended to ``ws://<host>/api/v1`` (must start with ``/``). */
  path: string;
  /**
   * Optional Zod schema. When present, inbound JSON is parsed through it;
   * parse failures are dropped with a ``console.warn`` so the UI is never
   * thrown by a malformed broadcast.
   */
  schema?: ZodType<T>;
  /** Called for every accepted message (after debounce). */
  onMessage: (msg: WebSocketMessage<T>) => void;
  /** Coalesce messages within this window before invoking ``onMessage``. */
  debounceMs?: number;
  /** Override the default ``ws://host/api/v1`` base URL. */
  baseUrl?: string;
  /** Reconnect on close (default: true). */
  reconnect?: boolean;
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------
export function useWebSocket<T = unknown>({
  path,
  schema,
  onMessage,
  debounceMs = DEFAULT_DEBOUNCE_MS,
  baseUrl,
  reconnect = true,
}: UseWebSocketOptions<T>): void {
  // Refs let us hand the latest callback/socket to the timeout without
  // re-running the effect on every render.
  const onMessageRef = useRef(onMessage);
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectAttemptRef = useRef(0);
  const debounceTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingMessagesRef = useRef<WebSocketMessage<T>[]>([]);
  const closedByEffectRef = useRef(false);

  useEffect(() => {
    onMessageRef.current = onMessage;
  }, [onMessage]);

  useEffect(() => {
    closedByEffectRef.current = false;
    reconnectAttemptRef.current = 0;

    const flushPending = () => {
      const batch = pendingMessagesRef.current;
      pendingMessagesRef.current = [];
      // Only deliver the last message — debouncing is for "many small
      // refetches" not for batched processing.
      const last = batch[batch.length - 1];
      if (last) onMessageRef.current(last);
    };

    const scheduleFlush = () => {
      if (debounceTimerRef.current) clearTimeout(debounceTimerRef.current);
      debounceTimerRef.current = setTimeout(() => {
        debounceTimerRef.current = null;
        flushPending();
      }, debounceMs);
    };

    const connect = () => {
      if (closedByEffectRef.current) return;

      // Re-read the access token on every (re)connect — it can rotate while
      // the page is open.
      const token = getAccessToken();
      const protocols = token ? [`token.${token}`] : undefined;
      // The Next.js HTTP rewrite in next.config.ts proxies /api/* → backend,
      // but WebSockets aren't proxied — the upgrade has to hit the backend
      // directly. ``NEXT_PUBLIC_WS_BASE_URL`` is the env-driven base; in
      // dev it defaults to the same backend the HTTP proxy targets.
      const base =
        baseUrl ??
        (typeof process !== "undefined" &&
        process.env.NEXT_PUBLIC_WS_BASE_URL
          ? process.env.NEXT_PUBLIC_WS_BASE_URL
          : typeof window !== "undefined"
            ? `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/v1`
            : "ws://localhost:8000/api/v1");
      const url = `${base}${path}`;

      let ws: WebSocket;
      try {
        ws = new WebSocket(url, protocols);
      } catch (err) {
        console.warn("[useWebSocket] failed to construct WebSocket", err);
        scheduleReconnect();
        return;
      }
      wsRef.current = ws;

      ws.onmessage = (event: MessageEvent) => {
        let parsed: T;
        try {
          parsed = JSON.parse(event.data) as T;
        } catch {
          console.warn(
            "[useWebSocket] received non-JSON frame, dropping",
            event.data,
          );
          return;
        }
        if (schema) {
          const result = schema.safeParse(parsed);
          if (!result.success) {
            console.warn(
              "[useWebSocket] schema validation failed, dropping",
              result.error,
            );
            return;
          }
          parsed = result.data;
        }
        pendingMessagesRef.current.push({ data: parsed, raw: event });
        scheduleFlush();
      };

      ws.onclose = () => {
        wsRef.current = null;
        if (!closedByEffectRef.current && reconnect) scheduleReconnect();
      };

      ws.onerror = () => {
        // The browser fires onerror immediately before onclose; let onclose
        // do the reconnect work to avoid double-scheduling.
      };
    };

    const scheduleReconnect = () => {
      if (closedByEffectRef.current) return;
      const attempt = reconnectAttemptRef.current++;
      // Exponential backoff with full jitter: random in [0, exp].
      const exp = Math.min(MAX_BACKOFF_MS, DEFAULT_BACKOFF_MS * 2 ** attempt);
      const delay = Math.floor(Math.random() * exp);
      setTimeout(connect, delay);
    };

    connect();

    return () => {
      closedByEffectRef.current = true;
      if (debounceTimerRef.current) {
        clearTimeout(debounceTimerRef.current);
        debounceTimerRef.current = null;
      }
      if (wsRef.current) {
        try {
          wsRef.current.close();
        } catch {
          // already closed
        }
        wsRef.current = null;
      }
    };
    // The connection is rebuilt when path, debounceMs, baseUrl, reconnect, or
    // schema identity changes. Stable identity ⇒ stable connection.
  }, [path, debounceMs, baseUrl, reconnect, schema]);
}