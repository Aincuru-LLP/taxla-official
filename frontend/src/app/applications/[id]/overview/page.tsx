"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import {
  Building2,
  User,
  Phone,
  Mail,
  CreditCard,
  CheckCircle2,
  Clock,
  Copy,
  ExternalLink,
  ShieldCheck,
  Briefcase,
  MapPin,
} from "lucide-react";

import { fetchApplicationDetail } from "@/lib/api";
import { WorkflowStepper } from "@/components/WorkflowStepper";
import { StatusBadge } from "@/components/StatusBadge";

export default function OverviewTabPage() {
  const params = useParams();
  const applicationId = params?.id as string;

  const [app, setApp] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [copiedLink, setCopiedLink] = useState(false);

  useEffect(() => {
    if (!applicationId) return;
    fetchApplicationDetail(applicationId)
      .then((data) => setApp(data))
      .catch((err) => console.error(err))
      .finally(() => setLoading(false));
  }, [applicationId]);

  if (loading) {
    return <div className="p-12 text-center text-sm text-slate-400">Loading overview…</div>;
  }

  const client = app?.client;
  const formUrl = typeof window !== "undefined"
    ? `${window.location.origin}/form/${app?.application_number}/token`
    : `/form/${app?.application_number}/token`;

  function copyFormUrl() {
    navigator.clipboard.writeText(formUrl);
    setCopiedLink(true);
    setTimeout(() => setCopiedLink(false), 2500);
  }

  return (
    <div className="space-y-6">
      {/* 9-Stage Operational Stepper */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs">
        <h2 className="text-xs font-bold text-slate-700 uppercase tracking-wider mb-3">
          Application Lifecycle Progression
        </h2>
        <WorkflowStepper status={app?.status} />
      </div>

      {/* Customer Intake Token Link Banner */}
      <div className="bg-indigo-50 border border-indigo-200 rounded-xl p-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3">
        <div>
          <div className="text-xs font-bold text-indigo-900 flex items-center gap-1.5">
            <ExternalLink className="w-3.5 h-3.5 text-indigo-600" />
            <span>Customer Requirement Intake Link</span>
          </div>
          <p className="text-xs text-indigo-700 mt-0.5">
            Share this link with the customer to complete their requirements on mobile or desktop.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={copyFormUrl}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-white border border-indigo-300 rounded-lg text-xs font-semibold text-indigo-700 hover:bg-indigo-100 transition-colors shadow-xs"
          >
            <Copy className="w-3.5 h-3.5" />
            <span>{copiedLink ? "Link Copied!" : "Copy Form Link"}</span>
          </button>
          <a
            href={formUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 px-3 py-1.5 bg-indigo-600 rounded-lg text-xs font-semibold text-white hover:bg-indigo-700 transition-colors shadow-xs"
          >
            <span>Open Form</span>
            <ExternalLink className="w-3 h-3" />
          </a>
        </div>
      </div>

      {/* 2-Column Info Grid */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Customer & Contact Summary */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <Building2 className="w-4 h-4 text-slate-500" />
              <span>Customer Information</span>
            </h3>
            {client?.id && (
              <Link
                href={`/customers/${client.id}`}
                className="text-xs font-semibold text-indigo-600 hover:underline flex items-center gap-1"
              >
                <span>Full Profile</span>
                <ExternalLink className="w-3 h-3" />
              </Link>
            )}
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Enterprise Name</span>
              <span className="font-semibold text-slate-900">{client?.business_name || "—"}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Applicant / Owner</span>
              <span className="font-semibold text-slate-900">{client?.applicant_name || "—"}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Mobile (WhatsApp)</span>
              <span className="font-semibold text-slate-900">{client?.mobile_number || "—"}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Email</span>
              <span className="font-semibold text-slate-900">{client?.email || "—"}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">PAN</span>
              <span className="font-semibold text-slate-900 uppercase">{client?.pan_number || "—"}</span>
            </div>
          </div>
        </div>

        {/* Enterprise & Registration Profile */}
        <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs space-y-4">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
              <Briefcase className="w-4 h-4 text-slate-500" />
              <span>Registration Details</span>
            </h3>
            <StatusBadge status={app?.status} />
          </div>

          <div className="space-y-3 text-xs">
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Service Workflow</span>
              <span className="font-semibold text-slate-900">{app?.workflow_type || "MSME Registration"}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Enterprise Type</span>
              <span className="font-semibold text-slate-900">{app?.enterprise_type || "Proprietorship"}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Major Activity</span>
              <span className="font-semibold text-slate-900">{app?.major_activity || "Services"}</span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Total Employees</span>
              <span className="font-semibold text-slate-900">
                {(app?.male_employees || 0) + (app?.female_employees || 0) + (app?.other_employees || 0)}
              </span>
            </div>
            <div className="flex justify-between py-1 border-b border-slate-50">
              <span className="text-slate-500">Created Date</span>
              <span className="font-semibold text-slate-900">
                {app?.created_at ? new Date(app.created_at).toLocaleString() : "—"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
