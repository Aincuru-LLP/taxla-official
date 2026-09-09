"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  Server,
  ArrowLeft,
  ShieldCheck,
  Cpu,
  Globe,
  Clock,
  ExternalLink,
} from "lucide-react";

import { fetchSettings } from "@/lib/api";

export default function SystemSettingsPage() {
  const [settings, setSettings] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchSettings()
      .then((data) => setSettings(data))
      .catch((err) => console.error("Failed to load settings:", err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-16 text-center text-sm text-slate-400">Loading system parameters…</div>;
  }

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3 pb-6 border-b border-slate-200">
        <Link
          href="/settings"
          className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            System & Automation Parameters
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Target Udyam environment, Playwright worker configuration, and operational timeouts.
          </p>
        </div>
      </div>

      {/* Target URL Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <Globe className="w-4 h-4 text-indigo-600" />
            <span>Target Portal Environment</span>
          </h2>
          <span className="px-2.5 py-0.5 rounded text-[11px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200 uppercase">
            {settings?.target_mode || "PRODUCTION"}
          </span>
        </div>

        <div className="p-4 bg-slate-50 rounded-lg border border-slate-200 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div>
            <div className="text-[11px] text-slate-500 uppercase font-semibold">Configured Target URL</div>
            <div className="font-mono text-sm font-bold text-slate-900 mt-0.5">
              {settings?.udyam_target_url}
            </div>
          </div>

          <a
            href={settings?.udyam_target_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-slate-300 hover:bg-slate-50 rounded-lg text-xs font-semibold text-slate-700 transition-colors shadow-2xs"
          >
            <span>Visit Target</span>
            <ExternalLink className="w-3.5 h-3.5" />
          </a>
        </div>
      </div>

      {/* Worker Parameters */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
        <div className="pb-3 border-b border-slate-100">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <Cpu className="w-4 h-4 text-slate-500" />
            <span>Worker Execution Parameters</span>
          </h2>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Browser Display Mode</span>
            <div className="font-bold text-slate-900 mt-0.5">
              {settings?.playwright_headed_mode ? "Headed (Visible Chrome)" : "Headless (Background)"}
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">OTP Human Checkpoint Timeout</span>
            <div className="font-bold text-slate-900 mt-0.5">
              {settings?.otp_timeout_seconds} Seconds (5 minutes)
            </div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Auto-Retry Max Limit</span>
            <div className="font-bold text-slate-900 mt-0.5">
              {settings?.auto_retry_max_attempts} Attempts on Failure
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
