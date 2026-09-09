"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  FileBox,
  Upload,
  CheckCircle,
  FileCheck,
  Eye,
  Download,
  AlertCircle,
  Plus,
} from "lucide-react";

import { fetchApplicationDocuments, uploadApplicationDocument, verifyDocument } from "@/lib/api";

export default function DocumentsTabPage() {
  const params = useParams();
  const applicationId = params?.id as string;

  const [documents, setDocuments] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  // Upload Modal State
  const [showUploadModal, setShowUploadModal] = useState(false);
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [docType, setDocType] = useState("PAN_CARD");
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);

  async function loadDocs() {
    try {
      const data = await fetchApplicationDocuments(applicationId);
      setDocuments(data || []);
    } catch (err) {
      console.error("Failed to load documents:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!applicationId) return;
    loadDocs();
  }, [applicationId]);

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!selectedFile) return;
    setUploadError(null);
    setUploading(true);
    try {
      await uploadApplicationDocument(applicationId, selectedFile, docType);
      setShowUploadModal(false);
      setSelectedFile(null);
      loadDocs();
    } catch (err: any) {
      setUploadError(err?.response?.data?.detail || "Document upload failed.");
    } finally {
      setUploading(false);
    }
  }

  async function handleVerify(docId: string, currentStatus: boolean) {
    try {
      await verifyDocument(docId, !currentStatus);
      loadDocs();
    } catch (err) {
      console.error("Failed to update verification status:", err);
    }
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-5 shadow-xs flex items-center justify-between">
        <div>
          <h2 className="text-base font-bold text-slate-900">Application Documents</h2>
          <p className="text-xs text-slate-500 mt-1">
            Uploaded identity, financial, address verification, and statutory registration files.
          </p>
        </div>

        <button
          onClick={() => setShowUploadModal(true)}
          className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span>Upload Document</span>
        </button>
      </div>

      {/* Documents Table */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-xs overflow-hidden">
        {loading ? (
          <div className="p-12 text-center text-sm text-slate-400">Loading documents…</div>
        ) : documents.length === 0 ? (
          <div className="p-12 text-center">
            <FileBox className="w-8 h-8 text-slate-300 mx-auto mb-2" />
            <div className="text-sm font-semibold text-slate-800">No documents attached</div>
            <div className="text-xs text-slate-500 mt-1">
              Upload customer identification and support files here.
            </div>
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
                  <th className="px-5 py-3 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {documents.map((doc) => {
                  const isVerified = doc.verified || doc.status === "VERIFIED";

                  return (
                    <tr key={doc.id} className="ops-table-row">
                      <td className="px-5 py-3.5 font-semibold text-slate-900 flex items-center gap-2">
                        <FileCheck className="w-4 h-4 text-indigo-600" />
                        <span>{doc.file_name || doc.name || "Attachment.pdf"}</span>
                      </td>
                      <td className="px-5 py-3.5 text-xs text-slate-600 font-medium">
                        {(doc.document_type || doc.type || "Other").replace(/_/g, " ")}
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
                      <td className="px-5 py-3.5 text-right space-x-2">
                        <button
                          onClick={() => handleVerify(doc.id, isVerified)}
                          className="px-2.5 py-1 text-xs font-semibold rounded border border-slate-300 hover:bg-slate-50 text-slate-700 transition-colors"
                        >
                          {isVerified ? "Unverify" : "Verify Document"}
                        </button>
                        <a
                          href={`/api/v1/documents/${doc.id}/file`}
                          target="_blank"
                          rel="noreferrer"
                          className="px-2.5 py-1 text-xs font-semibold rounded bg-indigo-50 text-indigo-700 hover:bg-indigo-100 transition-colors inline-block"
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

      {/* Upload Document Modal */}
      {showUploadModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-xs z-50 flex items-center justify-center p-4">
          <div className="bg-white rounded-xl max-w-md w-full border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-900">Upload Case Document</h3>
                <p className="text-xs text-slate-500">Attach verification file for this application.</p>
              </div>
              <button
                onClick={() => setShowUploadModal(false)}
                className="text-slate-400 hover:text-slate-600 text-lg font-bold"
              >
                &times;
              </button>
            </div>

            <form onSubmit={handleUpload} className="p-6 space-y-4">
              {uploadError && (
                <div className="p-3 bg-rose-50 border border-rose-200 rounded text-rose-700 text-xs">
                  {uploadError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Document Type *
                </label>
                <select
                  value={docType}
                  onChange={(e) => setDocType(e.target.value)}
                  className="w-full px-3 py-2 text-xs border border-slate-300 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-600 bg-white"
                >
                  <option value="PAN_CARD">PAN Card</option>
                  <option value="AADHAAR_CARD">Aadhaar Card</option>
                  <option value="BANK_STATEMENT">Bank Statement / Passbook</option>
                  <option value="ELECTRICITY_BILL">Electricity Bill (Official Address)</option>
                  <option value="RENT_AGREEMENT">Rent / Lease Agreement</option>
                  <option value="PRIOR_UAM">Prior UAM / Udyog Aadhaar</option>
                  <option value="OTHER">Other Attachment</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-700 mb-1">
                  Select File (PDF or Image) *
                </label>
                <input
                  type="file"
                  required
                  accept=".pdf,image/*"
                  onChange={(e) => setSelectedFile(e.target.files?.[0] || null)}
                  className="w-full text-xs text-slate-500 file:mr-3 file:py-1.5 file:px-3 file:rounded-lg file:border-0 file:text-xs file:font-semibold file:bg-indigo-50 file:text-indigo-700 hover:file:bg-indigo-100"
                />
              </div>

              <div className="pt-4 border-t border-slate-200 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setShowUploadModal(false)}
                  className="px-4 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100 rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={uploading || !selectedFile}
                  className="px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-sm transition-colors"
                >
                  {uploading ? "Uploading…" : "Upload File"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
