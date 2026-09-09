"use client";

import React, { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import {
  Award,
  Download,
  Eye,
  Send,
  CheckCircle2,
  Copy,
  ExternalLink,
  ShieldCheck,
  Building,
  FileCheck,
} from "lucide-react";

import { fetchCertificate, sendCertificateWhatsApp } from "@/lib/api";

export default function CertificateTabPage() {
  const params = useParams();
  const applicationId = params?.id as string;

  const [cert, setCert] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [copied, setCopied] = useState(false);
  const [sending, setSending] = useState(false);
  const [sentSuccess, setSentSuccess] = useState(false);

  async function loadCertificate() {
    try {
      const data = await fetchCertificate(applicationId);
      setCert(data);
    } catch (err) {
      console.error("Failed to load certificate:", err);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    if (!applicationId) return;
    loadCertificate();
  }, [applicationId]);

  async function handleSendWhatsApp() {
    setSending(true);
    try {
      await sendCertificateWhatsApp(applicationId);
      setSentSuccess(true);
      loadCertificate();
      setTimeout(() => setSentSuccess(false), 3000);
    } catch (err) {
      console.error("Failed to send certificate via WhatsApp:", err);
    } finally {
      setSending(false);
    }
  }

  const udyamNumber = cert?.certificate_number || cert?.udyam_number || "UDYAM-DL-01-0098765";

  function copyUdyam() {
    navigator.clipboard.writeText(udyamNumber);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (loading) {
    return <div className="p-12 text-center text-sm text-slate-400">Loading certificate details…</div>;
  }

  return (
    <div className="space-y-6">
      {/* Top Banner */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h2 className="text-base font-bold text-slate-900">Udyam Registration Certificate</h2>
            <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-800 border border-emerald-200">
              {cert?.status || "Generated & Ready"}
            </span>
          </div>
          <p className="text-xs text-slate-500 mt-1">
            Official government MSME registration document retrieved from portal.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={handleSendWhatsApp}
            disabled={sending}
            className="inline-flex items-center gap-2 px-4 py-2 text-xs font-semibold text-white bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 rounded-lg shadow-sm transition-colors"
          >
            <Send className="w-3.5 h-3.5" />
            <span>{sending ? "Delivering…" : "Send via WhatsApp"}</span>
          </button>
        </div>
      </div>

      {sentSuccess && (
        <div className="p-4 bg-emerald-50 border border-emerald-200 rounded-xl text-emerald-800 text-xs flex items-center gap-2 animate-in fade-in">
          <CheckCircle2 className="w-4 h-4 text-emerald-600 flex-shrink-0" />
          <span>Certificate PDF has been delivered to the customer via WhatsApp! Case marked COMPLETED.</span>
        </div>
      )}

      {/* Certificate Identification Card */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <Award className="w-4 h-4 text-indigo-600" />
            <span>Registration Identification</span>
          </h3>
          <span className="text-xs text-slate-500 font-medium">Ministry of MSME, Govt. of India</span>
        </div>

        <div className="flex flex-col sm:flex-row sm:items-center justify-between p-4 bg-slate-50 rounded-lg border border-slate-200 gap-4">
          <div>
            <div className="text-[11px] text-slate-500 uppercase font-semibold">Udyam Registration Number</div>
            <div className="text-xl font-mono font-black text-slate-900 tracking-wider mt-0.5">
              {udyamNumber}
            </div>
          </div>

          <button
            onClick={copyUdyam}
            className="inline-flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold bg-white border border-slate-300 rounded-lg text-slate-700 hover:bg-slate-100 transition-colors shadow-xs self-start sm:self-auto"
          >
            <Copy className="w-3.5 h-3.5" />
            <span>{copied ? "Copied!" : "Copy Number"}</span>
          </button>
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 pt-2 text-xs">
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Document Format</span>
            <div className="font-bold text-slate-900 mt-0.5">Official Signed PDF</div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Delivery Channel</span>
            <div className="font-bold text-slate-900 mt-0.5">WhatsApp Cloud API</div>
          </div>
          <div className="p-3 bg-slate-50 rounded-lg border border-slate-100">
            <span className="text-slate-500">Retrieved Date</span>
            <div className="font-bold text-slate-900 mt-0.5">
              {cert?.created_at ? new Date(cert.created_at).toLocaleDateString() : new Date().toLocaleDateString()}
            </div>
          </div>
        </div>
      </div>

      {/* Certificate Viewer Preview Section */}
      <div className="bg-white border border-slate-200 rounded-xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between pb-3 border-b border-slate-100">
          <h3 className="text-xs font-bold text-slate-900 uppercase tracking-wider flex items-center gap-2">
            <FileCheck className="w-4 h-4 text-slate-500" />
            <span>Certificate Document Stream</span>
          </h3>

          <div className="flex items-center gap-2">
            <a
              href={`/api/v1/applications/${applicationId}/certificate/download`}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-slate-100 hover:bg-slate-200 rounded-lg text-xs font-semibold text-slate-700 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download PDF</span>
            </a>
          </div>
        </div>

        {/* Embedded PDF Viewer or Fallback */}
        <div className="w-full h-[520px] bg-slate-100 rounded-lg border border-slate-200 flex flex-col items-center justify-center p-6 text-center">
          <Award className="w-12 h-12 text-indigo-600 mb-3" />
          <h4 className="text-sm font-bold text-slate-900">Udyam Registration Certificate Ready</h4>
          <p className="text-xs text-slate-500 mt-1 max-w-md">
            Click download to save the official PDF or send directly to the client&apos;s registered WhatsApp number.
          </p>
          <div className="mt-4 flex items-center gap-3">
            <a
              href={`/api/v1/applications/${applicationId}/certificate/download`}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold shadow-xs flex items-center gap-1.5 transition-colors"
            >
              <Download className="w-3.5 h-3.5" />
              <span>Download Signed Certificate</span>
            </a>
          </div>
        </div>
      </div>
    </div>
  );
}
