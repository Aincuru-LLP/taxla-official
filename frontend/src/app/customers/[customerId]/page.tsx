"use client";

import React, { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  Users,
  Building,
  Phone,
  Mail,
  CreditCard,
  Calendar,
  FileText,
  ArrowLeft,
  ArrowUpRight,
  Plus,
  MessageSquare,
  ShieldCheck,
} from "lucide-react";

import { fetchCustomerDetail, CustomerDetail } from "@/lib/api";
import { StatusBadge } from "@/components/StatusBadge";

export default function CustomerProfilePage() {
  const params = useParams();
  const router = useRouter();
  const customerId = params?.customerId as string;

  const [customer, setCustomer] = useState<CustomerDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!customerId) return;
    fetchCustomerDetail(customerId)
      .then((data) => setCustomer(data))
      .catch((err) => console.error("Failed to load customer profile:", err))
      .finally(() => setLoading(false));
  }, [customerId]);

  if (loading) {
    return <div className="p-16 text-center text-sm text-slate-400">Loading customer profile…</div>;
  }

  if (!customer) {
    return (
      <div className="p-16 text-center">
        <h2 className="text-base font-bold text-slate-900">Customer Not Found</h2>
        <Link href="/customers" className="text-xs text-indigo-600 hover:underline mt-2 inline-block">
          Return to Customer Directory
        </Link>
      </div>
    );
  }

  const apps = customer.applications || [];

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Back Button & Top Navigation */}
      <div className="flex items-center gap-3">
        <Link
          href="/customers"
          className="p-2 text-slate-400 hover:text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
          title="Back to Customers Directory"
        >
          <ArrowLeft className="w-5 h-5" />
        </Link>
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            {customer.business_name}
          </h1>
          <p className="text-xs text-slate-500 mt-0.5">
            Customer Profile &bull; ID: <span className="font-mono">{customer.id}</span>
          </p>
        </div>
      </div>

      {/* Customer Profile Details Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs">
        <div className="flex items-center justify-between pb-4 border-b border-slate-100">
          <h2 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <Users className="w-4 h-4 text-indigo-600" />
            <span>Contact & Identification Details</span>
          </h2>

          <div className="flex items-center gap-1.5 px-3 py-1 bg-emerald-50 text-emerald-800 border border-emerald-200 rounded-full text-xs font-semibold">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-600" />
            <span>WhatsApp Connected</span>
          </div>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 pt-4 text-xs">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Applicant / Owner</span>
            <div className="font-bold text-slate-900 mt-0.5">{customer.applicant_name}</div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Mobile (WhatsApp)</span>
            <div className="font-bold text-slate-900 mt-0.5">{customer.mobile_number}</div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Email Address</span>
            <div className="font-bold text-slate-900 mt-0.5 truncate">{customer.email || "—"}</div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">PAN Number</span>
            <div className="font-mono font-bold text-slate-900 mt-0.5 uppercase">
              {customer.pan_number || "—"}
            </div>
          </div>
        </div>
      </div>

      {/* Linked Applications List */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        <div className="p-5 border-b border-slate-200 flex items-center justify-between bg-slate-50/50">
          <div>
            <h2 className="text-base font-bold text-slate-900">
              Linked Applications ({apps.length})
            </h2>
            <p className="text-xs text-slate-500 mt-0.5">
              MSME registrations owned by this enterprise customer.
            </p>
          </div>

          <Link
            href="/applications"
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg transition-colors shadow-xs"
          >
            <Plus className="w-3.5 h-3.5" />
            <span>Create Application</span>
          </Link>
        </div>

        {apps.length === 0 ? (
          <div className="p-12 text-center text-xs text-slate-400">
            No active applications found for this customer.
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="ops-table-header">
                  <th className="px-5 py-3">Application ID</th>
                  <th className="px-5 py-3">Service</th>
                  <th className="px-5 py-3">Status</th>
                  <th className="px-5 py-3">Mode</th>
                  <th className="px-5 py-3">Created</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {apps.map((app) => (
                  <tr
                    key={app.id}
                    onClick={() => router.push(`/applications/${app.id}/overview`)}
                    className="ops-table-row cursor-pointer group"
                  >
                    <td className="px-5 py-3.5 font-semibold text-indigo-600 group-hover:text-indigo-800">
                      {app.application_number}
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600 font-medium">
                      {app.service}
                    </td>
                    <td className="px-5 py-3.5">
                      <StatusBadge status={app.status} />
                    </td>
                    <td className="px-5 py-3.5 text-xs text-slate-600">
                      {app.processing_mode}
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
      </div>
    </div>
  );
}
