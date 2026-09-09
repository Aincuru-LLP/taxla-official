"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams, usePathname, useRouter } from "next/navigation";
import {
  ArrowLeft,
  FileText,
  CheckSquare,
  FileBox,
  CreditCard,
  Cpu,
  Award,
  History,
  ExternalLink,
  User,
  AlertCircle,
} from "lucide-react";

import { fetchApplicationDetail } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

interface TabItem {
  id: string;
  label: string;
  href: string;
  icon: React.ComponentType<{ className?: string }>;
}

export default function ApplicationLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const params = useParams();
  const pathname = usePathname();
  const router = useRouter();
  const applicationId = params?.id as string;

  const [app, setApp] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!applicationId) return;
    fetchApplicationDetail(applicationId)
      .then((data) => setApp(data))
      .catch((err) => console.error("Error loading application detail:", err))
      .finally(() => setLoading(false));
  }, [applicationId, pathname]);

  const tabs: TabItem[] = [
    { id: "overview", label: "Overview", href: `/applications/${applicationId}/overview`, icon: FileText },
    { id: "requirements", label: "Requirements", href: `/applications/${applicationId}/requirements`, icon: CheckSquare },
    { id: "documents", label: "Documents", href: `/applications/${applicationId}/documents`, icon: FileBox },
    { id: "payment", label: "Payment", href: `/applications/${applicationId}/payment`, icon: CreditCard },
    { id: "automation", label: "Automation", href: `/applications/${applicationId}/automation`, icon: Cpu },
    { id: "certificate", label: "Certificate", href: `/applications/${applicationId}/certificate`, icon: Award },
    { id: "activity", label: "Activity", href: `/applications/${applicationId}/activity`, icon: History },
  ];

  const client = app?.client;
  const custName = client?.business_name || "Enterprise Customer";
  const applicantName = client?.applicant_name;

  return (
    <div className="flex flex-col min-h-screen bg-slate-50">
      {/* Command Center Sticky Header */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-20 shadow-xs">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
            {/* Left: Back + Identity */}
            <div className="flex items-center gap-3">
              <Link
                href="/applications"
                className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                title="Back to Applications Directory"
              >
                <ArrowLeft className="w-5 h-5" />
              </Link>

              <div>
                <div className="flex items-center gap-2.5">
                  <h1 className="text-xl font-bold text-slate-900 tracking-tight">
                    {loading ? "Loading…" : app?.application_number || "Application"}
                  </h1>
                  {app?.status && <StatusBadge status={app.status} />}
                  <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-slate-100 text-slate-600 border border-slate-200">
                    {app?.status === "MANUAL_PROCESSING" ? "MANUAL" : "AUTOMATION"}
                  </span>
                </div>

                <div className="flex items-center gap-3 text-xs text-slate-500 mt-1">
                  {client?.id ? (
                    <Link
                      href={`/customers/${client.id}`}
                      className="font-medium text-slate-700 hover:text-indigo-600 flex items-center gap-1 group"
                    >
                      <span>{custName}</span>
                      {applicantName && <span className="text-slate-400">({applicantName})</span>}
                      <ExternalLink className="w-3 h-3 text-slate-400 group-hover:text-indigo-600" />
                    </Link>
                  ) : (
                    <span>{custName}</span>
                  )}
                  <span>&bull;</span>
                  <span>Service: {app?.workflow_type || "MSME Registration"}</span>
                  <span>&bull;</span>
                  <span className="flex items-center gap-1">
                    <User className="w-3 h-3 text-slate-400" />
                    <span>{app?.assigned_user?.name || "Unassigned"}</span>
                  </span>
                </div>
              </div>
            </div>

            {/* Right: Quick Action Indicators */}
            <div className="flex items-center gap-2">
              <div className="text-right hidden sm:block">
                <div className="text-[11px] text-slate-400">Target URL</div>
                <div className="text-xs font-semibold text-slate-700">udyamregistration.gov.in</div>
              </div>
            </div>
          </div>

          {/* Sub-Tabs Bar */}
          <nav className="flex items-center gap-1 mt-4 -mb-4 overflow-x-auto border-t border-slate-100 pt-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const isActive = pathname === tab.href || pathname.startsWith(`${tab.href}/`);
              return (
                <Link
                  key={tab.id}
                  href={tab.href}
                  className={`flex items-center gap-2 px-3.5 py-2.5 text-xs font-semibold border-b-2 transition-colors whitespace-nowrap ${
                    isActive
                      ? "border-indigo-600 text-indigo-600 bg-indigo-50/40"
                      : "border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50"
                  }`}
                >
                  <Icon className={`w-3.5 h-3.5 ${isActive ? "text-indigo-600" : "text-slate-400"}`} />
                  <span>{tab.label}</span>
                </Link>
              );
            })}
          </nav>
        </div>
      </header>

      {/* Main Tab Content View */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6">
        {children}
      </main>
    </div>
  );
}
