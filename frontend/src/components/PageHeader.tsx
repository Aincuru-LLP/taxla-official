"use client";

/**
 * Shared page header used by every top-level page in the workspace.
 *
 * The header is the first thing an operator sees on each route, and
 * consistency here is what makes the app feel like one product rather
 * than ten disconnected screens. The header always renders:
 *
 *   * a leading icon (or icon group) inside a tinted square
 *   * a title + optional subtitle
 *   * an optional right-aligned action slot (buttons, refresh indicator,
 *     breadcrumbs, etc.)
 *
 * Backgrounds lean on the existing glassmorphism tokens; no per-page
 * palette decisions.
 */

import type { ReactNode } from "react";

export interface PageHeaderProps {
  icon: ReactNode;
  title: string;
  subtitle?: string;
  /** Small badge/chip rendered next to the title (e.g. "Live", "Beta"). */
  badge?: ReactNode;
  /** Right-aligned area — buttons, status indicator, etc. */
  actions?: ReactNode;
  /** Optional className for the outer container. */
  className?: string;
}

export function PageHeader({
  icon,
  title,
  subtitle,
  badge,
  actions,
  className,
}: PageHeaderProps) {
  return (
    <header
      className={
        "mb-8 flex flex-wrap items-end justify-between gap-4 " +
        (className ?? "")
      }
    >
      <div className="flex items-center gap-3">
        <div className="flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500/30 via-fuchsia-500/20 to-cyan-500/20 ring-1 ring-white/10">
          {icon}
        </div>
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-slate-50">
              {title}
            </h1>
            {badge}
          </div>
          {subtitle && (
            <p className="text-sm text-slate-400 mt-0.5">{subtitle}</p>
          )}
        </div>
      </div>
      {actions && <div className="flex items-center gap-2">{actions}</div>}
    </header>
  );
}
