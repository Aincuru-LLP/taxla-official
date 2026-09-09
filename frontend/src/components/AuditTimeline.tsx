"use client";

/**
 * Phase 11 — AuditTimeline.
 *
 * Vertical timeline showing what happened to an application, newest first.
 * Backed by ``GET /applications/{id}/audit`` (rows from the ``audit_logs``
 * table) merged with ``GET /applications/{id}/workflow-events`` (rows from
 * ``workflow_events``). The two are interleaved by timestamp so a reviewer
 * can see "X uploaded docs" then "PORTAL_RUNNING → OTP_REQUIRED" as one
 * narrative.
 *
 * Design choice: we never poll. React Query refetches on window focus and
 * the existing WebSocket fan-out in the application workspace pushes an
 * invalidation when a transition lands.
 *
 * We use the platform ``Intl.DateTimeFormat`` (no `date-fns` dep) — the
 * rest of the app should be consistent here if/when it adds a date lib.
 */

import { useMemo } from "react";
import {
  Circle,
  Activity,
  ClipboardList,
  FileEdit,
  GitBranch,
  ShieldAlert,
} from "lucide-react";

import {
  useApplicationAuditLog,
  useApplicationWorkflowEvents,
  type AuditLog,
  type WorkflowEvent,
} from "@/lib/api-client";
import { cn } from "@/lib/utils";

type IconKind = "doc" | "branch" | "activity" | "alert";

function iconFor(action: string): IconKind {
  if (action.includes("STATE_TRANSITION")) return "branch";
  if (action.includes("UPLOAD") || action.includes("DOCUMENT")) return "doc";
  if (
    action.includes("NIC") ||
    action.includes("OTP") ||
    action.includes("EXTRACTION")
  )
    return "activity";
  return "activity";
}

const ICON: Record<IconKind, typeof Activity> = {
  doc: FileEdit,
  branch: GitBranch,
  activity: Activity,
  alert: ShieldAlert,
};

const ICON_CLASS: Record<IconKind, string> = {
  doc: "bg-sky-500/15 text-sky-300 ring-sky-400/30",
  branch: "bg-violet-500/15 text-violet-300 ring-violet-400/30",
  activity: "bg-slate-500/15 text-slate-300 ring-slate-400/30",
  alert: "bg-red-500/15 text-red-300 ring-red-400/30",
};

interface TimelineRow {
  id: string;
  created_at: string;
  title: string;
  subtitle?: string;
  icon: IconKind;
}

function rowFromAudit(log: AuditLog): TimelineRow {
  return {
    id: `audit-${log.id}`,
    created_at: log.created_at,
    title: log.action.replace(/_/g, " "),
    subtitle: log.actor_id ? `actor ${log.actor_id.slice(0, 8)}` : undefined,
    icon: iconFor(log.action),
  };
}

function rowFromEvent(event: WorkflowEvent): TimelineRow {
  const isError = event.status === "FAILED" || Boolean(event.error_code);
  return {
    id: `event-${event.id}`,
    created_at: event.created_at,
    title: `${event.node_key} · ${event.event_type.toLowerCase()}`,
    subtitle: event.error_code ?? event.status,
    icon: isError ? "alert" : "branch",
  };
}

// Single DateTimeFormat instance is reused across renders.
const FORMATTER = new Intl.DateTimeFormat(undefined, {
  year: "numeric",
  month: "short",
  day: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
  second: "2-digit",
});

function formatTimestamp(iso: string): string {
  try {
    return FORMATTER.format(new Date(iso));
  } catch {
    return iso;
  }
}

export function AuditTimeline({
  applicationId,
  className,
}: {
  applicationId: string;
  className?: string;
}) {
  const audit = useApplicationAuditLog(applicationId);
  const events = useApplicationWorkflowEvents(applicationId);

  const rows: TimelineRow[] = useMemo(() => {
    const merged: TimelineRow[] = [];
    (audit.data ?? []).forEach((row) => merged.push(rowFromAudit(row)));
    (events.data ?? []).forEach((row) => merged.push(rowFromEvent(row)));
    merged.sort((a, b) => b.created_at.localeCompare(a.created_at));
    return merged;
  }, [audit.data, events.data]);

  const isLoading = audit.isLoading || events.isLoading;
  const error = audit.error ?? events.error;

  if (isLoading) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 text-sm text-slate-400 p-4",
          className,
        )}
      >
        <Circle className="w-3 h-3 animate-pulse" />
        Loading timeline…
      </div>
    );
  }

  if (error) {
    return (
      <div
        className={cn(
          "text-sm text-red-300 p-4 ring-1 ring-red-400/30 rounded-md",
          className,
        )}
      >
        Failed to load timeline.
      </div>
    );
  }

  if (rows.length === 0) {
    return (
      <div
        className={cn(
          "flex items-center gap-2 text-sm text-slate-500 p-4",
          className,
        )}
      >
        <ClipboardList className="w-4 h-4" />
        No audit events yet.
      </div>
    );
  }

  return (
    <ol
      className={cn(
        "relative pl-6 space-y-3 before:absolute before:left-2 before:top-2 before:bottom-2 before:w-px before:bg-slate-700/60",
        className,
      )}
      aria-label="Application audit timeline"
    >
      {rows.map((row) => {
        const Icon = ICON[row.icon];
        return (
          <li key={row.id} className="relative">
            <span
              className={cn(
                "absolute -left-6 top-0.5 inline-flex items-center justify-center w-4 h-4 rounded-full ring-1",
                ICON_CLASS[row.icon],
              )}
              aria-hidden="true"
            >
              <Icon className="w-2.5 h-2.5" />
            </span>
            <div className="flex flex-col">
              <span className="text-sm text-slate-100 capitalize">
                {row.title}
              </span>
              {row.subtitle && (
                <span className="text-xs text-slate-400">{row.subtitle}</span>
              )}
              <span className="text-[11px] text-slate-500 tabular-nums">
                {formatTimestamp(row.created_at)}
              </span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}