"use client";

import React from "react";

type Tone = "blue" | "amber" | "indigo" | "emerald" | "rose" | "purple" | "slate";

const TONE_BY_STATE: Record<string, Tone> = {
  NEW: "blue",
  FORM_SENT: "blue",
  FORM_SUBMITTED: "indigo",
  REVIEW_REQUIRED: "purple",
  READY_FOR_PAYMENT: "amber",
  PAYMENT_COMPLETED: "emerald",
  READY_FOR_AUTOMATION: "indigo",
  AUTOMATION_RUNNING: "indigo",
  PORTAL_RUNNING: "indigo",
  READY_FOR_PORTAL: "indigo",
  OTP_REQUIRED: "amber",
  AADHAAR_OTP: "amber",
  OTP_VERIFIED: "blue",
  FINAL_SUBMISSION: "purple",
  REGISTRATION_COMPLETED: "emerald",
  CERTIFICATE_RETRIEVED: "emerald",
  CERTIFICATE_READY: "emerald",
  CLIENT_NOTIFIED: "emerald",
  COMPLETED: "emerald",
  MANUAL_PROCESSING: "amber",
  AUTOMATION_FAILED: "rose",
  EXCEPTION: "rose",
  CANCELLED: "slate",
};

const TONE_CLASSES: Record<Tone, string> = {
  blue: "bg-blue-50 text-blue-700 border-blue-200",
  amber: "bg-amber-50 text-amber-800 border-amber-200",
  indigo: "bg-indigo-50 text-indigo-700 border-indigo-200",
  emerald: "bg-emerald-50 text-emerald-800 border-emerald-200",
  rose: "bg-rose-50 text-rose-700 border-rose-200",
  purple: "bg-purple-50 text-purple-700 border-purple-200",
  slate: "bg-slate-100 text-slate-700 border-slate-200",
};

const HUMAN_LABELS: Record<string, string> = {
  NEW: "New",
  FORM_SENT: "Form Sent",
  FORM_SUBMITTED: "Form Submitted",
  REVIEW_REQUIRED: "Review Required",
  READY_FOR_PAYMENT: "Ready for Payment",
  PAYMENT_COMPLETED: "Payment Completed",
  READY_FOR_AUTOMATION: "Ready for Automation",
  AUTOMATION_RUNNING: "Automation Running",
  PORTAL_RUNNING: "Automation Running",
  READY_FOR_PORTAL: "Ready for Automation",
  OTP_REQUIRED: "OTP Required",
  AADHAAR_OTP: "OTP Required",
  OTP_VERIFIED: "OTP Verified",
  FINAL_SUBMISSION: "Final Submission",
  REGISTRATION_COMPLETED: "Registered",
  CERTIFICATE_RETRIEVED: "Certificate Retrieved",
  CERTIFICATE_READY: "Certificate Ready",
  CLIENT_NOTIFIED: "Client Notified",
  COMPLETED: "Completed",
  MANUAL_PROCESSING: "Manual Processing",
  AUTOMATION_FAILED: "Automation Failed",
  EXCEPTION: "Exception",
  CANCELLED: "Cancelled",
};

export function StatusBadge({ status, className = "" }: { status?: string; className?: string }) {
  const key = status?.toUpperCase().trim() ?? "";
  const tone = TONE_BY_STATE[key] ?? "slate";
  const label = HUMAN_LABELS[key] ?? (key.replace(/_/g, " ") || "Unknown");

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-semibold border ${TONE_CLASSES[tone]} ${className}`}
    >
      <span className={`w-1.5 h-1.5 rounded-full mr-1.5 ${
        tone === "emerald" ? "bg-emerald-500" :
        tone === "amber" ? "bg-amber-500" :
        tone === "rose" ? "bg-rose-500" :
        tone === "blue" ? "bg-blue-500" :
        tone === "purple" ? "bg-purple-500" : "bg-indigo-500"
      }`} />
      {label}
    </span>
  );
}