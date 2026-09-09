"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  FileBox,
  Search,
  Filter,
  FileCheck,
  Eye,
  Download,
  ArrowUpRight,
  RefreshCw,
} from "lucide-react";

import { apiClient } from "@/api/workflow";

export default function GlobalDocumentsPage() {
  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState("ALL");

  async function loadDocuments() {
    setLoading(true);
    try {
      const res = await apiClient.get<any[]>("/documents");
      setDocuments(res.data || []);
    } catch (err) {
      console.error("Failed to load documents:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDocuments();
  }, []);

  const filteredDocs = documents.filter((doc) => {
    const matchesSearch =
      doc.file_name?.toLowerCase().includes(search.toLowerCase()) ||
      doc.application_number?.toLowerCase().includes(search.toLowerCase());
    const matchesType = typeFilter === "ALL" || doc.document_type === typeFilter;
    return matchesSearch && matchesType;
  });

  return (
    <div className="p-8 max-w-7xl mx-auto space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-6 border-b border-slate-200">
        <div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-900">
            Global Documents Repository
          </h1>
          <p className="text-sm text-slate-500 mt-1">
            Master repository of all client identity files, utility bills, and generated certificates.
          </p>
        </div>

        <button
          onClick={loadDocuments}
          className="inline-flex items-center gap-2 px-3 py-2 text-xs font-semibold text-slate-700 bg-white border border-slate-300 rounded-lg hover:bg-slate-50 transition-colors shadow-xs"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? "animate-spin" : ""}`} />
          <span>Refresh</span>
        </button>
      </div>

      {/* Filter & Search Bar */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-3 bg-white p-3 border border-slate-200 rounded-xl shadow-xs">
        <div className="relative w-full sm:w-80">
          <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by file name or case ID…"
            className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600 text-slate-900"
          />
        </div>

        <div className="flex items-center gap-3 w-full sm:w-auto">
          <select
            value={typeFilter}
            onChange={(e) => setTypeFilter(e.target.value)}
            className="px-3 py-1.5 text-xs bg-white border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600"
          >
            <option value="ALL">All Document Types</option>
            <option value="PAN_CARD">PAN Card</option>
            <option value="AADHAAR_CARD">Aadhaar Card</option>
            <option value="BANK_STATEMENT">Bank Statement</option>
            <option value="ELECTRICITY_BILL">Electricity Bill</option>
            <option value="UDYAM_CERTIFICATE">Udyam Certificate</option>
          </select>

          <div className="text-xs text-slate-500 whitespace-nowrap">
            Showing <strong className="text-slate-800">{filteredDocs.length}</strong> files
          </div>
        </div>
      </div>

      {/* Documents Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        {loading ? (
          <div className="p-16 text-center text-sm text-slate-400">Loading document catalog…</div>
        ) : filteredDocs.length === 0 ? (
          <div className="p-16 text-center">
            <FileBox className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-800">No documents found</div>
            <div className="text-xs text-slate-500 mt-1">Uploaded case files will appear here.</div>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-sm">
              <thead>
                <tr className="ops-table-header">
                  <th className="px-5 py-3">File Name</th>
                  <th className="px-5 py-3">Document Type</th>
                  <th className="px-5 py-3">Verification</th>
                  <th className="px-5 py-3">File Size</th>
                  <th className="px-5 py-3">Uploaded</th>
                  <th className="px-5 py-3 text-right">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {filteredDocs.map((doc) => {
                  const isVerified = doc.verified || doc.status === "VERIFIED";

                  return (
                    <tr key={doc.id} className="ops-table-row">
                      <td className="px-5 py-3.5 font-semibold text-slate-900 flex items-center gap-2">
                        <FileCheck className="w-4 h-4 text-indigo-600 flex-shrink-0" />
                        <span className="truncate max-w-[260px]">{doc.file_name || "Document.pdf"}</span>
                      </td>
                      <td className="px-5 py-3.5 text-xs text-slate-600 font-medium">
                        {(doc.document_type || "Other").replace(/_/g, " ")}
                      </td>
                      <td className="px-5 py-3.5">
                        <span
                          className={`inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold border ${
                            isVerified
                              ? "bg-emerald-50 text-emerald-800 border-emerald-200"
                              : "bg-amber-50 text-amber-800 border-amber-200"
                          }`}
                        >
                          <span
                            className={`w-1.5 h-1.5 rounded-full ${
                              isVerified ? "bg-emerald-500" : "bg-amber-500"
                            }`}
                          />
                          {isVerified ? "Verified" : "Pending Review"}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 text-xs text-slate-500">
                        {doc.file_size_bytes
                          ? `${(doc.file_size_bytes / 1024).toFixed(0)} KB`
                          : "120 KB"}
                      </td>
                      <td className="px-5 py-3.5 text-xs text-slate-500">
                        {doc.created_at ? new Date(doc.created_at).toLocaleDateString() : "—"}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <a
                          href={`/api/v1/documents/${doc.id}/file`}
                          target="_blank"
                          rel="noreferrer"
                          className="px-3 py-1 bg-indigo-50 hover:bg-indigo-100 text-indigo-700 rounded-lg text-xs font-semibold transition-colors inline-block"
                        >
                          View File
                        </a>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
}