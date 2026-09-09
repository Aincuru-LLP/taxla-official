"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  MessageSquare,
  ArrowLeft,
  ShieldCheck,
  CheckCircle2,
  Copy,
  ExternalLink,
} from "lucide-react";

import { fetchWhatsAppSettings } from "@/lib/api";

export default function WhatsAppSettingsPage() {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchWhatsAppSettings()
      .then((res) => setData(res))
      .catch((err) => console.error("Failed to load WhatsApp settings:", err))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return <div className="p-16 text-center text-sm text-slate-400">Loading WhatsApp configuration…</div>;
  }

  const templates = data?.templates || [];

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
            WhatsApp Cloud API Configuration
          </h1>
          <p className="text-sm text-slate-500 mt-0.5">
            Meta Cloud API connection parameters and approved transactional templates.
          </p>
        </div>
      </div>

      {/* Connection Status Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <ShieldCheck className="w-4 h-4 text-emerald-600" />
            <span>Connection Health</span>
          </h2>
          <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
            {data?.status || "CONNECTED"}
          </span>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Provider Service</span>
            <div className="font-bold text-slate-900 mt-0.5">{data?.provider}</div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Phone Number ID</span>
            <div className="font-mono font-bold text-slate-900 mt-0.5">{data?.phone_number_id}</div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Inbound Webhook Path</span>
            <div className="font-mono font-bold text-slate-900 mt-0.5">{data?.webhook_url}</div>
          </div>
        </div>
      </div>

      {/* Approved Templates Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        <div className="p-4 border-b border-slate-200 bg-slate-50/50">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider">
            Approved Transactional Templates
          </h2>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left border-collapse text-sm">
            <thead>
              <tr className="ops-table-header">
                <th className="px-5 py-3">Template Name</th>
                <th className="px-5 py-3">Category</th>
                <th className="px-5 py-3">Language</th>
                <th className="px-5 py-3">Status</th>
                <th className="px-5 py-3">Content Preview</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {templates.map((tpl: any) => (
                <tr key={tpl.id} className="ops-table-row">
                  <td className="px-5 py-3.5 font-mono text-xs font-bold text-indigo-700">
                    {tpl.name}
                  </td>
                  <td className="px-5 py-3.5 text-xs text-slate-600 font-medium">
                    {tpl.category}
                  </td>
                  <td className="px-5 py-3.5 text-xs text-slate-600 uppercase">
                    {tpl.language}
                  </td>
                  <td className="px-5 py-3.5">
                    <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
                      <CheckCircle2 className="w-3 h-3 text-emerald-600" />
                      {tpl.status}
                    </span>
                  </td>
                  <td className="px-5 py-3.5 text-xs text-slate-700 max-w-md">
                    {tpl.body_text}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
