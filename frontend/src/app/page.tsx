"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  FileText,
  Clock,
  CreditCard,
  PlayCircle,
  Cpu,
  KeyRound,
  CheckCircle2,
  AlertCircle,
  ArrowUpRight,
  Plus,
  RefreshCw,
  Search,
} from "lucide-react";

import { fetchDashboardSummary, fetchNeedsAttention, createApplication, DashboardSummary, NeedsAttentionItem } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

export default function DashboardPage() {
  const router = useRouter();
  const [summary, setSummary] = useState<DashboardSummary | null>(null);
  const [needsAttention, setNeedsAttention] = useState<NeedsAttentionItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  // New Application Modal State
  const [showNewModal, setShowNewModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [formData, setFormData] = useState({
    business_name: "",
    applicant_name: "",
    mobile_number: "",
    email: "",
    pan_number: "",
    aadhaar_number: "",
  });

  async function loadData() {
    try {
      const [sum, attention] = await Promise.all([
        fetchDashboardSummary(),
        fetchNeedsAttention(12),
      ]);
      setSummary(sum);
      setNeedsAttention(attention);
    } catch (err) {
      console.error("Failed to load dashboard data:", err);
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }

  useEffect(() => {
    loadData();
  }, []);

  async function handleCreateApplication(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setCreating(true);
    try {
      const res = await createApplication(formData);
      setShowNewModal(false);
      setFormData({
        business_name: "",
        applicant_name: "",
        mobile_number: "",
        email: "",
        pan_number: "",
        aadhaar_number: "",
      });
      // Redirect to the newly created application
      if (res.id) {
        router.push(`/applications/${res.id}/overview`);
      } else {
        loadData();
      }
    } catch (err: any) {
      setFormError(err.response?.data?.detail || "Failed to create application. Please check input.");
    } finally {
      setCreating(false);
    }
  }

  const metricCards = [
    {
      title: "Total Applications",
      count: summary?.total_applications ?? 0,
      icon: FileText,
      color: "text-slate-700 bg-slate-100",
      filterUrl: "/applications",
    },
    {
      title: "Pending Requirements",
      count: summary?.pending_requirements ?? 0,
      icon: Clock,
      color: "text-amber-700 bg-amber-50",
      filterUrl: "/applications?status=NEW,FORM_SENT",
    },
    {
      title: "Pending Payment",
      count: summary?.pending_payment ?? 0,
      icon: CreditCard,
      color: "text-blue-700 bg-blue-50",
      filterUrl: "/applications?status=READY_FOR_PAYMENT,FORM_SUBMITTED",
    },
    {
      title: "Ready for Automation",
      count: summary?.ready_for_automation ?? 0,
      icon: PlayCircle,
      color: "text-indigo-700 bg-indigo-50",
      filterUrl: "/applications?status=READY_FOR_PORTAL,READY_FOR_AUTOMATION",
    },
    {
      title: "Automation Running",
      count: summary?.automation_running ?? 0,
      icon: Cpu,
      color: "text-purple-700 bg-purple-50",
      filterUrl: "/applications?status=PORTAL_RUNNING,AUTOMATION_RUNNING",
    },
    {
      title: "Waiting for OTP",
      count: summary?.waiting_for_otp ?? 0,
      icon: KeyRound,
      color: "text-rose-700 bg-rose-50",
      filterUrl: "/applications?status=OTP_REQUIRED,AADHAAR_OTP",
    },
    {
      title: "Completed Cases",
      count: summary?.completed ?? 0,
      icon: CheckCircle2,
      color: "text-emerald-700 bg-emerald-50",
      filterUrl: "/applications?status=COMPLETED,CERTIFICATE_READY,REGISTERED",
    },
  ];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-8">
      {/* Header Bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Operations Dashboard
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Realtime workload metrics and cases requiring employee attention.
          </p>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => {
              setRefreshing(true);
              loadData();
            }}
            disabled={refreshing}
            className="inline-flex items-center gap-2 px-3 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors shadow-sm"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </button>

          <button
            onClick={() => setShowNewModal(true)}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>New Application</span>
          </button>
        </div>
      </div>

      {/* KPI Cards Grid */}
      <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-7 gap-3">
        {metricCards.map((card) => {
          const Icon = card.icon;
          return (
            <Link
              key={card.title}
              href={card.filterUrl}
              className="bg-white border border-slate-200 rounded-xl p-4 hover:border-indigo-300 hover:shadow-sm transition-all group"
            >
              <div className="flex items-center justify-between mb-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${card.color}`}>
                  <Icon className="w-4 h-4" />
                </div>
                <ArrowUpRight className="w-3.5 h-3.5 text-slate-300 group-hover:text-indigo-600 transition-colors" />
              </div>
              <div className="text-2xl font-bold text-slate-900 tracking-tight">
                {loading ? "…" : card.count}
              </div>
              <div className="text-[11px] font-medium text-slate-500 mt-1 truncate" title={card.title}>
                {card.title}
              </div>
            </Link>
          );
        })}
      </div>

      {/* Needs Attention Operational Section */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
          <div className="flex items-center gap-2.5">
            <div className="w-2.5 h-2.5 rounded-full bg-rose-500 animate-pulse" />
            <div>
              <h2 className="text-base font-bold text-slate-900">
                Needs Attention
              </h2>
              <p className="text-xs text-slate-500">
                Applications blocked or waiting on human intervention (OTP, Review, Payment, Verification).
              </p>
            </div>
          </div>

          <Link
            href="/applications"
            className="text-xs font-semibold text-indigo-600 hover:text-indigo-800 flex items-center gap-1"
          >
            <span>View All Applications</span>
            <ArrowUpRight className="w-3.5 h-3.5" />
          </Link>
        </div>

        {loading ? (
          <div className="p-12 text-center text-sm text-slate-400">Loading cases…</div>
        ) : needsAttention.length === 0 ? (
          <div className="p-12 text-center">
            <CheckCircle2 className="w-8 h-8 text-emerald-500 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-900">All caught up!</div>
            <div className="text-xs text-slate-500 mt-1">
              No applications currently require urgent employee intervention.
            </div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="ops-table-header">
                  <th className="px-5 py-3">Application</th>
                  <th className="px-5 py-3">Customer / Business</th>
                  <th className="px-5 py-3">Current Status</th>
                  <th className="px-5 py-3">Mode</th>
                  <th className="px-5 py-3">Assigned To</th>
                  <th className="px-5 py-3">Action Required</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {needsAttention.map((item) => (
                  <tr
                    key={item.id}
                    onClick={() => router.push(`/applications/${item.id}/overview`)}
                    className="ops-table-row cursor-pointer group"
                  >
                    <td className="px-5 py-3.5 font-semibold text-indigo-600 group-hover:text-indigo-800">
                      {item.application_number}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-slate-900 truncate max-w-[200px]">
                        {item.customer_name}
                      </div>
                      {item.customer_phone && (
                        <div className="text-xs text-slate-400">{item.customer_phone}</div>
                      )}
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={item.status} />
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600 font-medium">
                      {item.processing_mode}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600">
                      {item.assigned_employee_name || "Unassigned"}
                    </td>
                    <td className="px-5 py-3.5">
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded bg-amber-50 text-amber-800 border border-amber-200 text-xs font-medium">
                        <AlertCircle className="w-3 h-3 text-amber-600" />
                        {item.action_required}
                      </span>
                    </td>
                    <td className="px-5 py-3.5 text-right">
                      <span className="text-xs font-semibold text-indigo-600 group-hover:underline inline-flex items-center gap-0.5">
                        Open Command Center
                        <ArrowUpRight className="w-3 h-3" />
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* New Application Modal */}
      {showNewModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-lg w-full border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Create New Application</h3>
                <p className="text-xs text-slate-500">Initiate a new MSME registration case for a customer.</p>
              </div>
              <button
                onClick={() => setShowNewModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreateApplication} className="p-6 space-y-4">
              {formError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs">
                  {formError}
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Business / Enterprise Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.business_name}
                    onChange={(e) => setFormData({ ...formData, business_name: e.target.value })}
                    placeholder="e.g. Apex Engineering Ltd"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Applicant / Owner Name *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.applicant_name}
                    onChange={(e) => setFormData({ ...formData, applicant_name: e.target.value })}
                    placeholder="e.g. Rajesh Kumar"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Mobile Number (WhatsApp) *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.mobile_number}
                    onChange={(e) => setFormData({ ...formData, mobile_number: e.target.value })}
                    placeholder="9876543210"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Email Address
                  </label>
                  <input
                    type="email"
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    placeholder="rajesh@example.com"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    PAN Number *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.pan_number}
                    onChange={(e) => setFormData({ ...formData, pan_number: e.target.value.toUpperCase() })}
                    placeholder="ABCDE1234F"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg uppercase focus:outline-none focus:ring-2 focus:ring-indigo-600"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Aadhaar Number *
                  </label>
                  <input
                    type="text"
                    required
                    value={formData.aadhaar_number}
                    onChange={(e) => setFormData({ ...formData, aadhaar_number: e.target.value })}
                    placeholder="12-digit Aadhaar"
                    className="w-full px-3 py-2 text-sm border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
                  />
                </div>
              </div>

              <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowNewModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors"
                >
                  {creating ? "Creating Case…" : "Create & Send Form"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
