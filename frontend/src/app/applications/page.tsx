"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  Search,
  Filter,
  Plus,
  ArrowUpDown,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
  ArrowUpRight,
  CheckCircle,
} from "lucide-react";

import { fetchApplications, createApplication, ApplicationItem } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

const STATUS_TABS = [
  { id: "ALL", label: "All Cases" },
  { id: "PENDING_REQUIREMENTS", label: "Pending Requirements", filter: "NEW,FORM_SENT" },
  { id: "REVIEW", label: "Review Required", filter: "FORM_SUBMITTED,REVIEW_REQUIRED,NIC_REVIEW,VALIDATION_REVIEW" },
  { id: "PAYMENT", label: "Pending Payment", filter: "READY_FOR_PAYMENT" },
  { id: "AUTOMATION", label: "Ready for Automation", filter: "READY_FOR_PORTAL,READY_FOR_AUTOMATION,APPROVED" },
  { id: "RUNNING", label: "Running", filter: "PORTAL_RUNNING,AUTOMATION_RUNNING,OTP_REQUIRED" },
  { id: "EXCEPTIONS", label: "Exceptions / Issues", filter: "EXCEPTION,FAILED,REJECTED" },
  { id: "COMPLETED", label: "Completed", filter: "COMPLETED,CERTIFICATE_READY,REGISTERED" },
];

export default function ApplicationsPage() {
  const router = useRouter();
  const [applications, setApplications] = useState<ApplicationItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);

  // Filters & Pagination
  const [search, setSearch] = useState("");
  const [activeTab, setActiveTab] = useState("ALL");
  const [page, setPage] = useState(0);
  const pageSize = 15;

  // New Application Modal
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

  async function loadApplications() {
    setLoading(true);
    try {
      const tabObj = STATUS_TABS.find((t) => t.id === activeTab);
      const statusParam = tabObj?.filter;
      const res = await fetchApplications({
        search: search.trim() || undefined,
        status: statusParam,
        skip: page * pageSize,
        limit: pageSize,
      });
      setApplications(res.items);
      setTotal(res.total);
    } catch (err) {
      console.error("Failed to load applications:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadApplications();
  }, [activeTab, page]);

  function handleSearchSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPage(0);
    loadApplications();
  }

  async function handleCreate(e: React.FormEvent) {
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
      if (res.id) {
        router.push(`/applications/${res.id}/overview`);
      } else {
        loadApplications();
      }
    } catch (err: any) {
      setFormError(err.response?.data?.detail || "Failed to create application.");
    } finally {
      setCreating(false);
    }
  }

  const totalPages = Math.ceil(total / pageSize) || 1;

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Applications Directory
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Primary working queue for all client MSME & Udyam registrations.
          </p>
        </div>

        <button
          onClick={() => setShowNewModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 rounded-lg hover:bg-indigo-700 transition-colors shadow-sm"
        >
          <Plus className="w-4 h-4" />
          <span>New Application</span>
        </button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-1 overflow-x-auto border-b border-slate-200 pb-px">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => {
              setActiveTab(tab.id);
              setPage(0);
            }}
            className={`px-3 py-2 text-xs font-semibold rounded-t-md transition-colors whitespace-nowrap border-b-2 ${
              activeTab === tab.id
                ? "border-indigo-600 text-indigo-600 bg-indigo-50/50"
                : "border-transparent text-slate-500 hover:text-slate-800 hover:bg-slate-50"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Search & Actions Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 border border-slate-200 rounded-xl shadow-xs">
        <form onSubmit={handleSearchSubmit} className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by ID, business, PAN…"
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600 text-slate-900 placeholder:text-slate-400"
          />
        </form>

        <div className="flex items-center gap-2 text-xs text-slate-500">
          <span>
            Showing <strong className="text-slate-800">{total > 0 ? page * pageSize + 1 : 0}</strong>–
            <strong className="text-slate-800">{Math.min((page + 1) * pageSize, total)}</strong> of{" "}
            <strong className="text-slate-800">{total}</strong> cases
          </span>
          <button
            onClick={loadApplications}
            className="p-1.5 hover:bg-slate-100 rounded text-slate-600 ml-1 transition-colors"
            title="Refresh table"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          </button>
        </div>
      </div>

      {/* Applications Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden">
        {loading ? (
          <div className="p-16 text-center text-sm text-slate-400">Loading applications…</div>
        ) : applications.length === 0 ? (
          <div className="p-16 text-center">
            <CheckCircle className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-800">No applications found</div>
            <div className="text-xs text-slate-500 mt-1">Try adjusting your search or status filter.</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="ops-table-header">
                  <th className="px-5 py-3">Application ID</th>
                  <th className="px-5 py-3">Customer / Enterprise</th>
                  <th className="px-5 py-3">Service</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Assigned To</th>
                  <th className="px-5 py-3">Created</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {applications.map((app) => (
                  <tr
                    key={app.id}
                    onClick={() => router.push(`/applications/${app.id}/overview`)}
                    className="ops-table-row cursor-pointer group"
                  >
                    <td className="px-5 py-3.5 font-semibold text-indigo-600 group-hover:text-indigo-800">
                      {app.application_number}
                    </td>
                    <td className="px-5 py-3.5">
                      <div className="font-semibold text-slate-900 truncate max-w-[220px]">
                        {app.business_name || "Enterprise Client"}
                      </div>
                      {app.applicant_name && (
                        <div className="text-xs text-slate-400">{app.applicant_name}</div>
                      )}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600">
                      {app.workflow_type || "MSME Registration"}
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={app.status} />
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600">
                      {app.assigned_employee_name || "Unassigned"}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-500">
                      {app.created_at ? new Date(app.created_at).toLocaleDateString() : "—"}
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

        {/* Pagination Footer */}
        <div className="p-4 border-t border-slate-200 flex items-center justify-between bg-slate-50/50">
          <div className="text-xs text-slate-500">
            Page {page + 1} of {totalPages}
          </div>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setPage((p) => Math.max(0, p - 1))}
              disabled={page === 0 || loading}
              className="p-1.5 rounded border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 transition-colors"
            >
              <ChevronLeft className="w-4 h-4" />
            </button>
            <button
              onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
              disabled={page >= totalPages - 1 || loading}
              className="p-1.5 rounded border border-slate-300 text-slate-600 hover:bg-slate-100 disabled:opacity-40 transition-colors"
            >
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>

      {/* New Application Modal */}
      {showNewModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-lg w-full border border-slate-200 shadow-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Create New Application</h3>
                <p className="text-xs text-slate-500">Initiate a new MSME registration case.</p>
              </div>
              <button
                onClick={() => setShowNewModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleCreate} className="p-6 space-y-4">
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
                    placeholder="e.g. Apex Tech Ltd"
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
                    placeholder="e.g. Ankit Sharma"
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
                    placeholder="ankit@example.com"
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
